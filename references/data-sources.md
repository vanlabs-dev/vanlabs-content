# Data Sources (Validation)

How to validate a Bittensor claim before a draft relies on it. Ported and trimmed from the
IntoOps `intotao-writer` pipeline: this keeps the validation API calls, the source-priority
order, and the authority tiers. It drops the article-pipeline specifics (Supabase article
tables, snapshot saves, stale-identity stub routing) — this engine writes X drafts, not
articles.

**Rule:** validate only the 1-2 items you intend to engage (the shortlist), and call an API
only when the angle makes a claim that needs it. Protocol-mechanics claims are validated
against `references/ground-truth.md` with **no API call**.

---

## Source 1: TaoSwap (subnet identity, price, emission, owner) — free, no key

Use the detail endpoint. This is the anchor for subnet identity and the current owner.

```bash
curl -s "https://api.taoswap.org/subnets/${NETUID}/" --max-time 15
```

Fields confirmed live (2026-06-25):

- `identity.name`, `identity.url`, `identity.github`, `identity.discord`,
  `identity.description`, `identity.image`
- `owner` — current owner SS58 (who holds the slot right now)
- `price` — current (spot) price in TAO; `moving_price` — the EMA price (the one that drives
  emission share)
- `emission_percent`, `emission_ema_percent` — emission share (current / smoothed)
- `emission_miner_burn` — miner-burn proportion (0..1)
- `emission_chain_buys_percent`, `emission_chain_buys` — chain buys (NOT emission share)
- `active_miners`, `root_in_pool`, `tempo`, `modality`, `market_cap`,
  `registration_cost`, price-evolution fields (`price_evolution_h_24`, `_d_7`, `_d_30`)
- `holders_count`, `hhi_normalized`, `top10_share` — **never surface holder/concentration
  language in a draft** (hard rule); these exist only as on-chain readings.

### Identity confirmation (gates source authority)

Before treating any repo as primary for a subnet claim, this call must confirm WHO holds
the slot and WHAT repo they declare:

- `owner` — the team that holds the slot now.
- `identity.name` — the registered subnet identity.
- `identity.github` — the repo THIS owner declares. Only this repo is eligible to be the
  primary source. A repo URL from anywhere else is not trusted unless it matches this value.

Classify:

- **Valid** — `identity.name` is a real claimed name, or `identity.github` resolves to an
  active repo. Proceed to validate dev/mechanism claims against the repo (Source 2).
- **Parked / stale** — `identity.name` is UNKNOWN / UNCLAIMED / PARKED / FOR SALE / empty
  AND `identity.github` is empty or dead. Do not make subnet-development or mechanism claims
  about it. (Guard: a parked on-chain label but an active declared repo with recent commits
  is still Valid — repo-primary overrides a missing label.)
- **Empty / deregistered** — TaoSwap 404 or no on-chain data. Drop the item.

If TaoSwap errors or times out, identity is unconfirmed: do NOT promote any repo to primary
from memory or cache. Drop the subnet claim or hedge to protocol-level facts only.

---

## Source 2: GitHub API (development activity) — `GITHUB_TOKEN`

Authoritative for any "active / shipping / stalled" development claim. Use
`identity.github` from Source 1.

```bash
REPO_PATH=$(echo "$GITHUB_URL" | sed 's|https://github.com/||')

curl -s "https://api.github.com/repos/${REPO_PATH}" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" --max-time 15
# pushed_at, stargazers_count, forks_count, language, description

curl -s "https://api.github.com/repos/${REPO_PATH}/commits?per_page=10" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" --max-time 15
# date + messages of recent commits
```

- If `pushed_at` is within 45 days, development is NOT inactive: do not write inactivity
  language.
- If `pushed_at` is older than 45 days, an inactivity angle requires the full negative-claim
  process in `references/negative-claim-rules.md` (Desearch counter-evidence, hedged
  wording, two sources) — or drop the angle.
- A 404 means the repo was deleted/made private/moved, NOT that the team is inactive. Do not
  infer abandonment.

---

## Source 3: Desearch (social / counter-evidence) — `DESEARCH_API_KEY`

Already used for gather (`GET /twitter`). For validation, use it as counter-evidence before
any negative claim, and to corroborate a launch/partnership/release mentioned in the target
tweet. The AI search endpoint gives a summarized read:

```bash
curl -s -X POST "https://api.desearch.ai/desearch/ai/search" \
  -H "Authorization: $DESEARCH_API_KEY" \
  -H "Content-Type: application/json" --max-time 60 \
  -d "{
    \"prompt\": \"\\\"${SUBNET_NAME}\\\" OR \\\"SN${NETUID}\\\" Bittensor. Only information specifically about this subnet.\",
    \"tools\": [\"twitter\", \"web\", \"reddit\"],
    \"date_filter\": \"PAST_MONTH\",
    \"streaming\": false,
    \"result_type\": \"LINKS_WITH_FINAL_SUMMARY\",
    \"count\": \"20\"
  }"
```

`date_filter` enum is `PAST_MONTH` (the API rejects the older `PAST_30_DAYS`). Scan the
completion and tweets for recent product activity before writing any inactivity claim.

---

## Source 4 (optional): TaoStats — `TAOSTATS_API_KEY`

Only when an angle depends on registration date or subnet age (e.g. "this subnet just
launched"). Prefer the `taostats-api` skill, which encodes the correct calls and auth. Skip
if the key is not set.

## Source 5 (optional): TAO.app — `TAO_APP_API_KEY`

Only when an angle depends on team members or roadmap. Skip entirely if the key is not set.

```bash
curl -s "https://api.tao.app/api/beta/subnets/about?netuid=${NETUID}" \
  -H "X-API-Key: $TAO_APP_API_KEY" --max-time 15
```

If the about page is empty or sparse, do not fabricate team or roadmap context. Use only
what is explicitly present.

---

## Source Priority for Claims

| Claim type | Primary source | Secondary |
|---|---|---|
| Bittensor protocol mechanics | `references/ground-truth.md` | none (do not override with a repo) |
| Subnet identity / owner | TaoSwap on-chain identity | none |
| Development activity | GitHub API direct | Desearch social signals |
| Price, emission, market data | TaoSwap | none |
| Team members, roadmap | TAO.app about page (if key set) | Desearch web results |
| Product live status | Official website + GitHub | Desearch |
| Registration / subnet age | TaoStats (if key set) | TaoSwap `first_block` |
| Social traction | Desearch | TaoSwap social fields |

---

## Authority Tiers and Conflict Resolution

**Tier 1 — primary, authoritative:**
- The subnet's own main repo README/docs, official website, litepaper, live product surface
  (mechanism and product-status claims).
- On-chain identity, owner, registration state via TaoSwap (who holds the slot).
- `references/ground-truth.md` (Bittensor PROTOCOL mechanics only).

**Tier 2 — secondary, corroborating, presumed stale on divergence:**
- TaoSwap market data, TAO.app, TaoStats, Desearch.

**Resolution rule:** when Tier 1 and Tier 2 diverge, Tier 1 wins and Tier 2 is treated as
stale code lag. Two guards: (1) a repo only "wins" on a claim you actually read from it —
with no primary source, divergence among third parties means hedge, not auto-resolve; (2) a
repo's wording never overrides `ground-truth.md` on protocol mechanics.

For an engagement engine, a conflict you cannot resolve cleanly is a reason to **drop the
item**, not to draft a hedged guess. There is always another trending post.
