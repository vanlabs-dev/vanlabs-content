# Bittensor Engagement Engine — Design

Date: 2026-06-25
Repo: `vanlabs-content`
Status: Drafted for review

## Goal

A Claude routine that runs **2-3 times a day**, finds **trending Bittensor content** on
X, and produces up to **two copyable drafts** (each a **quote post** or a **reply**) in
the `@vaNlabs` voice. Drafts are delivered to Telegram for **manual** posting. The engine
reuses the proven shape of `ai-morning-briefing` (routine + `references/` + one
zero-dependency deterministic gate + pytest), and adds a **Bittensor validation layer**
ported from `intoops-routines`.

Two principles override everything:

1. **Nothing about Bittensor is assumed.** Every Bittensor factual claim a draft relies on
   must trace to `references/ground-truth.md` (protocol mechanics) or to live data fetched
   in the run (subnet identity/dev/market). A claim that cannot be validated is not made.
   If the only viable angle needs an unvalidated claim, the item is dropped.
2. **The content must not read as AI.** Quality and a human, expert voice beat cadence.
   Producing **zero** drafts in a window is a valid, expected outcome.

## Scope and key decisions (confirmed with the user)

- **Content scope:** ecosystem-wide **and** subnet-specific, ranked together by
  significance (not category).
- **Quote vs reply:** the model decides per item by genuine fit ("dynamic"), not random.
- **Output:** standalone Telegram delivery of copy-paste drafts. **No auto-posting.**
- **Two gates:** the deterministic `validate_drafts.py` (blocks malformed/sloppy/wrong
  drafts from reaching Telegram) and the **human** (decides whether any surfaced draft is
  posted to X).
- **Cross-run dedup:** a minimal Supabase table (`vanlabs_seen_targets`).
- **Lookback:** ~12h per run; up to 2 drafts/run, often 1, 0 when nothing clears the bar.
- **Scheduling:** Claude cloud schedule (scheduled cloud agent linked to this repo).
- **Self-contained:** the Bittensor grounding is copied into this repo so it runs with no
  runtime dependency on `intoops-routines`.

## Validated facts (live smoke tests, 2026-06-25)

These were confirmed against the live APIs so the design is not built on assumptions.

- **Desearch `GET https://api.desearch.ai/twitter`**, header `Authorization: <key>` (no
  `Bearer`), returns a **flat JSON list** of tweet objects. Confirmed fields used by this
  design:
  - tweet: `id`, `url`, `text`, `created_at` (e.g. `Wed Jun 24 20:00:01 +0000 2026`),
    `like_count`, `view_count`, `retweet_count`, `reply_count`, `quote_count`,
    `is_retweet`, `is_quote_tweet`, `in_reply_to_status_id` (null when not a reply),
    `conversation_id`, `lang`.
  - `user`: `username`, `name`, `verified`, `is_blue_verified`, `followers_count`,
    `description`.
  - `created_at` enables the **client-side 12h recency filter** (the date params are
    day-granular). `id` is the canonical key for dedup.
- **Relevance is not guaranteed.** The query `Bittensor OR dTAO OR subnet emissions`
  returned a **Canton Coin** tweet (a different chain) as the top hit. A **Bittensor
  relevance gate** is therefore mandatory; query hits cannot be assumed on-topic.
- **TaoSwap `GET https://api.taoswap.org/subnets/{netuid}/`** (free, no key) returns, among
  others: `identity.{name,url,github,image,discord,description}`, `owner` (SS58), `price`,
  `moving_price` (the EMA price), `emission_percent`, `emission_ema_percent`,
  `emission_miner_burn`, `emission_chain_buys_percent`, `active_miners`, `root_in_pool`,
  `tempo`, `modality`, `market_cap`, `holders_count` (**never surfaced in prose**),
  `registration_cost`. `GET /network-stats/` (free) returns `date`, `subnet_reg_cost_tao`.
- **Supabase REST** works with the service-role key. `vanlabs_seen_targets` does **not**
  exist yet (PostgREST `PGRST205`). The project is the **shared IntoOps Supabase** (it
  suggested `intoops_review_comments`), so our table uses the `vanlabs_` prefix to stay
  namespaced.

