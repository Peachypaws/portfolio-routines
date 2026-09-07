# X Sweep — dry run 3 (2026-09-07)

Prompt: `prompts/x-sweep.md` v1.4. Script: `scripts/x_sweep.py`.
Purpose: prove the script → model handoff. One page only, on purpose.

Run row: https://app.notion.com/p/3d431d4f7b778143ac90c4efffd52bad

## Command

```
python3 scripts/x_sweep.py --max-pages 1 \
  --pages-dir <scratchpad>/pages \
  --existing scripts/fixtures/dry-run-2-signal-inbox.json \
  --out candidates.json
```

Step 1b: the last run row was a manual dry run, so the high-water mark was
treated as absent and one page taken, as the prompt directs.

`candidates.json` is committed at `scripts/fixtures/dry-run-3-candidates.json`.
The 17 fetched pages (3.3 MB) were left in the container and are NOT committed.

## Mechanical half — what the script produced

| | |
|---|---|
| Pages pulled | 1 (list NOT exhausted; stopped on the page limit, `next_token` present) |
| Posts pulled | 87 |
| Oldest `created_at` | 2026-09-06T15:23:00Z |
| Newest `created_at` | 2026-09-07T20:57:07Z |
| **Window one page covers** | **~29.5 hours** |
| Same-author reply merges (Step 2) | 15 |
| Buckets pre-dedup | A 17 / B 41 / C 14 discarded |
| Step 6a source-URL clusters within run | 0 |
| Already filed against the 62 dry-run-2 rows | 37 |
| Candidates in `candidates.json` | 21 (uncapped) |
| Fetch failures | 1 (`https://300308.SZ`) |
| Parse failures | 1 (Meritz PDF, short-circuit — expected) |
| Rate limit | limit 900, remaining 899, access `read` |

Newest post ID / high-water mark: `2097066657378107786`.

## Model half

**Step 5.** Headline and Dated Claim written for all 21 candidates.

**Step 6b — claim-level dedup.** Two clusters *inside* this run:

1. Jensen Huang's GPT-6 Astra GPU count — @DrNHJ + @jukan05 (an RT).
2. The GF Securities memory tech-tour note — @jukan05 + @DrNHJ + @QQ_Timmy,
   in English, Korean and Chinese.

**Neither cluster was cross-bucket.** Every member was bucket B with no
resolved source URL, so the cross-bucket rule had nothing to protect. The rule
was not exercised this run.

A further five candidates carried a Dated Claim identical to a row already in
the inbox (Goldman optical transceivers; Amazon/AWS $220bn capex; Samsung 4nm
HBM4 base dies; plus both clusters above). They were dropped rather than
re-filed — see decision 2 below. The existing rows already carried every
handle involved, so no Account append was needed.

21 candidates → 13 rows.

**Step 6c — cap.** Did not fire. 11 bucket-B rows with Owned-Name Hits = None,
against `NIGHTLY_CAP_NOLINK` = 25. Rows kept on an owned-name hit: 2 (NVDA,
MU). Rows kept under the cap: 11. Nothing capped.

**Step 7a.** 13 rows, one batched call. The 62 dry-run-2 rows were left alone.

**Step 7c.** No-op, as expected — 0 rows at Status = "Routed to TMF".

## Decisions I had to make rather than follow

1. **`https://300308.SZ` — the DNS fallback did not fire.** X auto-linked the
   Shenzhen ticker code `300308.SZ` in @QQ_Timmy's Innolight post into a URL,
   and the script emitted the post as bucket A with that as the Underlying
   Source URL. Dry-run-2 decision (c) exists exactly for this and should have
   demoted it to bucket B. It did not, because `_is_dns_failure` never sees a
   DNS error behind this session's HTTPS CONNECT proxy: the proxy answers a
   non-resolving host with `OSError: Tunnel connection failed: 502 Bad
   Gateway`. Confirmed separately that `300308.SZ` does not resolve. I filed
   the post as bucket B by hand. **This is a script bug in any proxied
   environment, not a one-off.**

2. **Extended 6b to match against existing rows, not just within the run.**
   As written, 6b is within-run only, and 6a's cross-run arm matches on URLs
   only. So a claim pasted link-free by a new account on a later day re-files
   forever — the inbox has no cross-run defence against no-link duplicates at
   all. Five of the 21 would have been duplicates of dry-run-2 rows. The user's
   instruction to "dedup against them" settled it, but the prompt does not say
   this.

3. **Excluded Dated Claim = "none" from 6b.** Six candidates carried "none".
   Read literally, "the same Dated Claim from different accounts → one row"
   collapses six unrelated posts into one. "none" is the absence of a claim,
   not a claim.

