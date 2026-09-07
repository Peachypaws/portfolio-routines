# X Sweep — dry run 1

**Run At:** 2026-09-07 16:51 UTC · **Run Log row:** `X Sweep — dry run 1` (Routine = Manual dry run)

## Scope

| | |
|---|---|
| Channel | Curated List only (`1764453609561825483`) |
| Pull | one page, `max_results=20` → **18 posts**, `next_token` present (List not exhausted) |
| Steps run | 2, 3, 4, 5, 7, 8 |
| Steps skipped | **1a** (bookmarks) and **6** (write + bookmark removal), by instruction |
| Notion writes | one Run Log row. **Zero Signal Inbox rows. Zero TMF rows.** |

API: `GET /2/lists/{id}/tweets` → HTTP 200, `x-access-level: read`, rate limit 900 / 898 remaining / reset 1788800444. App-only bearer via the agent proxy; no token seen by the session. All three bucket-A source fetches returned HTTP 200.

## Step 2 — buckets

18 posts → **A: 3** (7, 12, 15) · **B: 9** (2, 3, 4, 8, 11, 13, 14, 16, 18) · **C: 6** (1, 5, 6, 9, 10, 17).
After the Step 5 merge of 2+4: **11 rows prepared**, representing **9 distinct stories** (see defect 1).

Accounts seen: @TheValueist, @pequityresearch, @DeItaone, @jukan05, @DrNHJ, @QQ_Timmy (6 of 8 List members).

## The 11 prepared rows

All rows: Channel = Curated List · Status = Pending Review · Classification = Unclassified · Anthropic Flag = unticked · Gate Impact / Source Discount / Second Source URL / Reviewed On / Bridged to TMF = blank.

### Bucket A — underlying source resolved, Verification = Source fetched

| # | Post | Headline | Underlying source | Publisher | Source Date | Owned / Layer |
|---|---|---|---|---|---|---|
| 1 | 7 · @jukan05 | Samsung has begun co-developing a next-generation on-device AI chip with Arm, with OpenAI named as the leading candidate for end customer. | greened.kr/news/articleView.html?idxno=349245 | 녹색경제신문 (Greened) | 2026-09-04 | None / — |
| 2 | 12 · @DrNHJ | King Slide reported August revenue of NT$6.466 billion, up 344% year over year and a record high. | money.udn.com/money/story/5710/9739533?from=edn_newestlist_rank&utm_source=chatgpt.com | 經濟日報 (Economic Daily News) | 2026-09-07 | None / — |
| 3 | 15 · @jukan05 | Samsung is using the same probe-station vendors as TSMC — FormFactor and MPI — for silicon photonics PIC wafer testing, and plans to finish PIC wafer testing within the year. | thelec.kr/news/articleView.html?idxno=61915 | 디일렉 (THE ELEC) | 2026-09-07 | TSM / Foundry |

Each fetch confirmed its post's claim. Row 1: the article body names 오픈AI as the leading end-customer candidate, matching the post's "believed to be". Row 2: 8月 64.66億, +344% confirmed in the headline. Row 3: FormFactor and MPI probe stations, and TSMC's use of the same, confirmed in the body.

### Bucket B — no link, Verification = Unverified, Underlying Source URL / Source Date blank

| # | Post | Headline | Account | Dated Claim | Translated | Owned / Layer |
|---|---|---|---|---|---|---|
| 4 | 4 + 2 (merged) | Copper set a record $14,533 a ton on the LME, up 17% over the past year, on expected US tariffs on refined copper and demand from data centers, renewables and grids. | @DeItaone, @TheValueist | Copper $14,533/ton record on the LME, +17% over the past year (unattributed Bloomberg copy) | — | None / — |
| 5 | 3 · @pequityresearch | 1.6T and 3.2T datacom optical interconnects will be strong, per an industry chart the account posted. | @pequityresearch | none | — | **COHR** / Optical Interconnect |
| 6 | 8 · @pequityresearch | Evercore ISI raised its 2027 wafer fab equipment base case to $215 billion from $180 billion. | @pequityresearch | Evercore ISI 2027 WFE base case raised to $215bn from $180bn (Evercore ISI, sell-side) | — | **ASML** / WFE / Lithography |
| 7 | 11 · @pequityresearch | Evercore ISI expects co-packaged optics at scale not before 2027/2028 on yield and cost, with AECs and pluggables remaining prominent for at least the next couple of years. | @pequityresearch | CPO at scale not before 2027/2028 (Evercore ISI, sell-side) | — | **NVDA, COHR** / — |
| 8 | 13 · @DrNHJ | King Slide reported August revenue of NT$6.466 billion, up 344.42% year over year and a record, with a Houston plant due to start mass production in September. | @DrNHJ | King Slide Aug revenue NT$6.466bn, +344.42% y/y; Jan–Aug NT$29.153bn, +163.96% y/y | Korean | **NVDA** / Compute Silicon |
| 9 | 14 · @jukan05 | CXMT remains short on LPDDR6 supply; Xiaomi's new foldable will use LPDDR6 from both CXMT and SK hynix, per sources in China. | @jukan05 | none | — | None / — |
| 10 | 16 · @jukan05 | Samsung selected the same silicon photonics test partners as TSMC — FormFactor and MPI probe stations — and plans to complete PIC wafer testing within the year; Broadcom is mentioned as a prospective customer. | @jukan05 | none | — | **TSM, AVGO** / — |
| 11 | 18 · @QQ_Timmy | Samsung Foundry has more than half of its 4nm capacity on HBM4 base dies, recently 50–60%, and expects Q3 HBM4 revenue to more than triple quarter over quarter with HBM4 above 60% of H2 HBM revenue. | @QQ_Timmy | Samsung 4nm HBM4 base-die share 50–60%; Pyeongtaek P2/P3 ~30k wpm, ~15k for HBM4 base dies; Q3 HBM4 revenue +>3x q/q; HBM4 >60% of H2 HBM revenue (Samsung guidance) | Chinese | None / — |

