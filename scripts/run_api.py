#!/usr/bin/env python3
"""Run Factory API locally — binds 127.0.0.1 only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Backend API (local-only)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("Refusing non-local bind in v0.1. Use 127.0.0.1 only.", file=sys.stderr)
        return 2
    import uvicorn

    uvicorn.run("api.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
