# X Sweep — mechanical script, offline test and diff

**Date:** 2026-09-07 · **Artifacts:** `scripts/x_sweep.py`, `scripts/test_x_sweep.py`,
`scripts/fixtures/dry-run-2-signal-inbox.json`, `prompts/x-sweep.md` v1.3

No sweep was run. No API call was made. Nothing was written to Notion.
Notion was read twice: the 62 Signal Inbox rows, and the dry run 2 Run Log row.

## The test could not be run as specified

Dry run 2's inputs are gone. The 265 pulled posts and the saved source pages
lived in that session's container; the container is ephemeral and was
reclaimed. `git log --all` confirms the repo has never held them — the only
files it has ever contained are `README.md`, the two run notes, and
`prompts/x-sweep.md`.

So there is no offline replay of dry run 2 and I am not going to describe one.
What exists instead:

| | |
|---|---|
| **Output side — real** | The 62 rows dry run 2 filed, read back from the Signal Inbox and committed as `scripts/fixtures/dry-run-2-signal-inbox.json` (mechanical fields only; Headline and Dated Claim are model fields and are left out). |
| **Counts — real** | Page sizes, merge count, bucket counts, dedup clusters, the cap split and all 52 dropped post IDs, read from the dry run 2 Run Log row. |
| **Input side — gone** | 265 post texts, 38 fetched pages. Not recoverable without new API calls. |

**Fix for next time:** the script now saves every fetched page under
`--pages-dir` with a `manifest.json`, and `--posts` takes the raw API pages.
Keep both and a future run is replayable.

## Test result

`python3 scripts/test_x_sweep.py` — **1260 checks, all pass.** Offline, no
network, stdlib only.

What it covers:

1. **Matching.** Every worked example in prompt v1.3 and in both run notes:
   the digit-led suffix positives (`HBM`→HBM3E/HBM4, `LPDDR`→LPDDR6,
   `DDR`→DDR5), the letter-led negatives (`Meta`/metal, `PIC`/Picture,
   `ASE`/ASEAN, `ASE`/increase, `TPU`/output, `UPS`/upside), the optional
   plural `s`, terms ending in a digit taking no suffix (`N2` ≠ N2P), the
   asymmetric leading boundary (`500MW` matches `MW`, `12nm` does not match
   `2nm`, `MWh` does not match `MW`, `DDR` does not match inside `LPDDR6`),
   CJK substring matching, and script detection for Translated From.
2. **URL cleaning** against the real URLs dry run 2 filed — `?from=…&utm_source=…`
   stripped from the udn URL, `?PU=…&SN=…` and `?no=…` kept, `#from=ios`
   stripped, an ordinary anchor kept.
3. **Parser** — `html.parser`, PDF short-circuit by magic bytes / content-type /
   extension, `<aside>` and `<script>` excluded from body text so a
   related-links sidebar cannot raise the Anthropic Flag, JSON-LD fallback,
   malformed HTML survives, the `signal.alarm` handler is restored after use.
4. **Step 2 merge** — the story-then-bare-link-reply chain, chains deeper than
   two, no merge across authors, quoted text captured for matching.
5. **Step 6 dedup** — earliest post wins, handles and owned-name hits union,
   cross-bucket merge keeps the resolved source URL, existing-row collision on
   Post URL and on cleaned source URL.
6. **Step 6 cap** — replayed over dry run 2's real post-dedup distribution
   (bucket A 37, bucket B 77 = 49 with an owned-name hit + 28 without) under
   both the v1.2 and the v1.3 rule. See the diff below.
7. **End to end** — the script run offline over a synthetic pull built to the
   shapes dry run 2 described, checking bucket assignment, tracking-param
   strip, PDF → Unverified, bucket-B publisher = handle, and that no record
   carries a `layer`, `headline`, `dated_claim`, `status` or `classification`
   key.
8. **Fixture contract** — all 62 filed rows carry every mechanical field the
   script emits, no Layer, bucket-B rows have no URL and are Unverified with
   the handle as Publisher, every filed source URL is already clean
   (`clean_url` is idempotent over all 37), every owned-name hit is a
   match-table ticker or the explicit `None`, and Translated From only ever
   holds Korean / Chinese / Japanese.

## Diff against the 62 filed rows

Split into rule-change differences and bugs, as asked.

### A. Differences the two ruled changes cause

**A1 — Suffix rule: no difference. 62 rows unchanged.**

The v1.3 rule ("a suffix that STARTS WITH A DIGIT") is exactly the narrowing
dry run 2 already applied as decision (a) and flagged for a ruling. Ruling it
in changes nothing about what dry run 2 produced; it removes the second
reading of the sentence so the next run cannot drift. The script's matcher
passes every example on both sides of the rule.

**A2 — Cap rule: 49 more rows. 62 → 111.**

| | v1.2 (as run) | v1.3 (ruled) |
|---|---|---|
| Bucket A rows | 37 | 37 |
| Bucket B rows kept on an owned-name hit | 25 | **49** |
| Bucket B rows kept under the cap | — | **25** |
| Bucket B rows dropped | 52 | **3** |
| — of those, carrying an owned-name hit | **24** | **0** |
| **Total rows filed** | **62** | **111** |