Publisher on every bucket-B row = `the account itself (@handle)`.

### Discarded (bucket C, 6)

| Post | Account | Why |
|---|---|---|
| 1 | @TheValueist | $FCX entry musing — digits, no owned name, no layer keyword |
| 5 | @pequityresearch | "Anyone?" — no digit in post text (the 30-40 min is in the quoted post) |
| 6 | @DeItaone | Hunter Biden $LAPTOP meme coin — digits, no match |
| 9 | @TheValueist | "$VLO $MPC $PSX $DK" — no digit |
| 10 | @TheValueist | "$VLO $MPC $PSX $DK" — no digit |
| 17 | @jukan05 | CXMT/Apple — keyword CXMT matches, **no digit in post text** (LPDDR6 is in the quoted Chinese post) |

## Step 5 — dedup and cap

- Existing Signal Inbox rows: **0**. No collision against filed rows.
- Within-run merge: posts 2 and 4 are the same unattributed Bloomberg copper copy from different accounts with the same Dated Claim → one row, both handles in Account.
- Cap: 8 bucket-B rows vs `NIGHTLY_CAP_NOLINK = 25`. **Nothing dropped.**

## Step 7 — bridge

No-op. Signal Inbox has no row with Status = "Routed to TMF", so nothing was bridged. **No write to any TMF database.**

## Defects found — for CEO ruling

1. **Split-story double row.** An account that posts the story and then replies with the bare link produces two rows. Step 5 dedups on Underlying Source URL, and the bucket-B parent has that field blank, so the pair never collides. Hit twice this run: 12+13 (King Slide) and 15+16 (Samsung silicon photonics). 11 rows represent 9 stories.
2. **Link-only replies carry no text.** Posts 12 and 15 are bare URLs, so owned-name matching has only the fetched headline. Post 12 filed with Owned-Name Hits = None on an NVDA-supplier story.
3. **Non-Latin text defeats the match table.** Post 18 (Chinese: Samsung 4nm HBM4 base dies for 輝達/博通/超微) and post 13 (Korean) match no owned name — the table is Latin-only. Post 18's own quoted post is the English version and does contain "Nvidia" and "Broadcom", but bucket-B matching reads post text only.
4. **Layer map assigns by name, not subject.** Post 15 is a silicon photonics story that gets Layer = Foundry because its single owned hit is TSM.
5. **Plurals.** "data centers" does not match keyword "data center" under whole-word matching; posts 2 and 4 qualified only once an optional trailing `s` was allowed. Plain substring is worse — in those same copper posts "Meta" matches *metal* and "ASE" matches *increase*, and "TPU" matches *output*, which would falsely tag GOOGL. **Recommend the table stay whole-word + optional trailing `s`.**
6. **Digit suffixes.** "LPDDR6" does not match keyword "LPDDR" (same shape for HBM3E, DDR5). Changed no outcome this run — post 14 also matched CXMT and SK hynix.
7. **Tracking params.** Post 12's URL carries `?from=edn_newestlist_rank&utm_source=chatgpt.com`, filed verbatim per Step 3. It will not dedup against a clean copy of the same article.
8. **Translated From under-fires.** Post 7 is an English post pointing at a Korean source; the field reads the post's script only, so it stays blank.
9. **Anthropic Flag.** Unticked on all 11. Post 7's source page carries 앤트로픽 in a related-links sidebar — not the Latin string, and not in the body.
10. **Dedup tie-break unspecified.** Step 5 says merge to one row but not which Post URL survives. Used the earlier post (@DeItaone, 15:36:24Z).
11. **High-value source hidden.** The copper story is Bloomberg copy pasted with no link by both accounts. It can only ever be filed Unverified.
12. **Unused options.** Layer has an "Outside layer map" option and Owned-Name Hits has "None", but Step 4 says leave Layer blank and never assigns either. Confirm intent.

## Notes on how this row was filed

- `Routine = Manual dry run`, not `X Sweep` — so this row does not enter the X Sweep run history.
- `Rows Filed = 0`, because Step 6 was skipped and nothing was written. The 11 rows are recorded here and in the run row's Notes only.
- The High-Water Mark is recorded but flagged **not valid** for the first scheduled run: this was one capped page, not an exhaustive pull.
