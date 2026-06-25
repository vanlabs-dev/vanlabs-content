import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_drafts as vd  # noqa: E402

HEADER = "\U0001f6f0️ <b>Bittensor - engage</b>\n<i>Thursday, June 25, 2026</i>\n\n"
FOOTER = "\n<i>Manual post only. Validated, you decide.</i>\n"

QUOTE = (
    'Quote post for <a href="https://x.com/opentensor/status/1000000000000000001">@opentensor</a>:\n'
    "<pre>Emission share is price-based again: root_prop x EMA price x (1 - miner_burn). "
    "Net flows are a demand signal now, not the lever.</pre>\n"
    "<i>Grounded on: emission model (ground-truth).</i>\n"
)
REPLY = (
    '\nReply to <a href="https://x.com/someminer/status/1000000000000000002">@someminer</a>:\n'
    "<pre>Chain buys and emission share are different metrics. What is the actual emission share here?</pre>\n"
    "<i>Grounded on: chain buys vs emission share (ground-truth).</i>\n"
)


def msg(*blocks):
    return HEADER + "".join(blocks) + FOOTER


def draft(pre, label='Quote post for <a href="https://x.com/x/status/1000000000000000009">@x</a>:'):
    return label + "\n<pre>" + pre + "</pre>\n<i>Grounded on: test.</i>\n"


# ---- helpers ----

def test_visible_text_strips_tags_and_decodes_entities():
    assert vd.visible_text("<b>Hi</b> A &amp; B") == "Hi A & B"


def test_utf16_len_basic():
    assert vd.utf16_len("abc") == 3


def test_extract_drafts_finds_two_with_targets():
    drafts = vd.extract_drafts(msg(QUOTE, REPLY))
    assert len(drafts) == 2
    assert drafts[0]["target"] == "https://x.com/opentensor/status/1000000000000000001"
    assert drafts[0]["text"].startswith("Emission share is price-based")
    assert drafts[1]["target"] == "https://x.com/someminer/status/1000000000000000002"


def test_extract_drafts_decodes_entities_in_text():
    d = vd.extract_drafts(draft("R&amp;D budgets shift."))
    assert d[0]["text"] == "R&D budgets shift."


def test_extract_drafts_target_none_when_label_has_no_link():
    d = vd.extract_drafts("Quote post for @nobody:\n<pre>No link here.</pre>")
    assert d[0]["target"] is None


def test_contains_emoji_true_false():
    assert vd.contains_emoji("ship it \U0001f680")
    assert not vd.contains_emoji("a clean take - no slop, 2024-2025")


def test_em_and_en_dash_helpers():
    assert vd.has_em_dash("this — that")
    assert not vd.has_em_dash("this - that")
    assert vd.has_en_dash("2024–2025")
    assert not vd.has_en_dash("2024-2025")


def test_holder_language_detection():
    assert vd.has_holder_language("watch the holders here")
    assert vd.has_holder_language("Holder distribution is concentrated")
    assert not vd.has_holder_language("stakeholder incentives align")


# ---- count / structure ----

def test_two_drafts_clean_ok():
    errors, _ = vd.validate(msg(QUOTE, REPLY))
    assert errors == [], errors


def test_active_requires_at_least_one_draft():
    errors, _ = vd.validate(HEADER + "Some text but no drafts.\n" + FOOTER)
    assert any("draft" in e.lower() for e in errors)


def test_three_drafts_errors():
    b1 = draft("One.", 'Quote post for <a href="https://x.com/a/status/1">@a</a>:')
    b2 = draft("Two.", 'Reply to <a href="https://x.com/b/status/2">@b</a>:')
    b3 = draft("Three.", 'Quote post for <a href="https://x.com/c/status/3">@c</a>:')
    errors, _ = vd.validate(msg(b1, b2, b3))
    assert any("max 2" in e.lower() or "2 draft" in e.lower() for e in errors)


def test_quiet_window_zero_drafts_ok():
    text = HEADER + "Quiet window. Nothing cleared the bar.\n" + FOOTER
    errors, _ = vd.validate(text)
    assert errors == [], errors


def test_quiet_window_with_drafts_errors():
    text = HEADER + "Quiet window. Nothing cleared the bar.\n" + QUOTE + FOOTER
    errors, _ = vd.validate(text)
    assert any("quiet" in e.lower() for e in errors)


# ---- voice / format errors ----

def test_draft_emoji_errors():
    errors, _ = vd.validate(msg(draft("Cost per token is the story \U0001f680")))
    assert any("emoji" in e.lower() for e in errors)


def test_em_dash_anywhere_errors():
    bad = msg(draft("Solid release.")) + "<i>extra — note</i>"
    errors, _ = vd.validate(bad)
    assert any("em dash" in e.lower() for e in errors)


