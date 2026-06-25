# Grounding Sync

The Bittensor grounding in this repo is **copied** from `intoops-routines` so the engine runs
independently (the cloud routine has no access to a local `intoops-routines` checkout). Three
files are kept **verbatim** with the source of truth and must be re-synced when that source
changes:

- `references/ground-truth.md`
- `references/fact-patterns.md`
- `references/negative-claim-rules.md`

`references/data-sources.md` is a **ported, trimmed** adaptation (article-pipeline specifics
removed), so it is maintained here by hand, not auto-synced. When the upstream validation
calls or authority tiers change materially, update it manually.

## Why nothing is assumed
`intoops-routines` is the validated source of truth for Bittensor mechanics. These files are
updated there when the protocol changes (e.g. the June 2026 reversion to price-based
emissions). Stale grounding would let the engine post outdated mechanics, which is exactly the
failure mode this project exists to prevent. Re-sync before relying on the grounding after any
upstream change.

## How to re-sync (local dev action)
Run the helper, which copies the three verbatim files from the source repo and reports any
file whose content changed:

```bash
python3 scripts/sync_grounding.py
```

By default it reads from `../IntoOps/intoops-routines/references` relative to this repo's
parent layout; override with `--source`:

```bash
python3 scripts/sync_grounding.py --source "D:/Coding/Bittensor/IntoOps/intoops-routines/references"
```

Use `--check` to verify parity without writing (exits non-zero if any verbatim file is out of
date), useful as a pre-commit sanity check:

```bash
python3 scripts/sync_grounding.py --check
```

After a sync that changes a file, review the diff, run the validator tests
(`python -m pytest scripts/ -v`), and commit the updated grounding.
