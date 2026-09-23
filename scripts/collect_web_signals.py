#!/usr/bin/env python3
"""CLI: collect market Signals from public RSS/Atom feeds (no API keys).

Uses Phase 2: normalize → validate → dedupe → upsert.
Does not create Opportunities.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.pipeline import ingest_candidates  # noqa: E402
from discovery.sources.web_rss import WebRssSignalSource  # noqa: E402


def load_feeds(config_path: Path, source_filter: str | None) -> list[dict]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    feeds = data.get("feeds") or []
    if source_filter:
        feeds = [f for f in feeds if f.get("name") == source_filter]
    return feeds


def main() -> int:
    p = argparse.ArgumentParser(description="Collect Signals from RSS/Atom feeds")
    p.add_argument(
        "--config",
        default=str(ROOT / "config" / "signal_sources.json"),
        help="Path to signal_sources.json",
    )
    p.add_argument("--source", default=None, help="Only this feed name from config")
    p.add_argument("--limit", type=int, default=None, help="Max items per feed")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--store-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(json.dumps({"ok": False, "error": f"config not found: {config_path}"}))
        return 1

    feeds = load_feeds(config_path, args.source)
    if not feeds:
        print(json.dumps({"ok": False, "error": "no feeds matched"}))
        return 1

    collector = WebRssSignalSource(
        feeds,
        timeout=args.timeout,
        limit_per_feed=args.limit,
    )
    candidates = collector.collect()
    store = Path(args.store_dir) if args.store_dir else None
    result = ingest_candidates(candidates, store_root=store, dry_run=args.dry_run)

    feed_report = [
        {
            "name": r.name,
            "url": r.url,
            "ok": r.ok,
            "error": r.error,
            "items_seen": r.items_seen,
            "candidates": len(r.candidates),
        }
        for r in collector.last_results
    ]

    summary = {
        "ok": True,
        "dry_run": args.dry_run,
        "candidates": len(candidates),
        "accepted": len(result.accepted),
        "rejected": len(result.rejected),
        "duplicates": len(result.duplicates),
        "feeds": feed_report,
        "accepted_ids": [x["signal"]["id"] for x in result.accepted],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
