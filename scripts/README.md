# scripts/

## `x_sweep.py` — the mechanical half of the X Sweep

Implements Steps 1 through **6a** of `prompts/x-sweep.md` (v1.5): pull with
pagination and high-water mark, same-author reply merge, bucket A/B/C, fetch,
parse, URL tracking-param strip, URL-level dedup. Standard library only,
Python 3.8+.

Then it stops. `candidates.json` carries **every surviving candidate,
uncapped.**

Writes one `candidates.json`:

```
{"meta": {...}, "records": [{post_url, account, captured, bucket,
  underlying_source_url, publisher, source_date, verification,
  owned_name_hits, anthropic_flag, translated_from, raw_post_text,
  fetched_page_path,
  _post_ids, _post_texts, _quoted_text, _quoted_posts, _layer_hits,
  _digit_gate, _source_excerpt, _page_title, _fetch_status}]}
```

**Underscore-prefixed keys are working fields for the model, not Signal Inbox
columns.** The six added for v1.5 close the handover gaps dry run 3 named:

| field | why |
|---|---|
| `_layer_hits` | the layer keywords that satisfied the Step 3B gate. It was computed and thrown away; for a bucket-B row it is often the only vocabulary the Headline can draw on. **It is not a Layer** — Layer is the Weekly Signal Review's and appears nowhere in this file. |
| `_digit_gate` | `{digit, context, source}` — what satisfied the digit test, *after* URLs are stripped, and whether it came from the post or the quoted post. |
| `_post_texts` | per-post attribution across a Step 2 merge or a 6a collapse: `{post_id, post_url, account, created_at, is_head, contributed_text, text}`. A figure has to be traceable to the Post URL it came from; the joined `raw_post_text` is a convenience, this is the record. |
| `_quoted_posts` | the quoted post's `account` and `post_url` alongside its text. Naming the interested party in a Dated Claim means naming who wrote it. |
| `_source_excerpt` | up to `SOURCE_EXCERPT_CHARS` (1500) of bucket-A body text, so "did the fetch confirm the claim" is answerable without re-reading the saved HTML. Body text only, so an excluded sidebar cannot leak in. `null` for bucket B. |
| `_fetch_status`, `_page_title`, `_post_ids` | as before. |

`meta` carries page counts, merge count, bucket counts, URL-dedup clusters,
already-filed collisions, fetch failures with HTTP status, parse failures, and
oldest/newest `created_at`. It has no cap keys — see below.

### What it does not do

It decides nothing a model should decide.

- **No Headline. No Dated Claim.** Those stay with the model, written from
  `_post_texts` / `_quoted_posts` and the page at `fetched_page_path`.
- **Never sets Layer.** There is no `layer` or `Layer` key in the output.
  `_layer_hits` is Step 3B gate evidence — the keywords that let a no-link post
  through — and assigning a Layer from it is exactly the judgment call the
  prompt reserves for the Weekly Signal Review.
- **`verification` is a floor, not a verdict, and it is never null.** Two named
  states, and only these two: `"Unverified"` where the prompt forces it
  mechanically (bucket B; a fetch that failed, was paywalled, or
  short-circuited on a PDF), and `"Model decides"` where the fetch produced
  readable text and the model must choose between `Source fetched` and
  `Unverified` — "Source fetched" means the fetch *confirmed the claim*, which
  is a reading judgment. Before v1.5 the second state was a bare `null`, which
  reads like a missing field. **`"Model decides"` is not a Notion option and
  must never reach the Signal Inbox** — the model resolves it at Step 5.
- **Step 6 stops at 6a.** The script dedups on Post URL and on cleaned
  Underlying Source URL, and that is all. It does not run 6b (claim-level
  dedup) — it cannot compare a field it does not write — and it does not run
  6c (the cap).

  Since prompt v1.5, 6b also runs against **existing** Signal Inbox rows —
  6a's cross-run arm is URL-only, so a link-free claim re-pasted by a new
  account on a later day has nothing to collide with. That arm is the model's
  too; the script has no view of the inbox beyond the `--existing` URL list.

  **The order matters and the prompt states it: 6a, then 6b, then 6c.** Capping
  before claim-level dedup counts duplicates against the limit and drops rows
  that were about to merge into a surviving row — and the copy it drops may be
  the one carrying a handle, an owned-name hit, or the cluster's only resolved
  source URL. So the script hands over everything and the model caps last.
- **`translated_from` reads the post's script only.** The "or says it is a
  translation" arm of the rule is left to the model.

### Usage

```
# live run
python3 scripts/x_sweep.py --high-water-mark <last run row's mark> --out candidates.json

# offline replay over saved pages, no API calls
python3 scripts/x_sweep.py --posts pulled.json --offline --pages-dir pages --out candidates.json

# dedup against rows already in the Signal Inbox
python3 scripts/x_sweep.py --posts pulled.json --offline --pages-dir pages \
    --existing signal-inbox.json --out candidates.json
```

Every fetched page is saved under `--pages-dir` with a `manifest.json`, so a
run can be replayed offline and the model can read the page the script read.

