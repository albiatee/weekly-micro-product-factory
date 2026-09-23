"""Tests for RSS/Atom web signal collector — no real network."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.pipeline import ingest_candidates  # noqa: E402
from discovery.sources.web_rss import (  # noqa: E402
    WebRssSignalSource,
    item_to_candidate,
    parse_feed_xml,
)
from discovery.store import list_signals  # noqa: E402

RSS_SAMPLE = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example</title>
    <item>
      <title>I waste hours reconciling invoices manually every week</title>
      <description>Looking for a simple offline way to match payments without a full ERP.</description>
      <link>https://example.com/post/1</link>
      <pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>x</title>
      <description>short</description>
      <link>https://example.com/post/tiny</link>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <entry>
    <title>Need barcode stock counts without monthly SaaS fees</title>
    <summary>Small shop still using paper counts; errors every month-end.</summary>
    <link href="https://example.com/atom/1"/>
    <published>2025-09-01T12:00:00Z</published>
  </entry>
</feed>
"""

MALFORMED = b"<rss><channel><item><title>broken"


def test_parse_rss():
    items = parse_feed_xml(RSS_SAMPLE)
    assert len(items) == 2
    assert "invoice" in items[0]["title"].lower()
    assert items[0]["link"] == "https://example.com/post/1"


def test_parse_atom():
    items = parse_feed_xml(ATOM_SAMPLE)
    assert len(items) == 1
    assert "barcode" in items[0]["title"].lower()
    assert items[0]["link"] == "https://example.com/atom/1"


def test_malformed_xml():
    with pytest.raises(ValueError, match="malformed"):
        parse_feed_xml(MALFORMED)


def test_item_reject_short():
    assert item_to_candidate(
        {"title": "x", "summary": "y", "link": "https://x"}, feed_name="t"
    ) is None


def test_item_provenance():
    c = item_to_candidate(
        {
            "title": "I need offline invoicing for a one-person shop",
            "summary": "Cloud tools are too expensive for a few invoices per month.",
            "link": "https://example.com/a",
            "published": "2025-09-01T12:00:00Z",
        },
        feed_name="demo_feed",
        source="other",
    )
    assert c is not None
    assert c.meta["collector"] == "rss"
    assert c.meta["source_detail"] == "demo_feed"
    assert c.url == "https://example.com/a"
    assert "willing" not in c.raw_text.lower()


def test_http_error_isolation(tmp_path: Path):
    def fake_fetch(url, timeout=15, max_bytes=2_000_000):
        if "bad" in url:
            raise TimeoutError("timed out")
        return RSS_SAMPLE, "application/rss+xml"

    src = WebRssSignalSource(
        [
            {"name": "good", "url": "https://example.com/good.xml", "source": "other"},
            {"name": "bad", "url": "https://example.com/bad.xml", "source": "other"},
        ],
        fetch_fn=fake_fetch,
        limit_per_feed=5,
    )
    cands = src.collect()
    assert any(r.name == "good" and r.ok for r in src.last_results)
    assert any(r.name == "bad" and not r.ok for r in src.last_results)
    assert len(cands) >= 1


def test_empty_feed():
    empty = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>e</title></channel></rss>"""

    def fetch(url, timeout=15, max_bytes=2_000_000):
        return empty, "application/rss+xml"

    src = WebRssSignalSource(
        [{"name": "e", "url": "https://example.com/e.xml", "source": "other"}],
        fetch_fn=fetch,
    )
    assert src.collect() == []


def test_ingest_and_dedupe(tmp_path: Path):
    def fetch(url, timeout=15, max_bytes=2_000_000):
        return RSS_SAMPLE, "application/rss+xml"

    store = tmp_path / "signals"
    store.mkdir()
    src = WebRssSignalSource(
        [{"name": "f", "url": "https://example.com/f.xml", "source": "other"}],
        fetch_fn=fetch,
    )
    cands = src.collect()
    r1 = ingest_candidates(cands, store_root=store, dry_run=False)
    assert len(r1.accepted) >= 1
    r2 = ingest_candidates(src.collect(), store_root=store, dry_run=False)
    assert len(r2.accepted) == 0
    assert len(r2.duplicates) >= 1


def test_dry_run_no_write(tmp_path: Path):
    def fetch(url, timeout=15, max_bytes=2_000_000):
        return RSS_SAMPLE, "application/rss+xml"

    store = tmp_path / "signals"
    store.mkdir()
    src = WebRssSignalSource(
        [{"name": "f", "url": "https://example.com/f.xml", "source": "other"}],
        fetch_fn=fetch,
    )
    r = ingest_candidates(src.collect(), store_root=store, dry_run=True)
    assert len(r.accepted) >= 1
    assert list_signals(store) == {}


def test_limit_per_feed():
    def fetch(url, timeout=15, max_bytes=2_000_000):
        return RSS_SAMPLE, "application/rss+xml"

    src = WebRssSignalSource(
        [{"name": "f", "url": "https://example.com/f.xml", "source": "other"}],
        fetch_fn=fetch,
        limit_per_feed=1,
    )
    assert src.collect()  # at most one useful item from sample
    assert src.last_results[0].items_seen == 1