## Architecture and repo layout

```
vanlabs-content/
  ROUTINE.md                  # the pipeline (source of truth the routine executes)
  README.md                   # how it fits together, env, how to run the gate
  .gitignore                  # ignores .env (already in place)
  .env                        # local-only secrets (gitignored; never in the repo)
  references/
    brand-voice.md            # @vaNlabs X-draft voice, Bittensor-native few-shot (anti-slop)
    quality-bar.md            # editorial gate: significance, source tiers, dedup, relevance
    ground-truth.md           # COPIED VERBATIM from intoops-routines (protocol canon)
    fact-patterns.md          # COPIED VERBATIM (factual error patterns)
    negative-claim-rules.md   # COPIED VERBATIM (no uncorroborated negative claims)
    data-sources.md           # PORTED + TRIMMED (validation API calls + authority tiers)
    telegram-format.md        # the engage-message template + send call
    grounding-sync.md         # how to re-sync the copied grounding when intoops changes
  scripts/
    validate_drafts.py        # deterministic gate (zero-dep): format + voice + Bittensor lint
    test_validate_drafts.py   # pytest suite (dev-only)
    sync_grounding.py         # local dev helper: re-copy the 3 verbatim grounding files
  examples/
    sample-message.html       # a valid engage message; doubles as a validator fixture
  requirements-dev.txt        # pytest (dev only)
  docs/superpowers/specs/2026-06-25-bittensor-engagement-engine-design.md
```

Runtime is **zero third-party Python deps** (`validate_drafts.py` is stdlib only). The
routine itself uses bash + curl. `pytest` is dev-only.

## The pipeline (`ROUTINE.md`)

### Step 0 — Load grounding
Read, in order: `references/quality-bar.md`, `references/brand-voice.md`,
`references/ground-truth.md`, `references/fact-patterns.md`,
`references/negative-claim-rules.md`, `references/data-sources.md`,
`references/telegram-format.md`. These govern everything below; on any conflict, the hard
rules (no em dash, no holder language, no fabricated metrics, no uncorroborated negatives,
source attribution) win.

### Step 1 — Gather trending Bittensor content
Run a small set of Desearch `/twitter` queries (`sort=Top`, `lang=en`, `count` ~15-20).
Tune `min_likes` per sweep — authority matters more than raw reach for this niche. Two
sweeps:

- **Ecosystem** (`min_likes` ~10): anchored on unambiguous terms, e.g.
  `Bittensor OR "$TAO" OR dTAO OR "TAO subnet" OR netuid`.
- **Subnet sweep** (`min_likes` ~2, so an authoritative subnet announcement with modest
  engagement still surfaces): e.g.
  `Bittensor (subnet OR SN OR netuid) (launch OR release OR mainnet OR shipped OR update)`.

Set the date params to cover the run's lookback (today, plus yesterday for the first run
of the day). If a query errors or is empty, note it and continue. Never fabricate to fill
space.

### Step 2 — Filter, rank, select targets
1. **Bittensor-relevance gate (mandatory):** drop any hit not genuinely about Bittensor
   (the live test returned Canton Coin under "emissions"). Require a real Bittensor signal
   (Bittensor / TAO-as-Bittensor / a named subnet / `SNxx` / `netuid` in the
   Bittensor sense). When unsure, drop.
2. **Recency:** prefer tweets with `created_at` within ~12h.
3. **Dedup:** exclude any `id` already in `vanlabs_seen_targets` within the window
   (Step 7 / dedup section).
4. **Rank by significance** per `quality-bar.md` across both categories together. Rank on
   authority and **groundability** (can we validate and add a real point?), not raw reach
   alone, so a high-authority subnet announcement is not buried under a big-account hot
   take. Soft preference for a range across the two drafts (e.g. one ecosystem, one
   subnet) when both clear the bar — never a quota.
5. **Select the target tweet** per chosen item from that story's hits: exclude
   `is_retweet` and pure replies (`in_reply_to_status_id` set); exclude tweets authored by
   the engine's own accounts (`@vaNlabs`, `@IntoTAO` — never engage your own posts); prefer
   the primary actor's own post; else rank by `is_blue_verified` / `verified`, then
   `followers_count`; break ties by `view_count` then `like_count`. Use `url` as the target
   link and `user.username` as the @handle. If an item's only tweets are low-credibility,
   skip it and use the next-best item.

