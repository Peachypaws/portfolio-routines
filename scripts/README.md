# scripts/

## `x_sweep.py` — the mechanical half of the X Sweep

Implements Steps 1–6 of `prompts/x-sweep.md` (v1.3): pull with pagination and
high-water mark, same-author reply merge, bucket A/B/C, fetch, parse, URL
tracking-param strip, dedup, cap. Standard library only, Python 3.8+.

Writes one `candidates.json`:

```
{"meta": {...}, "records": [{post_url, account, captured, bucket,
  underlying_source_url, publisher, source_date, verification,
  owned_name_hits, anthropic_flag, translated_from, raw_post_text,
  fetched_page_path}]}
```

`meta` carries page counts, merge count, bucket counts, dedup clusters, the
dropped-by-cap list, fetch failures with HTTP status, parse failures, and
oldest/newest `created_at`.

### What it does not do

It decides nothing a model should decide.

- **No Headline. No Dated Claim.** Those stay with the model, written from
  `raw_post_text` and the page at `fetched_page_path`.
- **Never sets Layer.** There is no `layer` key anywhere in the output.
- **`verification` is a floor, not a verdict.** `"Unverified"` where the prompt
  forces it mechanically (bucket B; a fetch that failed, was paywalled, or
  short-circuited on a PDF). `null` means the fetch produced readable text and
  the model must choose between `Source fetched` and `Unverified` — "Source
  fetched" means the fetch *confirmed the claim*, which is a reading judgment.
- **Dedup on Dated Claim is not performed.** The script dedups on Post URL and
  on cleaned Underlying Source URL. It cannot compare a field it does not
  write. Hand the model's clusters back with `--merged-groups` (a JSON list of
  lists of Post URLs) and re-run Step 6.
- **`translated_from` reads the post's script only.** The "or says it is a
  translation" arm of the rule is left to the model.

### Usage

```
# live run
python3 scripts/x_sweep.py --high-water-mark <last run row's mark> --out candidates.json

# offline replay over saved pages, no API calls
python3 scripts/x_sweep.py --posts pulled.json --offline --pages-dir pages --out candidates.json

# fold the model's Dated-Claim clusters back into Step 6
python3 scripts/x_sweep.py --posts pulled.json --offline --pages-dir pages \
    --merged-groups clusters.json --existing signal-inbox.json --out candidates.json
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

`python3 scripts/test_x_sweep.py` — offline, no network. 1260 checks.

`fixtures/dry-run-2-signal-inbox.json` holds the mechanical fields of the 62
rows dry run 2 filed, read back from Notion. Dry run 2's **inputs** — the 265
pulled posts and the saved source pages — lived in that session's container and
were never committed, so the suite is not an end-to-end replay of dry run 2.
See `notes/runs/2026-09-07-x-sweep-script-test.md`.

## Unruled carry-overs

These come from dry run 2's "Decisions taken, not followed from the prompt".
Only decision (a) has been ruled (it is now the v1.3 suffix rule). The rest are
implemented as dry run 2 implemented them, and still need a CEO ruling:

| | Decision | How the script implements it |
|---|---|---|
| (b) | Asymmetric leading boundary | Letter-initial terms need a non-letter before them (`500MW` matches `MW`); digit-initial terms need a non-alphanumeric (`12nm` does not match `2nm`). Side effect: `MWh`/`GWh` do not match `MW`/`GW`. |
| (c) | Bogus expanded URL | A host that does not resolve at all is not a source: the candidate falls back to bucket B. A refused, reset or timed-out connection is a real host and stays in bucket A, Unverified — which is what dry run 2 did with the Sina Finance URL. |
| (d) | Shortener resolved | Redirects are followed and the final URL is recorded. |
| (e) | Fragment stripped | A fragment that is entirely tracking `key=value` pairs is stripped; an ordinary anchor is kept. |
| (f) | Cross-bucket merge keeps the source | A dedup cluster that joins a bucket-B row to a bucket-A row keeps the earliest Post URL **and** the resolved source URL. |
| (g) | "Source fetched" means read and confirmed | A PDF that downloaded but was not read files Unverified. |

Two more things the script surfaces rather than fixes:

- **The Anthropic Flag strings look wrong.** The prompt lists `앱트로픽` and
  `安人比`. Dry run 1 found `앤트로픽` on a source page — a different word. The
  script matches the prompt verbatim, because correcting a match string is a
  rule change. Worth a ruling.
- **The bucket-B digit gate now reads the quoted post.** The prompt's MATCHING
  RULES say to match against the post text, the note_tweet, *and* the quoted
  post's text; Step 3B gates on "the matched text". The script follows that.
  Dry run 1 excluded the quoted post from the digit check and discarded two
  posts as bucket C for it (defects: posts 5 and 17). Under the prompt as
  written those posts are bucket B. This will widen bucket B on a live run.
