# Quality Bar (Editorial Gate)

The model applies this gate. It is judgment, not mechanics; the deterministic checks live in
`scripts/validate_drafts.py`. An item is engaged only if it passes every check here. When in
doubt, drop it — there is always another trending post, and a forced draft is slop.

## Step 0: Bittensor-relevance gate (mandatory, runs first)
Trending queries return off-topic crypto. A live test of `Bittensor OR ... OR emissions`
returned a Canton Coin tweet (a different chain). Before anything else, confirm each
candidate is genuinely about Bittensor:

- A real Bittensor signal is present: Bittensor itself, TAO as the Bittensor token, dTAO, a
  named subnet, `SNxx`, `netuid`, or a clearly Bittensor-specific mechanic.
- "Emissions", "subnet", "validators", "staking", "TAO" alone are NOT enough — every chain
  uses these words. Canton, Celestia, Cosmos, etc. are not Bittensor.
- When unsure, drop. Never engage a post you cannot confirm is about Bittensor.

## What counts as significant (INCLUDE)
- Protocol or governance developments (emissions model, deregistration, halving, conviction,
  root, chain upgrades) with real consequences.
- A subnet launch, mainnet/testnet milestone, or substantive release backed by a verifiable
  source (repo commit, official post).
- A claim, debate, or analysis where @vaNlabs can add a grounded, second-order point a
  generic account could not.
- A widely-shared misconception about Bittensor mechanics that a respectful, sourced
  correction would genuinely help.

## What to exclude (SKIP)
- Price, trading, token-target, or "is $TAO going to X" speculation.
- Engagement bait, vague hype ("Bittensor is the future"), and influencer noise with no
  substance to engage.
- Unsourced rumor or a single anonymous claim with no corroboration.
- Pure shilling of a subnet's alpha with no product or mechanism substance.
- Anything you cannot ground: if the angle needs a Bittensor claim you cannot validate, skip.
- Your own posts (@vaNlabs, @IntoTAO) and retweets.

## Source credibility (for the target tweet)
- Tier 1: the primary actor's own account (a subnet's official account for its own news), the
  Bittensor core/foundation accounts, named researchers, official repos/docs.
- Tier 2: established crypto/AI press and reputable named accounts.
- Tier 3: credible community accounts. Engage only with corroboration or a primary link.
- Reject: anonymous or unverifiable accounts as the sole basis.

Prefer engaging an authoritative original post over a bigger account's hot take. A subnet's
own announcement with modest engagement outranks a large account paraphrasing it.

## Deduplication
- Within a run: one story equals one engagement. Do not draft two posts about the same
  development.
- Across runs: a target tweet already in `vanlabs_seen_targets` (last 7 days) is excluded. A
  genuinely new tweet on an ongoing story is still eligible, but do not repeat the same point
  you already made (the `topic` field is the reminder).

## Volume
Up to 2 drafts per run. Often 1. Zero when nothing clears the bar — send the quiet note, not
padding. Quality and a real, grounded point beat cadence every time.

## Per-item checklist (drop the item if any fail)
1. Confirmed about Bittensor (Step 0).
2. Significant and engageable, not bait, hype, or price talk.
3. A credible, authoritative target tweet exists (original post, not a retweet or pure reply,
   not your own account).
4. Every Bittensor claim the draft would make is validated (ground-truth or live data).
5. No uncorroborated negative claim (see `references/negative-claim-rules.md`).
6. Not a duplicate (within run or across runs).
7. The draft passes the two judgment tests in `references/brand-voice.md` (concrete anchor;
   "would @vaNlabs actually send this?").

After drafting, re-read each draft once as a skeptical editor and cut anything that would not
survive scrutiny or that reads as generic AI.