### Step 3 — Validate the shortlist (the "nothing assumed" core)
Run **only on the 1-2 items we intend to engage** (not the whole gather set). For each:

1. **Enumerate every Bittensor factual claim** the draft would rely on (including any
   claim made in the target tweet that our angle would affirm or correct).
2. **Route by authority tier** (`data-sources.md`):
   - **Protocol mechanics** (emissions, dTAO, staking, deregistration, halving, conviction,
     chain buys vs emission share, miner burn) → validate against `ground-truth.md`. No API
     call needed.
   - **Subnet identity / development / market** → live fetch, conditional on the angle:
     TaoSwap identity (`identity.github`, `owner`, price/emission) → GitHub API (dev
     activity, authenticated with `GITHUB_TOKEN`) → Desearch (social counter-evidence) →
     optional TaoStats (registration/age, via the `taostats-api` skill) / optional TAO.app
     (team/roadmap, only if `TAO_APP_API_KEY` is set).
3. **Drop rule:** a claim that cannot be validated is **not made**. If the only angle needs
   it, drop the item and move to the next-best.
4. **Negative-claim gate** (`negative-claim-rules.md`): never call a subnet/project
   inactive, abandoned, or declining without two independent sources. Otherwise rephrase to
   a hedged, sourced statement or drop. Single-source negatives are dropped.
5. **Do not amplify a false claim.** If the target tweet asserts something `ground-truth.md`
   contradicts, the angle becomes a **respectful, sourced correction/clarification**
   (protocol facts are not negative claims about a project), or the item is dropped. No
   snark, no dunking (`BRAIN` governance: brand integrity beats engagement).

### Step 4 — Draft
The model picks **quote vs reply by fit** and writes each draft per `brand-voice.md`:

- **Reply** when there is a sharp, specific point, correction, or a genuine question
  directed at the author. Lives in-thread; must earn it (not reply-guy filler).
- **Quote** when there is a standalone angle worth broadcasting to your own audience; adds
  a distinct layer on top of the quoted post.

Drafts are **URL-free commentary** (the quote attaches the card; the reply lives
in-thread). Bittensor claims appear only as validated in Step 3. Run the `fact-patterns.md`
self-check and the anti-slop pre-emit checklist before emitting.

### Step 5 — Deterministic gate
Assemble the Telegram message per `telegram-format.md`, write it to `message.html`, and run:

```bash
python3 scripts/validate_drafts.py message.html
```

Proceed only on exit 0. On exit 1, read the errors, fix, and re-run. Resolve warnings
(rewrite) unless clearly spurious. Details in the validator section.

### Step 6 — Send to Telegram
Build the JSON payload with a real encoder (never hand-interpolate) and POST to
`sendMessage` with `parse_mode: HTML` and link previews disabled. Confirm `"ok":true`. On a
quiet window (zero drafts), send the short quiet note (see template).

### Step 7 — Record dedup
Upsert the engaged target tweet `id`s into `vanlabs_seen_targets` (see dedup section).
Recorded at draft-time so the same trending tweet is not re-surfaced every run.

No run is written to a database (standalone Telegram model). If the dedup read or write
fails, do not abort: proceed and note "dedup unavailable" in the run output (duplicates
become possible until it recovers).

## The anti-AI-slop quality engine

The strategic core: **the validation layer is the source of content that cannot sound like
AI.** Generic AI cannot correctly separate chain buys from emission share, or push back on
"SN-X has 0% emission buy, it's dying" with the real mechanic. Only the grounding makes
that post possible. The highest-value outputs are the **skeptic's-challenge** and
**pointed-question** registers aimed at overhyped trending claims, grounded in
`ground-truth.md` — at once the most on-brand, most useful, and least AI-sounding.

Three layers (judgment separated from mechanics, as IntoOps does):

