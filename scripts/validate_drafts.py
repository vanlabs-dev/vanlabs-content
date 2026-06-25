#!/usr/bin/env python3
"""Deterministic pre-send gate for the Bittensor Engagement Engine.

Validates the final Telegram message text (HTML, parse_mode=HTML) BEFORE it is sent.
Exit code 0 means the message is safe to send. Exit code 1 means one or more hard
errors were found and the routine MUST NOT send it.

This gate enforces format, brand-voice invariants, and known-wrong Bittensor phrasings.
It is NOT a truth detector: live-data validation (the routine) and the human gate cover
semantic correctness. See references/ for the editorial and validation rules.

Hard errors (block the send):
  - unsupported or unbalanced HTML tags; unescaped '<', '>' or '&'
  - an <a> without an http(s) href; message over the 4096 visible-char limit
  - leftover {placeholder} tokens
  - draft count out of range (1-2 on an active window; 0 on a quiet window)
  - a draft with no target tweet link, or a target that is not an x.com/twitter.com status
  - an em dash anywhere in the message (global brand rule)
  - in a draft: emoji, a thread opener (N/), holder-count language
  - a high-confidence wrong Bittensor claim (negation-aware)

Warnings (printed, do NOT block):
  - a draft over 280 chars; an en dash; a URL inside the copy block
  - a high-signal slop phrase; lower-confidence factual patterns needing context

Usage:
  python3 validate_drafts.py message.html
  python3 validate_drafts.py -            # read from stdin
"""
from __future__ import annotations

import argparse
import html
import re
import sys

ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "a", "code", "pre", "blockquote", "tg-spoiler",
}

TELEGRAM_MAX_LEN = 4096

TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^<>]*?)?)\s*>")
ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);")
HREF_RE = re.compile(r'href\s*=\s*"([^"]*)"', re.I)
PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z0-9_]+\}")
PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.S)
X_STATUS_RE = re.compile(r"https?://(x\.com|(mobile\.)?twitter\.com)/", re.I)
QUIET_RE = re.compile(r"quiet window", re.I)
HOLDER_RE = re.compile(r"\bholders?\b", re.I)
URL_IN_TEXT_RE = re.compile(r"https?://", re.I)
NEG_RE = re.compile(r"\b(not|never|no|isn't|aren't|don't|doesn't|didn't|won't|cannot|can't)\b|n't", re.I)

# Emoji / pictographic ranges (excludes punctuation, hyphens, en/em dashes).
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF]"
)

# High-confidence wrong Bittensor claims -> ERROR. Each is checked negation-aware.
# (pattern, message). Patterns are case-insensitive.
FACTUAL_ERROR_PATTERNS = [
    (r"emissions?\s+(are\s+|paid\s+)?only\s+(in\s+)?alpha", "emissions described as alpha-only (both TAO and alpha are injected)"),
    (r"emissions?\s+(are\s+)?only\s+(in\s+)?tao", "emissions described as TAO-only (both TAO and alpha are injected)"),
    (r"emissions?\s+paid\s+in\s+tao\b", "emissions described as paid in TAO (both TAO and alpha are injected)"),
    (r"earn(ing)?\s+tao\s+from\s+emissions", "earning TAO from emissions (participants receive alpha; TAO backs the pool)"),
    (r"receives?\s+tao\s+as\s+emissions", "receiving TAO as emissions (participants receive alpha)"),
    (r"7[,]?200\s*tao", "outdated emission rate 7,200 TAO (current is ~3,600 TAO/day)"),
    (r"validators?\s+(mine|mining|produce\s+work)", "validators do not mine; they evaluate and set weights"),
    (r"tao\s+(is\s+)?burned?\s+(when|during|by|on)\s+staking", "TAO is not burned when staking (it enters the AMM pool)"),
    (r"staking\s+burns?\s+tao", "staking does not burn TAO (it enters the AMM pool)"),
    (r"root\s+validators?\s+(vote|voting|decide|determine|set)\w*\b[^.]{0,40}emissions?", "root validators no longer vote on emissions (price-based since dTAO)"),
    (r"emissions?\s+(are|is)\s+(driven\s+by|based\s+on|determined\s+by)\s+(net\s+)?(tao\s+)?flows?", "flow-based emissions are outdated (price-based since June 2026)"),
    (r"(net\s+)?(tao\s+)?flows?\s+(drive|determine|set)\s+\w{0,12}\s*emissions?", "net flows no longer drive emissions (price-based since June 2026)"),
    (r"(locking|locked|conviction)\b[^.]{0,40}(boost|increas|raise|higher|more)\w*[^.]{0,25}(emission|reward|yield|weight)", "locking/conviction does not boost emissions or rewards"),
    (r"(boost|increas|raise|higher|more)\w*[^.]{0,25}(emission|reward|yield|weight)[^.]{0,25}(by\s+)?(locking|conviction)", "locking/conviction does not boost emissions or rewards"),
]
FACTUAL_ERROR_RE = [(re.compile(p, re.I), m) for p, m in FACTUAL_ERROR_PATTERNS]

