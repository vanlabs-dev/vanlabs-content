# vanlabs-content - Bittensor Engagement Engine

An autonomous Claude routine that runs a few times a day, finds **trending Bittensor
content** on X (via Desearch), and produces up to two copyable drafts (each a **quote post**
or a **reply**) in the `@vaNlabs` voice. Drafts are validated against Bittensor ground truth
and a deterministic gate, then delivered to Telegram for **manual** posting. Nothing is
auto-posted.

Two principles drive the whole design:

1. **Nothing about Bittensor is assumed.** Every Bittensor claim a draft makes traces to
   `references/ground-truth.md` or to live data fetched in the run. Unvalidatable angles are
   dropped.
2. **The content must not read as AI.** The grounding is what makes the content un-fakeable
   by a generic account; producing zero drafts beats posting slop.

This repo reuses the shape of `ai-morning-briefing` (routine + `references/` + a
zero-dependency validator + pytest) and adds a Bittensor validation layer copied from
`intoops-routines`, so it runs independently.

## How it fits together

| File | Role |
|---|---|
| `ROUTINE.md` | The pipeline the routine executes. Source of truth. |
| `references/quality-bar.md` | Editorial gate: relevance, significance, source tiers, dedup. |
| `references/brand-voice.md` | The `@vaNlabs` X voice + anti-slop few-shot (slop vs signal). |
| `references/ground-truth.md` | Bittensor protocol canon. Verbatim from intoops-routines. |
| `references/fact-patterns.md` | Factual error patterns. Verbatim from intoops-routines. |
| `references/negative-claim-rules.md` | No uncorroborated negative claims. Verbatim. |
| `references/data-sources.md` | Validation API calls + authority tiers. Ported/trimmed. |
| `references/telegram-format.md` | The message template, escaping, and send call. |
| `references/grounding-sync.md` | How to re-sync the verbatim grounding. |
| `scripts/validate_drafts.py` | Deterministic pre-send gate. Non-zero exit blocks the send. |
| `scripts/sync_grounding.py` | Local helper to re-copy the verbatim grounding. |
| `scripts/schema.sql` | One-time DDL for the dedup table. |
| `examples/sample-message.html` | A valid reference message; doubles as a validator fixture. |

## Pipeline

`ROUTINE.md`: gather (2 Desearch sweeps) -> filter/rank/select target -> **validate the
shortlist** -> draft (quote or reply, chosen by fit) -> deterministic gate -> send to
Telegram -> record dedup. See the file for the exact calls.

## Environment variables

All secrets are set on the **Claude routine (cloud schedule) environment**; the routine
reads the repo, not `.env`. The local `.env` is gitignored and holds only a subset for
running the gate tests and live smoke checks.

| Variable | Purpose |
|---|---|
| `DESEARCH_API_KEY` | Desearch `/twitter` (Authorization header, no Bearer) |
| `SB_URL` | Supabase REST base (dedup). Routine convention; falls back to `SUPABASE_URL`. |
| `SB_KEY` | Supabase service-role key (dedup). Routine convention; falls back to `SUPABASE_SERVICE_ROLE_KEY`. |
| `GITHUB_TOKEN` | GitHub API for dev-activity validation |
| `TELEGRAM_BOT_TOKEN` | `sendMessage` |
| `TELEGRAM_CHAT_ID` | destination chat/channel |
| `TAOSTATS_API_KEY` | optional: registration/age validation (via the `taostats-api` skill) |
| `TAO_APP_API_KEY` | optional: team/roadmap validation via TAO.app |

## Setup

One-time: create the dedup table (PostgREST cannot run DDL). Apply `scripts/schema.sql` via
the Supabase SQL editor or the Supabase MCP. It is additive and namespaced (`vanlabs_`); it
lives in the shared IntoOps Supabase project.

## The quality gate

`scripts/validate_drafts.py` is the hard gate. It separates **errors** (block the send) from
**warnings** (printed, do not block):

- Errors: unsupported/unbalanced HTML, unescaped `&` `<` `>`, an `<a>` without an http(s)
  href, over the 4096 visible-char limit, leftover `{placeholder}` tokens, draft count out
  of range (1-2 active / 0 quiet), a draft with no/invalid `x.com` target, an em dash
  anywhere, a draft with emoji or a thread opener or holder-count language, and a
  high-confidence wrong Bittensor claim (negation-aware).
- Warnings: a draft over 280 chars, an en dash, a URL inside the copy block, a high-signal
  slop phrase, and lower-confidence factual patterns that need context.

The gate enforces format, voice, and known-wrong phrasings. It is **not** a truth detector;
live-data validation (the routine) and the human (who decides whether to post) cover
semantic correctness.

```bash
python3 scripts/validate_drafts.py examples/sample-message.html
python3 scripts/validate_drafts.py - < my-message.html   # reads stdin too
```

## Testing

```bash
python -m pip install -r requirements-dev.txt
python -m pytest scripts/ -v
```

## Keeping the grounding current

The three verbatim grounding files are the validated source of truth in `intoops-routines`.
Re-sync when that changes:

```bash
python3 scripts/sync_grounding.py            # copy updates in
python3 scripts/sync_grounding.py --check    # verify parity (non-zero if stale)
```

`data-sources.md` is a trimmed adaptation, maintained here by hand.

## Scheduling

A Claude cloud schedule linked to this repo, firing ~3x/day, with a minimal prompt: read
`ROUTINE.md` and everything in `references/`, execute the pipeline, proceed autonomously.
Secrets live in the schedule environment. The dedup table must exist before the first run.