### Layer 1 — Voice spec (`brand-voice.md`), few-shot-forward
- **Invariants:** one idea per post; concrete over abstract; evidence-led; skeptical of
  hype; plain declaratives; hyphens not em dashes; no emoji, no threads, no hashtag
  decoration, no engagement-bait openers.
- **Rotating registers** (pick one per draft by fit): analyst take, builder's implication,
  skeptic's challenge, pointed question, thesis-connect (agents / verification / open
  source / Bittensor — used sparingly, only when it genuinely fits).
- **Bittensor-native few-shot is the centerpiece.** Worked examples (trending post →
  quote/reply) in the `@vaNlabs` cadence, spanning registers and both formats, each using
  correct mechanics. Includes **paired slop-vs-signal examples** (the generic-AI version
  next to the `@vaNlabs` version) because contrast teaches voice better than rules. Every
  example must itself pass `ground-truth.md` and the gate.
- **Pre-emit self-check** mirroring the gate, plus two judgment tests every draft must pass
  or be dropped: (a) **concrete anchor** — a specific number, mechanism, or named thing, or
  a genuinely sharp question (vibes-only → drop); (b) **"would `@vaNlabs` actually send
  this?"** — summaries of the quoted post, diplomatic mush, and generic enthusiasm → drop.

### Layer 2 — Deterministic lint (`validate_drafts.py`), high precision
Catches the mechanical tells with low false-positive risk (see validator section): emoji,
em/en dash, thread openers, a tight high-signal **slop blocklist**, and the **Bittensor
factual-error lint** ported from `fact-patterns.md`. Subtle tells (rhythm, both-sides mush,
restating the quoted post) are deliberately left to Layer 1 and the human gate, not regex.

### Layer 3 — Model self-check + the human gate
The model resolves all warnings before sending; the human decides whether any clean draft
is actually posted to X. The freedom to produce **zero** is first-class: forcing two drafts
against weak targets manufactures the slop we are avoiding.

## Brand voice (`references/brand-voice.md`)

