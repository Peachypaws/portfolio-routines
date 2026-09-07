# X Sweep — mechanical script, offline test and diff

**Date:** 2026-09-07 · **Artifacts:** `scripts/x_sweep.py`, `scripts/test_x_sweep.py`,
`scripts/fixtures/dry-run-2-signal-inbox.json`, `prompts/x-sweep.md` v1.4

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

`python3 scripts/test_x_sweep.py` — **1290 checks, all pass.** Offline, no
network, stdlib only.

What it covers:

1. **Matching.** Every worked example in prompt v1.4 and in both run notes:
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
5. **Step 6a dedup** — earliest post wins, handles and owned-name hits union,
   existing-row collision on Post URL and on cleaned source URL, and the two
   things 6a must NOT do: it does not join a no-link candidate to a linked one,
   and two accounts pasting the same claim link-free both survive.
6. **Step 6c cap — reference arithmetic only.** The script does not cap. Both
   rules are implemented in the test file and run over dry run 2's real
   post-dedup distribution (bucket A 37, bucket B 77 = 49 with an owned-name
   hit + 28 without), so the numbers below stay checkable. The suite also
   asserts the script exposes no `apply_cap` and no cap constant.
7. **End to end** — the script run offline over a synthetic pull built to the
   shapes dry run 2 described, checking bucket assignment, tracking-param
   strip, PDF → Unverified, bucket-B publisher = handle, that a no-hit
   bucket-B candidate survives (nothing is capped), that `meta` declares 6b and
   6c not done, that only `앤트로픽` raises the Anthropic Flag and `앱트로픽`
   does not, and that no record carries a `layer`, `headline`, `dated_claim`,
   `status` or `classification` key.
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

The ruled suffix rule ("a suffix that STARTS WITH A DIGIT") is exactly the narrowing
dry run 2 already applied as decision (a) and flagged for a ruling. Ruling it
in changes nothing about what dry run 2 produced; it removes the second
reading of the sentence so the next run cannot drift. The script's matcher
passes every example on both sides of the rule.

**A2 — Cap rule: 49 more rows. 62 → 111.**

| | Old cap (as run) | Ruled cap |
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
drop under the ruled cap are the oldest of the no-hit group:

- `@wallstengine/2095951985732395334`
- `@wallstengine/2095963007939743911`
- `@DrNHJ/2095989208171319364`

That grouping is read off the list's ordering, not stated in the Run Log row.
Worth confirming against the posts before treating the three IDs as final; the
counts (24 / 28 / 3) do not depend on it.

Both cap outcomes are computed by the test, not asserted — `test_cap` runs the
old rule and the ruled one over the same 114-row distribution. The script does
not cap; that arithmetic lives in the test file to keep these numbers checkable.

### B. Bugs and divergences found — not caused by the rule changes

**B1 — The Anthropic Flag strings were wrong. Ruled and fixed.** The prompt
matched `앱트로픽` (wrong character — the word is 앤트로픽) and `安人比`, which
is not a rendering of Anthropic anyone could substantiate. Both removed. The
list is now `Anthropic`, `Claude`, `앤트로픽` — three strings, no others, in
both the prompt and the script. No effect on dry run 2's 5 flagged rows: all
five fired on the Latin strings. The effect is forward — a Korean post naming
앤트로픽 now flags where it previously could not.

**B2 — The bucket-B digit gate reads the quoted post. Ratified as written.**
The prompt's MATCHING RULES say to match against the post text, the note_tweet
*and* the quoted post's text; Step 3B gates on "the matched text". Dry run 1
narrowed that to the post text alone and put two live candidates in bucket C
for it (its posts 5 and 17 — "the 30-40 min is in the quoted post", "LPDDR6 is
in the quoted Chinese post"). **That narrowing was the bug.** Step 3B now says
so explicitly, and `scripts/README.md` carries a "do not fix this back" note.
This will widen bucket B on a live run; that is the intended effect. Dry run
2's bucket C was 84 of 214 candidates and I cannot say how much of it moves,
because the post texts are gone.

**B3 — "Source fetched" is not mechanical, so the script does not set it.**
The prompt says Source fetched "if the fetch confirmed the claim". Confirming a
claim is a reading judgment. The script emits `verification: "Unverified"`
where the prompt forces it (bucket B; failed, paywalled or PDF fetches) and
`null` otherwise, meaning the model must choose. Of dry run 2's 37 bucket-A
rows, 9 were fetch failures — those the script sets Unverified on its own; the
other 28 it leaves for the model.

**B4 — Dedup on Dated Claim cannot be mechanical, and that moved the Step 6
boundary.** Of dry run 2's 11 dedup clusters, **only cluster 1** (Samsung
Foundry HBM4, two bucket-A posts on the same ZDNet URL) is reachable by URL
matching. The other 10 either had no link on at least one side or joined a
no-link post to a linked one. So URL matching reproduces 1 of 11 clusters.

That is where the clerk/model split actually falls, and it forces the order.
Step 6 is now three sub-steps in the prompt, stated as a rule:

- **6a URL-level dedup** — mechanical, the script's, and where it stops.
- **6b claim-level dedup** — the model's, and impossible before Step 5, because
  Dated Claim does not exist until the model writes it.
- **6c the cap** — the model's, and **last**.

Capping before 6b counts duplicates against the limit and drops rows that were
about to merge into a surviving row — and the copy it drops may be the one
carrying a handle, an owned-name hit, or the cluster's only resolved source
URL. On dry run 2's numbers 10 of 11 clusters are invisible at 6a, so capping
there would have been capping a list that was still ~15 candidates too long.

The script therefore emits **every surviving candidate, uncapped**. It has no
`--merged-groups`, no `--cap`, and no cap constant.

**B5 — 8 of the 62 filed rows are multi-account,** and the fixture confirms the
script's account-merge shape reproduces them (handles appended in
earliest-first order, hits unioned). The other 3 clusters dry run 2 recorded
never became rows — they were dropped by the cap.

### C. Decisions carried over from dry run 2 that are still unruled

Implemented as dry run 2 implemented them, listed in `scripts/README.md`:
(b) asymmetric leading boundary, (c) bogus expanded URL falls back to bucket B,
(d) shortener resolved to its target, (e) tracking fragment stripped,
(g) an unread PDF is Unverified. (f) is now written into the prompt as a Step 6b
rule.

Decision (c) is the one with a mechanical edge: the script reclassifies A→B
only when the host does not resolve at all. A refused, reset or timed-out
connection stays bucket A and Unverified — which is what dry run 2 did with the
Sina Finance URL, while `https://300308.SZ`
(`@QQ_Timmy/2096850021434974542`) was reclassified.

## Still open

- The cap is no longer the binding constraint. On dry run 2's numbers the ruled
  cap files 111 rows where the old one filed 62. Whether 111 rows a night is
  the intended volume is a separate call from the one already ruled.
- The List was not exhausted at 3 pages and the high-water mark is not a clean
  stopping point. Unchanged by this work.
- Defect 3 from dry run 1 (Latin-only match table under-fires on Korean body
  text) is unchanged. The script matches the table it is given.