The parser is `html.parser` with a per-file `signal.alarm` timeout and a PDF
short-circuit — a PDF is saved and recorded, never parsed. `<nav>`, `<aside>`,
`<footer>`, `<script>` and `<style>` are excluded from body text, so a
related-links sidebar cannot raise the Anthropic Flag.

`api.x.com` is reached through the environment's API credential; the script
sends no token of its own unless `X_BEARER_TOKEN` is set.

### Tests

`python3 scripts/test_x_sweep.py` — offline, no network. 1435 checks.

The suite also holds both cap rules as reference arithmetic for prompt Step 6c,
so the 62 → 111 figure in the run note stays checkable. The script itself has
no cap and the suite asserts that.

`fixtures/dry-run-2-signal-inbox.json` holds the mechanical fields of the 62
rows dry run 2 filed, read back from Notion. Dry run 2's **inputs** — the 265
pulled posts and the saved source pages — lived in that session's container and
were never committed, so the suite is not an end-to-end replay of dry run 2.
See `notes/runs/2026-09-07-x-sweep-script-test.md`.

## Unruled carry-overs

These come from dry run 2's "Decisions taken, not followed from the prompt".
(a) has been ruled — it is now the suffix rule. (f) has been folded into the
prompt as a Step 6b rule. The rest are implemented as dry run 2 implemented
them, and still need a CEO ruling:

| | Decision | How the script implements it |
|---|---|---|
| (b) | Asymmetric leading boundary | Letter-initial terms need a non-letter before them (`500MW` matches `MW`); digit-initial terms need a non-alphanumeric (`12nm` does not match `2nm`). Side effect: `MWh`/`GWh` do not match `MW`/`GW`. |
| (c) | Bogus expanded URL | **Ruled and rewritten after dry run 3 — see below.** The host is now validated *before* any fetch. A refused, reset or timed-out connection is still a real host and stays in bucket A, Unverified — which is what dry run 2 did with the Sina Finance URL. |
| (d) | Shortener resolved | Redirects are followed and the final URL is recorded. |
| (e) | Fragment stripped | A fragment that is entirely tracking `key=value` pairs is stripped; an ordinary anchor is kept. |
| (f) | Cross-bucket merge keeps the source | Now a Step 6b rule, stated in the prompt: a cluster joining a no-link row to one with a resolved source keeps the earliest Post URL **and** that source URL. It cannot arise at 6a — every member of a URL cluster carries the same URL. |
| (g) | "Source fetched" means read and confirmed | A PDF that downloaded but was not read files Unverified. |

## Ruled 2026-09-07 — do not "fix" these back

- **Anthropic Flag strings are `Anthropic`, `Claude`, `앤트로픽`. Three strings,
  no others.** The earlier list carried `앱트로픽` — wrong character, the word
  is 앤트로픽 — and `安人比`, which is not a rendering of Anthropic anyone could
  substantiate. Both are gone. Do not re-add them.

- **The Step 3B digit gate strips URLs first.** A t.co shortlink is random
  alphanumerics and carries digits almost always. Dry run 3 filed
  "KING CHARLES III'S AI MEETING LIST" — no figure anywhere in the post — on
  the digits inside `https://t.co/w9kVRQr8iC`. `strip_urls()` runs before the
  digit test and nowhere else: **owned-name and layer-keyword matching still
  read the text with its URLs intact**, because a keyword inside a slug is a
  real hit. Do not "simplify" the two paths back together.

- **An implausible host is rejected BEFORE the fetch, and never on HTTP
  status.** `implausible_host()` demotes the candidate to bucket B with no
  request made. Dry run 2's decision (c) watched for a DNS resolver error;
  behind an HTTPS CONNECT proxy the resolver error never surfaces — the proxy
  answers `502 Bad Gateway` — so `https://300308.SZ` filed as bucket A in both
  dry run 2 and dry run 3.

  Note what the rule actually keys on. **`.sz` is a real ccTLD (Eswatini)**, so
  "is this a real TLD" does *not* reject `300308.SZ`. What rejects it is its
  shape: X's auto-linker turns an exchange ticker written in running text into
  a URL, and an all-digit label under a two-letter TLD with no path and no
  query is that ticker, not a website — `300308.SZ`, `600519.SS`, `0700.HK`,
  `005930.KS`. The path condition keeps it narrow: `https://300308.sz/news/x`
  passes. `_is_dns_failure` is kept as a second net for unproxied runs.

- **The bucket-B digit gate reads the quoted post, and that is correct.**
  "Matched text" is the full set from MATCHING RULES: post text, note_tweet,
  **and** the quoted post. The digit may come from the quoted post, and so may
  the matched string. Dry run 1 narrowed this to the post text alone and threw
  away two live candidates for it (its posts 5 and 17 — "the 30-40 min is in
  the quoted post", "LPDDR6 is in the quoted Chinese post"). **That narrowing
  was the bug, not the fix.** It will widen bucket B on a live run; that is the
  intended effect. If a future run shows bucket B growing and someone reaches
  for the post-text-only reading, this is the note saying no.
