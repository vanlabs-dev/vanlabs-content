#!/usr/bin/env python3
"""Re-sync the verbatim Bittensor grounding from intoops-routines.

Three reference files are kept byte-for-byte identical to the source of truth in
`intoops-routines/references` so this repo runs independently while staying current:

  - ground-truth.md
  - fact-patterns.md
  - negative-claim-rules.md

`data-sources.md` is a ported, trimmed adaptation and is NOT synced here (maintain by hand).

Usage:
  python3 scripts/sync_grounding.py                 # copy from the default source path
  python3 scripts/sync_grounding.py --source PATH   # copy from a custom references dir
  python3 scripts/sync_grounding.py --check         # verify parity only (no writes)

`--check` exits non-zero if any verbatim file is out of date. This is a local dev action;
the cloud routine never runs it (it cannot see a local intoops-routines checkout).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

VERBATIM = ["ground-truth.md", "fact-patterns.md", "negative-claim-rules.md"]

DEFAULT_SOURCE = Path(__file__).resolve().parent.parent.parent / "IntoOps" / "intoops-routines" / "references"
DEST = Path(__file__).resolve().parent.parent / "references"


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync verbatim Bittensor grounding files.")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE),
                    help="Path to intoops-routines/references (default: sibling repo layout)")
    ap.add_argument("--check", action="store_true",
                    help="Verify parity without writing; exit 1 if any file differs")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        print(f"ERROR: source dir not found: {source}")
        return 2

    changed = []
    missing = []
    for name in VERBATIM:
        src = source / name
        dst = DEST / name
        if not src.is_file():
            missing.append(name)
            continue
        src_bytes = src.read_bytes()
        dst_bytes = dst.read_bytes() if dst.is_file() else None
        if src_bytes == dst_bytes:
            continue
        changed.append(name)
        if not args.check:
            dst.write_bytes(src_bytes)

    if missing:
        print("MISSING in source: " + ", ".join(missing))

    if args.check:
        if changed or missing:
            print("OUT OF DATE: " + ", ".join(changed + missing))
            return 1
        print("OK: all verbatim grounding files are in sync.")
        return 0

    if changed:
        print("UPDATED: " + ", ".join(changed))
        print("Review the diff, run `python -m pytest scripts/ -v`, then commit.")
    else:
        print("OK: nothing to update; grounding already current.")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