# High-signal slop -> WARNING (kept tight to avoid false positives).
SLOP_PATTERNS = [
    r"game[\s-]?changer", r"game[\s-]?changing", r"this changes everything",
    r"let that sink in", r"the future is here", r"\bhot take:", r"unpopular opinion:",
    r"buckle up", r"we'?re so back", r"we are so back", r"\bdelve\b", r"\brevolutionary\b",
    r"\bgroundbreaking\b", r"\bcutting[\s-]edge\b", r"not just .{1,40}?,?\s+it'?s\b",
    r"\bthrilled to\b", r"\bexcited to\b", r"\b(massive|insane)\b",
    r"thoughts\?\s*$", r"what do you think", r"\bever wonder",
]
SLOP_RE = [re.compile(p, re.I) for p in SLOP_PATTERNS]

# Lower-confidence factual patterns -> WARNING (need context).
FACTUAL_WARN_PATTERNS = [
    (r"(0%|zero|no)\s+(emission\s+buy|chain\s+buy)", "0% chain buys is not a risk signal; confirm framing"),
    (r"all\s+subnets\s+(do|are|use|run|focus)", "'all subnets' claim; verify it is accurate"),
    (r"you\s+earn\s+by\s+staking\s+tao", "stakers earn through validators, not directly"),
]
FACTUAL_WARN_RE = [(re.compile(p, re.I), m) for p, m in FACTUAL_WARN_PATTERNS]


def utf16_len(s: str) -> int:
    """Telegram counts message length in UTF-16 code units."""
    return len(s.encode("utf-16-le")) // 2


def visible_text(s: str) -> str:
    """Approximate what Telegram renders: strip tags, then decode entities."""
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def contains_emoji(s: str) -> bool:
    return bool(EMOJI_RE.search(s))


def has_em_dash(s: str) -> bool:
    return "—" in s or "―" in s  # em dash, horizontal bar


def has_en_dash(s: str) -> bool:
    return "–" in s  # en dash


def has_holder_language(s: str) -> bool:
    return bool(HOLDER_RE.search(s))


def _negated(text: str, start: int, end: int) -> bool:
    """True if a negation token sits within the match or just before it."""
    window = text[max(0, start - 25):end]
    return bool(NEG_RE.search(window))


def bittensor_factual_errors(text: str) -> list[str]:
    """Known-wrong Bittensor phrasings, negation-aware. Returns error messages."""
    out = []
    low = text
    for rx, msg in FACTUAL_ERROR_RE:
        for m in rx.finditer(low):
            # '7,200 TAO' is fine when it is the OLD rate ('from 7,200 ...').
            if "7,200" in m.group(0) or "7200" in m.group(0):
                pre = low[max(0, m.start() - 12):m.start()].lower()
                if "from" in pre or "dropped" in pre or "was" in pre:
                    continue
            if _negated(low, m.start(), m.end()):
                continue
            out.append(f"Bittensor factual error: {msg}")
            break  # one report per pattern is enough
    return out


def slop_warnings(text: str) -> list[str]:
    out = []
    for rx in SLOP_RE:
        if rx.search(text):
            out.append(f"Possible slop phrase: {rx.pattern!r}")
    return out


def factual_warnings(text: str) -> list[str]:
    out = []
    for rx, msg in FACTUAL_WARN_RE:
        if rx.search(text):
            out.append(f"Check: {msg}")
    return out


def parse_html(s: str):
    """Validate Telegram-HTML tags and entity escaping. Returns (errors, hrefs)."""
    errors = []
    hrefs = []
    stack = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "<":
            m = TAG_RE.match(s, i)
            if not m:
                snippet = s[i:i + 25].replace("\n", " ")
                errors.append(f"Unescaped '<' (use &lt;) near: {snippet!r}")
                i += 1
                continue
            name = m.group(1).lower()
            attrs = m.group(2) or ""
            is_close = m.group(0).startswith("</")
            if name not in ALLOWED_TAGS:
                errors.append(f"Unsupported HTML tag <{name}> - Telegram will reject the message")
            elif is_close:
                if not stack or stack[-1] != name:
                    errors.append(f"Mismatched closing tag </{name}>")
                else:
                    stack.pop()
            else:
                if name == "a":
                    hm = HREF_RE.search(attrs)
                    if not hm:
                        errors.append("<a> tag has no href")
                    else:
                        href = hm.group(1)
                        hrefs.append(href)
                        if not re.match(r"https?://", href, re.I):
                            errors.append(f"<a> href is not http(s): {href!r}")
                stack.append(name)
            i = m.end()
        elif c == ">":
            errors.append("Unescaped '>' (use &gt;)")
            i += 1
        elif c == "&":
            m = ENTITY_RE.match(s, i)
            if m:
                i = m.end()
            else:
                snippet = s[i:i + 20].replace("\n", " ")
                errors.append(f"Unescaped '&' (use &amp;) near: {snippet!r}")
                i += 1
        else:
            i += 1
    if stack:
        errors.append("Unclosed tag(s): " + ", ".join("<%s>" % t for t in stack))
    return errors, hrefs