def test_draft_missing_target_errors():
    errors, _ = vd.validate(msg("Quote post for @nolink:\n<pre>No target.</pre>\n"))
    assert any("target" in e.lower() for e in errors)


def test_draft_non_x_target_errors():
    bad = draft("Off platform.", 'Quote post for <a href="https://example.com/x">@x</a>:')
    errors, _ = vd.validate(msg(bad))
    assert any("x.com" in e.lower() for e in errors)


def test_thread_opener_errors():
    errors, _ = vd.validate(msg(draft("1/ here is a thread about emissions")))
    assert any("thread" in e.lower() for e in errors)


def test_holder_language_in_draft_errors():
    errors, _ = vd.validate(msg(draft("The holders here are too concentrated.")))
    assert any("holder" in e.lower() for e in errors)


def test_unescaped_amp_errors():
    errors, _ = vd.validate(msg(draft("R&D budgets shift.")))
    assert any("amp" in e.lower() for e in errors)


def test_placeholder_errors():
    errors, _ = vd.validate(msg(draft("Hello {author} today.")))
    assert any("placeholder" in e.lower() for e in errors)


# ---- Bittensor factual lint (errors, negation-aware) ----

def test_single_token_emissions_errors():
    errors, _ = vd.validate(msg(draft("Remember, emissions are only alpha here.")))
    assert any("emission" in e.lower() for e in errors)


def test_validators_mine_errors():
    errors, _ = vd.validate(msg(draft("On this one the validators mine the data.")))
    assert errors != []


def test_validators_do_not_mine_ok():
    errors, _ = vd.validate(msg(draft("Quick note: validators do not mine, they set weights.")))
    assert errors == [], errors


def test_tao_burned_when_staking_errors():
    errors, _ = vd.validate(msg(draft("Note that TAO is burned when staking on a subnet.")))
    assert errors != []


def test_outdated_7200_errors():
    errors, _ = vd.validate(msg(draft("Daily emissions are 7,200 TAO right now.")))
    assert errors != []


def test_7200_from_is_ok():
    errors, _ = vd.validate(msg(draft("Block rewards dropped from 7,200 TAO to 3,600.")))
    assert errors == [], errors


def test_conviction_boosts_emissions_errors():
    errors, _ = vd.validate(msg(draft("Locking with conviction boosts your emissions.")))
    assert errors != []


def test_conviction_does_not_boost_ok():
    errors, _ = vd.validate(msg(draft("Locking does not boost emissions, it is a signal.")))
    assert errors == [], errors


def test_root_validators_vote_emissions_errors():
    errors, _ = vd.validate(msg(draft("Root validators vote to determine emissions each tempo.")))
    assert errors != []


# ---- warnings (do not block) ----

def test_over_280_warns_not_errors():
    errors, warnings = vd.validate(msg(draft("a" * 300)))
    assert errors == [], errors
    assert any("280" in w for w in warnings)


def test_en_dash_errors():
    errors, _ = vd.validate(msg(draft("Range was 2024–2025 here.")))
    assert any("en dash" in e.lower() for e in errors)


def test_robot_opener_warns():
    _, warnings = vd.validate(msg(draft("Under the current model, miner_burn cuts share.")))
    assert any("throat" in w.lower() or "lead with the point" in w.lower() for w in warnings)


def test_tidy_closer_warns():
    _, warnings = vd.validate(msg(draft("It cuts the share. The two goals aligned here by design.")))
    assert any("closer" in w.lower() or "by design" in w.lower() for w in warnings)


def test_url_in_draft_warns():
    _, warnings = vd.validate(msg(draft("See https://x.com/foo for the detail.")))
    assert any("url" in w.lower() for w in warnings)


def test_slop_phrase_warns():
    _, warnings = vd.validate(msg(draft("This is a total game changer for staking.")))
    assert any("slop" in w.lower() or "game changer" in w.lower() for w in warnings)


def test_chain_buys_as_risk_warns():
    _, warnings = vd.validate(msg(draft("0% chain buys, looks weak to me.")))
    assert any("chain buy" in w.lower() for w in warnings)


def test_temporal_miner_burn_past_warns():
    _, warnings = vd.validate(msg(draft("Every point of miner burn was costing them emission share.")))
    assert any("temporal" in w.lower() for w in warnings)


def test_current_tense_miner_burn_no_temporal_warn():
    _, warnings = vd.validate(msg(draft("miner_burn now cuts the subnet emission share directly.")))
    assert not any("temporal" in w.lower() for w in warnings)


# ---- repo sample fixture ----

def test_repo_sample_validates_clean():
    path = Path(__file__).resolve().parent.parent / "examples" / "sample-message.html"
    errors, _ = vd.validate(path.read_text(encoding="utf-8"))
    assert errors == [], errors