4. **Cluster 2's members quote the same note at different lengths.**
   @jukan05's copy of the GF Securities note omits the HBM4 $/Gb figures that
   the Korean and Chinese copies carry. A literal string comparison of Dated
   Claim would not have merged them. I merged on *same underlying claim* and
   took the fullest version's figures for the surviving row.

5. **Translated From left blank for English posts.** The schema offers
   "None — English"; the prompt says "otherwise blank". I followed the prompt.
   Several kept rows (#5 HIWIN, #6 Meritz) are plainly English renderings of a
   Chinese or Korean original but do not *say* they are translations, so the
   "or says it is a translation" arm did not fire.

## What was awkward to work from in `candidates.json`

- **No `layer_hits` in the record.** The script computes them to run the Step
  3B gate, then throws them away. They are the fastest signal for *why* a
  no-link post survived, and for a bucket-B row they are often the only
  vocabulary the Headline can draw on. Emitting them (as a working `_` field,
  not a Layer) would cost nothing.

- **No record of which string satisfied the digit gate.** Row #20
  (@wallstengine, "KING CHARLES III'S AI MEETING LIST") has no digit anywhere
  in the post text. It passed Step 3B on the digits inside the t.co shortlink
  `https://t.co/w9kVRQr8iC`. That is a spurious pass, and nothing in the
  output makes it visible. The digit gate should ignore URL text — and the
  record should say what matched.

- **`raw_post_text` concatenates merged posts with `\n\n---\n\n`, but the
  per-post boundaries are gone.** With 15 merges in this run, when a merged
  candidate carries two figures I cannot tell which post each came from, so I
  cannot attribute the Dated Claim to the right Post URL. `_post_ids` lists
  the IDs but not which text belongs to which.

- **No `_page_body_excerpt` for bucket A.** The Anthropic Flag is computed
  against the fetched body, and Verification is left null for the model to
  decide from "did the fetch confirm the claim" — but the body text is not in
  the file. I would have had to re-read the saved HTML off disk to answer a
  question the script explicitly delegated to me. (Moot this run: the single
  surviving bucket-A row turned out to be decision 1 above.)

- **`_quoted_text` is present but the quoted post's URL and author are not.**
  Several claims live entirely in the quoted post (#8, #15, #16). Naming the
  interested party in the Dated Claim means naming whoever wrote the quoted
  post, and the record does not say who that is.

- **Nothing carries the "already filed" reason back to the survivor.** 37
  candidates were dropped at 6a; the meta lists them, but a kept row that is
  the *same story* as a dropped one gives no hint. That is what made the five
  cross-run claim duplicates a manual scan of 62 existing Dated Claims.

- **Minor:** `verification: null` means "model decides" and
  `verification: "Unverified"` means "forced". Both are legal; the null is
  easy to read as a missing field.

## Rows written

| Account | Post | Notion |
|---|---|---|
| @pequityresearch | 2096715060852793378 | https://app.notion.com/p/3d431d4f7b7781f49aa8fafb0b995479 |
| @jukan05 | 2096731794704093565 | https://app.notion.com/p/3d431d4f7b7781db8432de52fca83684 |
| @pequityresearch | 2096739471869833462 | https://app.notion.com/p/3d431d4f7b7781548d7de76ab78097fd |
| @jukan05 | 2096753462038138969 | https://app.notion.com/p/3d431d4f7b7781ba9ea5ed54dc611868 |
| @dnystedt | 2096772052619510166 | https://app.notion.com/p/3d431d4f7b7781c9b3eeebc782310c3d |
| @pequityresearch | 2096789028506849617 | https://app.notion.com/p/3d431d4f7b7781baa522c1e715c0da05 |
| @QQ_Timmy | 2096823353869054037 | https://app.notion.com/p/3d431d4f7b77814399e3f971cc54ef1b |
| @QQ_Timmy | 2096826615594672511 | https://app.notion.com/p/3d431d4f7b7781819788eb7b34978a30 |
| @jukan05 | 2096901251443368260 | https://app.notion.com/p/3d431d4f7b7781ef8c54e625f49a1f09 |
| @jukan05 | 2096934443026153775 | https://app.notion.com/p/3d431d4f7b778174b3dfd072bddc28b2 |
| @pequityresearch | 2096983580215812188 | https://app.notion.com/p/3d431d4f7b77810e9860c03959332b03 |
| @wallstengine | 2097053208636199267 | https://app.notion.com/p/3d431d4f7b77819e9476fea79cccd923 |
| @pequityresearch | 2097066657378107786 | https://app.notion.com/p/3d431d4f7b7781c391d0f0bef42a0504 |

## Note on the repository

Prompt v1.4 was read from `44ad47f`, which is the tip of `main`. This note is
committed on `claude/quirky-keller-l4h9ss`, one commit ahead of it.