def extract_drafts(s: str):
    """Find X drafts. A draft is a <pre> block (chrome never uses <pre>).

    The target tweet link is the last <a href> in the same paragraph (since the
    previous blank line) preceding the block.
    """
    drafts = []
    for m in PRE_RE.finditer(s):
        raw = m.group(1)
        text = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        chunk = s[: m.start()].split("\n\n")[-1]
        hm = None
        for hm in HREF_RE.finditer(chunk):
            pass  # keep the last href in the label paragraph
        target = hm.group(1) if hm else None
        drafts.append({"text": text, "raw": raw, "target": target})
    return drafts


def validate(text, max_len=TELEGRAM_MAX_LEN):
    """Run all checks. Returns (errors, warnings)."""
    errors = []
    warnings = []

    # 1. HTML validity + escaping
    html_errors, _ = parse_html(text)
    errors.extend(html_errors)

    # 2. Length (visible text after entity parsing)
    length = utf16_len(visible_text(text))
    if length > max_len:
        errors.append(f"Message is {length} chars, over the Telegram {max_len} limit")
    elif length > max_len - 200:
        warnings.append(f"Message is {length} chars, close to the {max_len} limit")

    # 3. Placeholders
    for ph in sorted(set(PLACEHOLDER_RE.findall(text))):
        errors.append(f"Unfilled placeholder token: {ph}")

    # 4. Em dash anywhere (global brand rule)
    if has_em_dash(text):
        errors.append("Em dash (or horizontal bar) present; use a hyphen, comma, or colon")

    # 5. Draft count vs quiet window
    quiet = QUIET_RE.search(text) is not None
    drafts = extract_drafts(text)
    n = len(drafts)
    if quiet:
        if n != 0:
            errors.append(f"{n} draft(s) present on a quiet window (expected 0)")
    else:
        if n < 1:
            errors.append("No drafts found and not a quiet window (expected 1-2)")
        elif n > 2:
            errors.append(f"{n} drafts found (max 2)")

    # 6. Per-draft checks
    for idx, d in enumerate(drafts, 1):
        dt = d["text"]
        if not d["target"]:
            errors.append(f"Draft {idx} has no target tweet link in its label")
        elif not X_STATUS_RE.search(d["target"]):
            errors.append(f"Draft {idx} target is not an x.com/twitter.com link: {d['target']!r}")
        if contains_emoji(dt):
            errors.append(f"Draft {idx} contains emoji")
        if re.match(r"^\s*\d+/", dt):
            errors.append(f"Draft {idx} looks like a thread ('N/' opener)")
        if has_holder_language(dt):
            errors.append(f"Draft {idx} uses holder-count language (banned)")
        for e in bittensor_factual_errors(dt):
            errors.append(f"Draft {idx}: {e}")
        # warnings
        if len(dt) > 280:
            warnings.append(f"Draft {idx} is {len(dt)} chars (>280; tighten if you can)")
        if has_en_dash(dt):
            warnings.append(f"Draft {idx} contains an en dash")
        if URL_IN_TEXT_RE.search(dt):
            warnings.append(f"Draft {idx} contains a URL inside the copy block")
        for w in slop_warnings(dt):
            warnings.append(f"Draft {idx}: {w}")
        for w in factual_warnings(dt):
            warnings.append(f"Draft {idx}: {w}")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate a Bittensor engage message before sending to Telegram."
    )
    ap.add_argument("path", help="Path to the message HTML file, or '-' for stdin")
    ap.add_argument("--max-len", type=int, default=TELEGRAM_MAX_LEN,
                    help="Max visible message length in UTF-16 units (default 4096)")
    args = ap.parse_args()

    if args.path == "-":
        text = sys.stdin.read()
    else:
        with open(args.path, "r", encoding="utf-8") as fh:
            text = fh.read()

    errors, warnings = validate(text, max_len=args.max_len)

    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR:   {e}")

    if errors:
        print(f"\nFAIL: {len(errors)} error(s), {len(warnings)} warning(s). Do NOT send.")
        return 1
    drafts = extract_drafts(text)
    length = utf16_len(visible_text(text))
    print(f"\nOK: message valid ({len(drafts)} draft(s), {length} chars, "
          f"{len(warnings)} warning(s)). Safe to send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