The 24 rows that carried a live owned-name hit and were dropped anyway are now
never dropped. The cap falls back onto the 28 no-hit rows, keeps the most
recent 25 of them, and drops 3.

The Run Log row lists all 52 dropped post IDs. The list is two independently
descending runs of exactly 24 and 28 IDs, which lines up with the recorded
"24 that DID carry an owned-name hit plus all 28 no-hit rows" — so the two
groups are identifiable. Reading it that way, the 3 posts that would *still*
drop under v1.3 are the oldest of the no-hit group:

- `@wallstengine/2095951985732395334`
- `@wallstengine/2095963007939743911`
- `@DrNHJ/2095989208171319364`

That grouping is read off the list's ordering, not stated in the Run Log row.
Worth confirming against the posts before treating the three IDs as final; the
counts (24 / 28 / 3) do not depend on it.

Both cap outcomes are computed by the test, not asserted — `test_cap` runs the
v1.2 rule and the v1.3 rule over the same 114-row distribution.

### B. Bugs and divergences found — not caused by the rule changes

**B1 — The Anthropic Flag strings look wrong.** The prompt matches `앱트로픽`
and `安人比`. Dry run 1 found `앤트로픽` on a source page — a different word
(앱 vs 앤). `安人比` is not a rendering of Anthropic I can substantiate. The
script matches the prompt verbatim, because changing a match string is a rule
change. **Needs a ruling.** As written, the Korean and Chinese arms of that
flag will almost certainly never fire; the flag's 5 hits in dry run 2 all came
from the Latin strings.

**B2 — The bucket-B digit gate reads the quoted post, and dry run 1's did not.**
The prompt's MATCHING RULES say to match against the post text, the note_tweet
*and* the quoted post's text. Step 3B gates on "the matched text". The script
follows that. Dry run 1 excluded the quoted post from the digit check and put
two posts in bucket C for it (its posts 5 and 17 — "the 30-40 min is in the
quoted post", "LPDDR6 is in the quoted Chinese post"). Under the prompt as
written those are bucket B. **This will widen bucket B on a live run.** Dry run
2's bucket C was 84 of 214 candidates; I cannot say how much of that moves,
because the post texts are gone.

**B3 — "Source fetched" is not mechanical, so the script does not set it.**
The prompt says Source fetched "if the fetch confirmed the claim". Confirming a
claim is a reading judgment. The script emits `verification: "Unverified"`
where the prompt forces it (bucket B; failed, paywalled or PDF fetches) and
`null` otherwise, meaning the model must choose. Of dry run 2's 37 bucket-A
rows, 9 were fetch failures — those the script sets Unverified on its own; the
other 28 it leaves for the model.

**B4 — Dedup on Dated Claim cannot be mechanical either.** The script does not
write Dated Claim, so it cannot compare it. Of dry run 2's 11 dedup clusters,
**only cluster 1** (Samsung Foundry HBM4, two bucket-A posts on the same
ZDNet URL) is reachable by URL matching. The other 10 either had no link on at
least one side or joined a bucket-B post to a bucket-A post. So the script
reproduces 1 of 11 clusters unaided.

That is not a defect in the script — it is where the split between clerk and
model actually falls. `--merged-groups` takes the model's clusters back and
re-runs Step 6, so the two halves compose. It does mean the cap the script
reports is provisional until the model's dedup is folded in: fewer bucket-B
rows after dedup means a different cap outcome.

**B5 — 8 of the 62 filed rows are multi-account,** and the fixture confirms the
script's account-merge shape reproduces them (handles appended in
earliest-first order, hits unioned). The other 3 clusters dry run 2 recorded
never became rows — they were dropped by the cap.

### C. Decisions carried over from dry run 2 that are still unruled

Implemented as dry run 2 implemented them, listed in `scripts/README.md`:
(b) asymmetric leading boundary, (c) bogus expanded URL falls back to bucket B,
(d) shortener resolved to its target, (e) tracking fragment stripped,
(f) cross-bucket merge keeps the source URL, (g) an unread PDF is Unverified.

Decision (c) is the one with a mechanical edge: the script reclassifies A→B
only when the host does not resolve at all. A refused, reset or timed-out
connection stays bucket A and Unverified — which is what dry run 2 did with the
Sina Finance URL, while `https://300308.SZ`
(`@QQ_Timmy/2096850021434974542`) was reclassified.

## Still open

- The cap is no longer the binding constraint. On dry run 2's numbers, v1.3
  files 111 rows where v1.2 filed 62. Whether 111 rows a night is the intended
  volume is a separate call from the one just ruled.
- The List was not exhausted at 3 pages and the high-water mark is not a clean
  stopping point. Unchanged by this work.
- Defect 3 from dry run 1 (Latin-only match table under-fires on Korean body
  text) is unchanged. The script matches the table it is given.
