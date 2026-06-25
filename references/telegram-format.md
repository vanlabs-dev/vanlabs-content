# Telegram Format

The message is sent with `parse_mode: HTML`. HTML (not Markdown) is used because it is far
more robust to special characters in handles and draft text.

## Allowed tags (everything else is rejected by Telegram)
Use only: `<b>` `<strong>` `<i>` `<em>` `<u>` `<ins>` `<s>` `<strike>` `<del>`
`<a href="...">` `<code>` `<pre>` `<blockquote>` `<tg-spoiler>`

Do NOT use `<br>`, `<p>`, `<div>`, `<ul>`, `<li>`, `<h1>`, or a bare `<span>`. Use real
newlines for line breaks.

## Escaping (critical)
In any dynamic text (draft body, handles, the "Grounded on" note), escape these three:
- `&` becomes `&amp;`
- `<` becomes `&lt;`
- `>` becomes `&gt;`

Unescaped `&`, `<`, or `>` is the most common cause of a Telegram "can't parse entities"
error. `scripts/validate_drafts.py` enforces this.

## Active window template (1-2 drafts)
Keep one blank line between blocks. Each draft is a `<pre>` block (tap-to-copy); its content
is plain text, HTML-escaped, with no emoji, no em dash, and no URL. The label line above
carries the chosen format and the target tweet link. The italic "Grounded on" line sits
*outside* the `<pre>` so the copy block stays clean.

```
🛰️ <b>Bittensor - engage</b>
<i>{Weekday, Month DD, YYYY · HH:MM TZ}</i>

Quote post for <a href="TWEET_URL">@author</a>:
<pre>One to three sentences of original commentary in the @vaNlabs voice.</pre>
<i>Grounded on: one-line validation basis.</i>

Reply to <a href="TWEET_URL">@author</a>:
<pre>A shorter, pointed reply or a genuine question.</pre>
<i>Grounded on: one-line validation basis.</i>

<i>Manual post only. Validated, you decide.</i>
```

No em dash appears anywhere in the message (header, labels, drafts, footer): the brand rule
is no em dashes ever, and the gate enforces it across the whole message. Hyphens are fine.

- `TWEET_URL` must be an `x.com`/`twitter.com` status link.
- The label MUST start with exactly "Quote post for" or "Reply to" (the gate and you parse
  this to know the chosen format).
- "Grounded on:" names what was checked, e.g. "chain buys vs emission share (ground-truth);
  SN64 owner + emission live via TaoSwap" or "GitHub commit 9f2a1c, pushed 2 days ago".

## Quiet window template (0 drafts)
Send this when nothing clears the bar. The marker phrase "Quiet window" is what the gate uses
to require zero drafts.

```
🛰️ <b>Bittensor - engage</b>
<i>{Weekday, Month DD, YYYY · HH:MM TZ}</i>

Quiet window. Nothing cleared the bar.
```

## Build the payload safely and send
After `scripts/validate_drafts.py` exits 0, build the JSON with a real encoder. Do not
hand-interpolate HTML into a shell string (newlines and quotes will break it):

```bash
python3 - "$TELEGRAM_CHAT_ID" message.html > payload.json <<'PY'
import json, sys
chat_id, path = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
print(json.dumps({
    "chat_id": chat_id,
    "parse_mode": "HTML",
    "link_preview_options": {"is_disabled": True},
    "text": text,
}))
PY

curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  --data @payload.json
```

Confirm the response contains `"ok":true`. If Telegram returns a parse error, it is almost
always an unescaped `&`, `<`, or `>` in dynamic text: fix it and retry once.
