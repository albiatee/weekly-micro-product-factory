"""Web RSS/Atom signal collector — no API keys, no LLM, no browser.

Produces RawSignalCandidate only; Phase 2 pipeline handles normalize/validate/dedupe/store.
"""
from __future__ import annotations

import email.utils
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import RawSignalCandidate, SignalSource

# Cap response body to avoid unbounded downloads
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 15
USER_AGENT = "WeeklyMicroProductFactory-RSSCollector/1.0 (+local; research; no-api-key)"

# RSS/Atom namespaces
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _strip_html(text: str) -> str:
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _parse_date(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    # RFC 2822 (RSS)
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, IndexError):
        pass
    # ISO-ish (Atom)
    try:
        cleaned = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def fetch_feed_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[bytes, str | None]:
    """HTTP GET with timeout, size limit, no credentials. Returns (body, content_type)."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-http(s) URL: {url!r}")
    req = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
        method="GET",
    )
    with urlopen(req, timeout=timeout) as resp:  # nosec B310 — http(s) only checked above
        status = getattr(resp, "status", None) or resp.getcode()
        if status and int(status) >= 400:
            raise HTTPError(url, int(status), f"HTTP {status}", resp.headers, None)
        ctype = resp.headers.get("Content-Type")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"response exceeds max_bytes={max_bytes}")
            chunks.append(chunk)
        return b"".join(chunks), ctype


def parse_feed_xml(data: bytes) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom into item dicts: title, summary, link, published."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError(f"malformed XML: {e}") from e

    root_tag = _local(root.tag).lower()
    items: list[dict[str, Any]] = []

    if root_tag == "rss" or root_tag == "rdf":
        channel = None
        for child in root:
            if _local(child.tag).lower() == "channel":
                channel = child
                break
        nodes = channel if channel is not None else root
        for node in nodes:
            if _local(node.tag).lower() != "item":
                continue
            items.append(_parse_rss_item(node))
    elif root_tag == "feed":
        for node in root:
            if _local(node.tag).lower() == "entry":
                items.append(_parse_atom_entry(node))
    else:
        # try find items/entries anywhere
        for node in root.iter():
            loc = _local(node.tag).lower()
            if loc == "item":
                items.append(_parse_rss_item(node))
            elif loc == "entry":
                items.append(_parse_atom_entry(node))

    return items


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts = [el.text or ""]
    for c in el:
        parts.append(_text(c))
        parts.append(c.tail or "")
    return "".join(parts).strip()


def _child(parent: ET.Element, *names: str) -> ET.Element | None:
    want = {n.lower() for n in names}
    for c in parent:
        if _local(c.tag).lower() in want:
            return c
    return None


def _parse_rss_item(node: ET.Element) -> dict[str, Any]:
    title = _text(_child(node, "title"))
    description = _text(_child(node, "description"))
    content = _text(_child(node, "encoded", "content"))
    link = _text(_child(node, "link"))
    pub = _text(_child(node, "pubDate", "date"))
    guid = _text(_child(node, "guid"))
    body = content or description
    return {
        "title": title,
        "summary": body,
        "link": link or guid,
        "published": pub,
    }


def _parse_atom_entry(node: ET.Element) -> dict[str, Any]:
    title = _text(_child(node, "title"))
    summary = _text(_child(node, "summary"))
    content = _text(_child(node, "content"))
    published = _text(_child(node, "published", "updated"))
    link = ""
    for c in node:
        if _local(c.tag).lower() == "link":
            href = c.attrib.get("href") or ""
            rel = c.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
            if not link and href:
                link = href
    body = content or summary
    return {
        "title": title,
        "summary": body,
        "link": link,
        "published": published,
    }


def item_to_candidate(
    item: dict[str, Any],
    *,
    feed_name: str,
    source: str = "other",
) -> RawSignalCandidate | None:
    """Map feed item → candidate. Reject empty/useless text."""
    title = _strip_html(str(item.get("title") or ""))
    summary = _strip_html(str(item.get("summary") or ""))
    link = (item.get("link") or "").strip() or None

    if summary and title and title not in summary:
        raw = f"{title}\n\n{summary}"
    elif summary:
        raw = summary
    elif title:
        raw = title
    else:
        return None

    raw = raw.strip()
    if len(raw) < 20:
        return None

    captured = _parse_date(item.get("published")) or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    contract_source = source if source in (
        "github_issue",
        "x",
        "reddit",
        "trends",
        "review",
        "competitor",
        "manual",
        "other",
    ) else "other"

    return RawSignalCandidate(
        source=contract_source,
        raw_text=raw,
        captured_at=captured,
        created_by="system:web_rss",
        url=link,
        meta={
            "source_detail": feed_name,
            "collector": "rss",
            "title": title or None,
        },
    )


@dataclass
class FeedFetchResult:
    name: str
    url: str
    ok: bool
    candidates: list[RawSignalCandidate] = field(default_factory=list)
    error: str | None = None
    items_seen: int = 0


class WebRssSignalSource(SignalSource):
    """Collect from configured RSS/Atom feeds."""

    name = "web_rss"

    def __init__(
        self,
        feeds: list[dict[str, Any]],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        limit_per_feed: int | None = None,
        fetch_fn=None,
    ):
        self.feeds = feeds
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.limit_per_feed = limit_per_feed
        self._fetch_fn = fetch_fn or fetch_feed_bytes
        self.last_results: list[FeedFetchResult] = []

    def collect(self) -> list[RawSignalCandidate]:
        self.last_results = []
        out: list[RawSignalCandidate] = []
        for feed in self.feeds:
            name = str(feed.get("name") or "unnamed")
            url = str(feed.get("url") or "").strip()
            source = str(feed.get("source") or "other").strip()
            if not url:
                self.last_results.append(
                    FeedFetchResult(name=name, url=url, ok=False, error="missing url")
                )
                continue
            try:
                body, _ctype = self._fetch_fn(
                    url, timeout=self.timeout, max_bytes=self.max_bytes
                )
                items = parse_feed_xml(body)
                if self.limit_per_feed is not None:
                    items = items[: self.limit_per_feed]
                cands: list[RawSignalCandidate] = []
                for it in items:
                    c = item_to_candidate(it, feed_name=name, source=source)
                    if c is not None:
                        cands.append(c)
                self.last_results.append(
                    FeedFetchResult(
                        name=name, url=url, ok=True, candidates=cands, items_seen=len(items)
                    )
                )
                out.extend(cands)
            except Exception as e:  # isolate per-feed failures
                self.last_results.append(
                    FeedFetchResult(name=name, url=url, ok=False, error=str(e))
                )
        return out