Adapts `ai-morning-briefing/references/brand-voice.md` (the `@vaNlabs` X-draft voice) with
Bittensor-native few-shot and mechanics. `@vaNlabs`: founder of `@IntoTAO`, Bittensor
investor/miner/builder, rigor-first; terse, concrete, data-led, skeptical of hype, values
verification and provenance. The article-voice from IntoOps `BRAIN.md` ("professional but
relaxed") is **not** used here; this is X-native.

## Deterministic gate (`scripts/validate_drafts.py`)

Derived from `ai-morning-briefing/scripts/validate_digest.py`: reuse the HTML/entity
parser, `utf16_len`, `visible_text`, `extract_drafts` (drafts = `<pre>` blocks; target link
= last `<a href>` in the label paragraph above), and the `validate(text) -> (errors,
warnings)` shape with a pytest-driven pure function. **Remove** the news-digest item logic
(`extract_items`, the 6-10 items rule) — this engine has no digest body. **Add** the
Bittensor lint and the expanded slop blocklist. Scope all content checks to draft text
inside `<pre>` so message chrome (header, "Grounded on" lines) is untouched.

### Errors (block the send; the model must fix and re-run)
- Unsupported/unbalanced HTML tags; unescaped `&` `<` `>`; an `<a>` without an http(s)
  href (Telegram-breaking).
- Visible length over 4096 (measured on `visible_text`).
- Draft count outside range. The validator detects a **quiet window** by a marker phrase
  in the message (`"Quiet window"`, mirroring `ai-morning-briefing`'s `"quiet day"`
  detection): when the marker is present, exactly 0 drafts are required (a `<pre>` present
  alongside the quiet marker is an error); when it is absent, 1-2 drafts are required
  (0 or >2 is an error).
- A draft with no target link in its label, or a target that is not an
  `x.com`/`twitter.com` status link.
- An em dash (U+2014) or horizontal bar (U+2015) **anywhere in the message** (the brand's
  global no-em-dash rule, not only inside drafts).
- In any draft (inside `<pre>`): emoji; a thread opener (`^\s*\d+/`).
- **Holder-count language** anywhere in a draft ("holders", "holder count",
  concentration-by-holders).
- **Bittensor factual-error lint** (ported from `fact-patterns.md`), high-confidence and
  **negation-aware** (suppressed when preceded within ~3 words by not/n't/never/no):
  single-token emissions ("emissions paid in TAO", "emissions are only alpha", etc.);
  "7,200 TAO"/"7200 TAO" as current (not preceded by from/dropped); Taoflow / flow-based as
  the **current** model; "validators mine/mining"; "TAO burned when staking"; "root
  validators vote on emissions"; locking/conviction "boosts/increases emissions".

### Warnings (printed; the model resolves unless clearly spurious)
- A draft over 280 chars; an en dash (U+2013); a URL inside the copy block.
- A high-signal **slop** phrase present (kept tight to avoid false positives): "game
  changer", "this changes everything", "let that sink in", "the future is here",
  "Hot take:", "Unpopular opinion:", "not just X, it's Y", "buckle up", "we're so back",
  "delve", "game-changing/revolutionary/groundbreaking/cutting-edge", "massive/insane" as
  filler, rhetorical-question openers.
- Lower-confidence factual patterns that need context: chain-buys-as-risk ("0% emission
  buy" as bad), "all subnets do/are", "you earn by staking TAO".

The gate enforces format/voice/known-wrong phrasings. It is **not** a truth detector;
live-data validation (Step 3) and the human gate cover semantic correctness. This division
mirrors IntoOps (`sanitize_article.py` + model self-check).

## Telegram message format (`references/telegram-format.md`)

`parse_mode: HTML`, allowed tags only (`<b> <i> <a> <pre>` etc.), dynamic text escaped
(`&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`). Active window:

```
🛰️ <b>Bittensor - engage</b>
<i>{Weekday, Month DD, YYYY · HH:MM TZ}</i>

Quote post for <a href="TWEET_URL">@author</a>:
<pre>One to three sentences of original commentary in the @vaNlabs voice.</pre>
<i>Grounded on: {one-line validation basis}</i>

Reply to <a href="TWEET_URL">@author</a>:
<pre>A shorter, pointed reply or a genuine question.</pre>
<i>Grounded on: {one-line validation basis}</i>

<i>Manual post only. Validated, you decide.</i>
```

Quiet window:

```
🛰️ <b>Bittensor - engage</b>
<i>{Weekday, Month DD, YYYY · HH:MM TZ}</i>

Quiet window. Nothing cleared the bar.
```

No em dash appears anywhere in the message; the gate enforces no em dash across the whole
message (not only inside drafts), per the brand's global no-em-dash rule.

`TWEET_URL` is an `x.com`/`twitter.com` status link. The label line ("Quote post for" /
"Reply to") sets the format and carries the target link; the `<pre>` is the tap-to-copy
draft; the italic "Grounded on" line (outside the `<pre>`) gives the human gate the
validation basis without polluting the copy block. The send uses a python-built JSON
payload then `curl` to `sendMessage`, confirming `"ok":true` (per the format reference).

## Cross-run dedup (Supabase)

One-time DDL (run in the Supabase SQL editor or via the Supabase MCP; PostgREST cannot do
DDL). Lives in the shared IntoOps project under the `vanlabs_` prefix:

```sql
create table if not exists vanlabs_seen_targets (
  tweet_id   text primary key,      -- canonical X status id (Desearch tweet.id)
  tweet_url  text not null,
  author     text,                  -- @handle engaged
  topic      text,                  -- short label of the item (story-level variety)
  format     text,                  -- 'quote' | 'reply'
  run_at     timestamptz not null default now()
);
```

- **Read (Step 2):**
  `GET {SUPABASE_URL}/rest/v1/vanlabs_seen_targets?select=tweet_id&run_at=gte.{now-7d}`
  with `apikey` + `Authorization: Bearer` (service role). Exclude matching `id`s.
- **Write (Step 7):** `POST .../vanlabs_seen_targets` with
  `Prefer: resolution=merge-duplicates` (upsert) for each engaged target.
- **Window:** 7 days. Dedup is at the **tweet** level, so a genuinely new tweet about an
  ongoing story is still eligible; `topic` lets the model avoid repeating the same point.
- **Resilience:** a failed read/write never aborts the run (note "dedup unavailable").

## Files copied from `intoops-routines`

Verbatim copies (kept current with `scripts/sync_grounding.py`; see `grounding-sync.md`):
- `references/ground-truth.md`
- `references/fact-patterns.md`
- `references/negative-claim-rules.md`

Ported and trimmed (drop the article-pipeline specifics — Supabase article tables,
`github_snapshots` fallback wording, save payloads — keep the validation API recipes,
Source Priority for Claims, and Authority Tiers / Conflict Resolution):
- `references/data-sources.md`

After this, the engine has **no runtime dependency** on `intoops-routines`. The sync helper
re-copies the three verbatim files from a configurable local path and reports diffs; it is a
local dev action (the cloud routine cannot see the local `intoops-routines` checkout).

## Environment variables

All secrets are provisioned in the **Claude routine (cloud schedule) environment**; the
routine reads the repo, not `.env`. The local `.env` is gitignored and holds only a subset
for local development and gate/smoke testing — it does not need to be complete, and Telegram
and TAO.app keys are not required locally.

| Variable | Purpose |
|---|---|
| `DESEARCH_API_KEY` | Desearch `/twitter` (Authorization header, no Bearer) |
| `SUPABASE_URL` | Supabase REST base (dedup) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase REST auth (dedup) |
| `GITHUB_TOKEN` | GitHub API for dev-activity validation |
| `TELEGRAM_BOT_TOKEN` | `sendMessage` |
| `TELEGRAM_CHAT_ID` | destination chat/channel |
| `TAOSTATS_API_KEY` | optional: registration/age validation (via the `taostats-api` skill) |
| `TAO_APP_API_KEY` | optional: team/roadmap validation via TAO.app |

All of the above are set on the routine. The local `.env` currently includes
`DESEARCH_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GITHUB_TOKEN`, and
`TAOSTATS_API_KEY`, which is enough to run the gate tests and live smoke checks locally.

## Scheduling

A Claude cloud schedule linked to `vanlabs-dev/vanlabs-content`, firing ~3x/day (e.g.
08:00 / 14:00 / 20:00 in the chosen TZ), minimal prompt: "Read `ROUTINE.md` and everything
in `references/`, execute the pipeline exactly, proceed autonomously." Secrets live in the
schedule environment. The `vanlabs_seen_targets` table must exist before the first run. The
schedule is created by the user (the `/schedule` skill) at deploy time, not by this spec.

## Testing

- `pytest` suite for `validate_drafts.py`: passes on `examples/sample-message.html`; fails
  on each new error (emoji, em dash, 3 drafts, draft without target link, non-x.com target,
  holder language, each high-confidence factual pattern); warns (not fails) on a 300-char
  draft, en dash, in-draft URL, and each slop phrase; confirms negation-awareness (a
  grounded correction containing "validators do not mine" does **not** error).
- The sample fixture is a valid two-draft Bittensor engage message that passes the gate.
- A live Desearch smoke run on first deploy to confirm query tuning (min_likes, window)
  yields on-topic Bittensor results after the relevance gate.

## Out of scope

- Auto-posting to X (human copies and posts — explicit).
- A run database / `intoops_runs` logging (standalone Telegram model).
- The article-writer machinery: registration/reg-cost tracking (Step 0), `subnet_reg_cost`,
  article tables, publish/archive logic.
- Changing IntoOps or `ai-morning-briefing`.

## Success criteria

- 2-3x/day the routine sends a Telegram message: 0-2 Bittensor drafts (quote/reply chosen
  by fit, varying across runs), each tap-to-copy with a working target link to an
  authoritative original tweet, and a one-line "Grounded on" basis.
- Every Bittensor claim in a draft traces to `ground-truth.md` or live data; unvalidatable
  angles are dropped; no uncorroborated negative claims.
- `python scripts/validate_drafts.py message.html` exits 1 on any defined error and 0 on a
  clean message, with 280-char / en-dash / slop issues surfacing as warnings.
- Drafts read as `@vaNlabs` — a rigorous human voice — not as generic AI output.
- The same trending tweet is not surfaced twice within the dedup window.
```