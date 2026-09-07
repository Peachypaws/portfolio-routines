# X Sweep — dry run 2

**Run At:** 2026-09-07 20:19 UTC · **Run Log row:** [`X Sweep — dry run 2`](https://app.notion.com/p/3d431d4f7b7781278d7af78302c31f04) (Routine = Manual dry run)

## Scope

| | |
|---|---|
| Channel | Curated List only (`1764453609561825483`) |
| Pull | 3 pages, `max_results=100` → **265 posts**. `next_token` still present → **List not exhausted** |
| High-water mark | none existed. The 3-page override replaced the prompt's one-page fallback |
| Steps run | 2, 3, 4, 5, 6, 7a, 7c, 8 — **in full, including the Signal Inbox write** |
| Steps skipped | **1a** (bookmarks) and **7b** (bookmark removal), by instruction |
| Notion writes | **62 Signal Inbox rows** + 1 Run Log row. **Zero TMF rows.** |

API: `GET /2/lists/{id}/tweets` ×3 → HTTP 200 each, `x-access-level: read`, limit 900, remaining 899 → 898 → 897, reset 1788811242. App-only bearer via the agent proxy; no token seen by the session.

**Cost:** the X API returned no cost header on any of the three calls, and this session has no console access. The only usage signal available is the rate-limit counter: **3 of 900 requests** in the 15-minute window. Cost per request is not reported and I am not going to guess it.

Accounts seen: all 8 List members — @DrNHJ, @pequityresearch, @jukan05, @QQ_Timmy, @dnystedt, @TheValueist, @wallstengine, @DeItaone.

## Step 2 — merges

**30 same-author reply merges**, collapsing 265 posts into 214 candidates.

| Pattern | Count | Accounts |
|---|---|---|
| Story post + reply carrying the bare link | 24 | @DrNHJ (17), @jukan05 (7) |
| Thesis post + 8 chart-image replies | 3 chains (27 posts) | @TheValueist — $PBF, $PARR, $DK |
| Story + author's own follow-on commentary | 3 | @dnystedt — TSMC 3nm, Winbond, UMC |

The 24 story+link chains are exactly what defect 1 from dry run 1 predicted. Step 2 now catches them before bucketing, so they file as one bucket-A row instead of a bucket-A/bucket-B pair.

## Step 3 — buckets

Before dedup: **A 38 · B 92 · C 84** (214 candidates).
After dedup and one reclassification: **A 37 · B 77 · C 84**.

## Step 6 — dedup

Signal Inbox was **empty** at run start, so there was no collision against filed rows and no `already filed` discards.

**11 within-run clusters collapsed 26 candidates into 11 rows.** Earliest post wins the Post URL in every case.

| # | Story | Posts merged (earliest first) |
|---|---|---|
| 1 | Samsung Foundry HBM4 on 4nm base dies | @jukan05 05:45:59 + @QQ_Timmy 08:59:10 |
| 2 | Amazon capex $220bn / AWS rack pull-in | @dnystedt 00:28:24 + @DrNHJ 02:46:57 + @QQ_Timmy 05:53:00 |
| 3 | GF Securities DRAM tech tour | @pequityresearch 01:26:07 + @jukan05 02:05:49 + @DrNHJ 02:37:31 + @QQ_Timmy 03:28:11 |
| 4 | Korean government Vera Rubin rack budget | @pequityresearch 00:28:00 + @DrNHJ 02:51:39 |
| 5 | Goldman optical transceiver forecast raise | @pequityresearch 03:33 + @DrNHJ 04:26 |
| 6 | Copper record $14,533/t | @DeItaone 15:36:24 + @TheValueist 16:40:32 |
| 7 | Jensen Huang, 100K+ Grace Blackwell | @wallstengine 09-06 20:46 + @DrNHJ 22:02 + @jukan05 22:18 |
| 8 | Dell/CoreWeave first Vera Rubin NVL72 racks | @DrNHJ 09-04 23:17 + @QQ_Timmy 09-05 04:40 + @wallstengine 09-05 13:20 |
| 9 | Hopper price decline vs Blackwell | @pequityresearch 09-05 22:20 + @QQ_Timmy 09-06 08:53 |
| 10 | Anthropic IPO mid-October | @wallstengine 09-04 23:13 + @DrNHJ 09-05 00:29 |
| 11 | Meritz Astra / memory note | @DrNHJ 09-06 23:25 + @jukan05 09-07 00:12 |

Clusters 2, 4, 10 and 11 each joined a bucket-B post to a bucket-A post. See decision (f).

## Step 6 — cap

77 bucket-B rows against `NIGHTLY_CAP_NOLINK = 25`. Kept owned-name hits first, then most recent.

Post-dedup bucket B splits **49 with an owned-name hit / 28 without**.

- All 25 kept rows carry an owned-name hit.
- **52 dropped** = **24 rows that carried an owned-name hit** + all **28** no-hit rows.
- Every dropped post is listed by @handle and status ID in the Run Log row's Notes.

The cap is where this run loses the most. 52 posts dropped against 25 kept means the cap is doing more work than the filter is. Worth a CEO ruling on whether 25 is right for a three-page pull.

## The 62 rows filed

All rows: Channel = Curated List · Status = Pending Review · Classification = Unclassified · **Layer blank** · Gate Impact / Source Discount / Second Source URL / Reviewed On / Bridged to TMF blank.

### Bucket A — 37 rows, underlying source resolved

| # | Account(s) | Headline | Publisher | Source Date | Verification | Owned | Notion |
|---|---|---|---|---|---|---|---|
| A01 | @jukan05 | Samsung co-developing on-device AI chip with Arm, OpenAI believed the end customer | 녹색경제신문 | 2026-09-04 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b778168a5edf988dec1bc6c) |
| A02 | @DrNHJ | King Slide August revenue NT$6.466bn, +344% y/y, record | 經濟日報 | 2026-09-07 | Source fetched | NVDA | [row](https://app.notion.com/p/3d431d4f7b77810cad80c93e374705db) |
| A03 | @jukan05 | Samsung picks TSMC's silicon photonics test partners — FormFactor, MPI | 디일렉 | 2026-09-07 | Source fetched | TSM, AVGO | [row](https://app.notion.com/p/3d431d4f7b7781e4bb3cc1d8f8596313) |
| A04 | @QQ_Timmy | Counterpoint: robotaxi services $168bn by 2035, ~3.6m fleet | Counterpoint Research | 2026-06-16 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781ed99b6c9c3d9210bdd) |
| A05 | @TheValueist | Ship fuel shortage looms as war-strained refiners favour other products | Reuters | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b7781139fb2ce7731e98222) |
| A06 | @jukan05, @QQ_Timmy | Over half of Samsung Foundry 4nm capacity on HBM4 base dies, 50–60% | ZDNet Korea | 2026-09-07 | Source fetched | NVDA, AVGO | [row](https://app.notion.com/p/3d431d4f7b7781cebc71f3e20f218f87) |
| A07 | @DrNHJ | Anthropic compute contracts $517bn over 11 months, +14.8GW | 조선비즈 | 2026-09-07 | Source fetched | MU, NVDA, AVGO, GOOGL | [row](https://app.notion.com/p/3d431d4f7b77817e9006e4d744f0cc3e) |
| A08 | @DrNHJ | xAI planning a Doosan-equipped combined-cycle plant for Memphis | 데일리안 | — | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b77814896dfe3c1733b1f27) |
| A09 | @DrNHJ | Goldman Samsung NDR: memory tightening 2027, persisting to 2028 | Telegram channel | — | Source fetched | MU | [row](https://app.notion.com/p/3d431d4f7b77818ab00fd8ef2bdc4db1) |
| A10 | @dnystedt, @DrNHJ, @QQ_Timmy | Amazon capex to $220bn from $200bn; AI rack pull-in | 經濟日報 | 2026-09-07 | Source fetched | NVDA, TSM | [row](https://app.notion.com/p/3d431d4f7b77813e8797ea24d94ad000) |
| A11 | @pequityresearch, @DrNHJ | Korea budgets ₩27.5bn per Vera Rubin rack | 머니투데이 | 2026-09-07 | Source fetched | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781a59fa0d5f46a7d2b95) |
| A12 | @DrNHJ | Power transformer / GSU lead times still 2–3 years | MarketScale | 2026-09-06 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781949cefdc8a302f8a9d) |
| A13 | @DrNHJ | KB: Samsung/SK hynix memory inventory under 10 days | 한국경제 | — | Source fetched | MU | [row](https://app.notion.com/p/3d431d4f7b778143961dcf61cf52782d) |
| A14 | @DrNHJ | Iljin Electric: power equipment boom runs another decade | 한국경제 | 2026-09-07 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781c6afd6dbb4e181e187) |
| A15 | @DrNHJ, @jukan05 | Meritz: Astra launch supports a memory share rebound | 메리츠증권 | 2026-09-07 | Unverified | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781a299f0e7b0238d6a40) |
| A16 | @jukan05 | SK hynix raising 1c DRAM share; main process early next year | 조선비즈 | 2026-09-04 | Source fetched | MU, NVDA, GOOGL | [row](https://app.notion.com/p/3d431d4f7b77810da0cbcf7f4cc12736) |
| A17 | @TheValueist | OpenClaw 2026.9.2 adds a triage tool | OpenClaw | — | Source fetched | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b778153b055e0962277ea6e) |
| A18 | @pequityresearch | Third-party site for X's Original Content Rewards picks | ocr-helper.grok.me | — | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b778147b3bad10501271ff2) |
| A19 | @dnystedt | Tokyo Electron SEMICON Taiwan 2026 IR tech talk deck | Tokyo Electron | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b77817b8a32c959dd13bea3) |
| A20 | @DrNHJ | Japan AI data centre capacity >4x by mid-2030s on ~¥10tn | 日本経済新聞 | 2026-09-05 | Source fetched | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781e1b791ef98ea351b1e) |
| A21 | @jukan05 | Irrational Analysis Hot Chips 2026 recap | Irrational Analysis | — | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781068fc7e527b580ed5c) |
| A22 | @pequityresearch | Goldman optical networking report published free | Goldman Sachs | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b77810895c8e6fb297603a3) |
| A23 | @DrNHJ | GPU rental prices 6 Sep: B200 $6.42/hr, H100 $3.06/hr | 新浪财经 | — | Unverified | NVDA | [row](https://app.notion.com/p/3d431d4f7b7781619658f69b24ada408) |
| A24 | @jukan05 | MoneyLink item; article body not retrievable | MoneyLink 富聯網 | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b7781b2bd57d9cc591d5665) |
| A25 | @DrNHJ | TSMC: 20 fabs under construction, still short of AI demand | 工商時報 | 2026-09-06 | Source fetched | MU, NVDA, TSM | [row](https://app.notion.com/p/3d431d4f7b7781289980d24e6f97556b) |
| A26 | @TheValueist | Pelican-SVG grid across Astra reasoning levels | Simon Willison's Weblog | 2026-09-04 | Source fetched | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781f4ad7ad0329977f823) |
| A27 | @TheValueist | OpenAI financial-services customer page | OpenAI | — | Unverified | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781c6983bd2755d27e37a) |
| A28 | @DrNHJ | Goldman Delta One head calls Astra a standout | 华尔街见闻 | — | Unverified | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781b8aac1e1a36b6e4ad7) |
| A29 | @jukan05 | Chinese equipment makers localising into advanced packaging | 전자신문 | 2026-09-05 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781edb43fdb0162254069) |
| A30 | @QQ_Timmy | Gavin Baker on AI data centres and blue-collar wages | Business Insider | 2026-09-02 | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781c59fefcec0d1dafde7) |
| A31 | @dnystedt | Winbond August revenue NT$27.3bn, +289.4% y/y | Winbond | — | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b778146bdb4ed659643339b) |
| A32 | @dnystedt | UMC August revenue NT$25.05bn, +30.7% y/y | UMC | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b77812c830befd5b1f9f09e) |
| A33 | @DrNHJ | US and China preparing a mid-September AI safety dialogue | Reuters | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b77819992f0e3d32be4918d) |
| A34 | @wallstengine, @DrNHJ | Anthropic IPO marketing shifts to mid-October | Reuters | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b7781669d55c6e6fcc44c91) |
| A35 | @pequityresearch | Aurelion Research Buy initiation on Tradeweb (Drive file) | Aurelion Research | 2026-07-24 | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b7781b990d6c738c3d77506) |
| A36 | @pequityresearch | Asset Alliance Investment Group research collective | Asset Alliance Investment Group | — | Source fetched | None | [row](https://app.notion.com/p/3d431d4f7b7781369a26f2ff1aa33f6b) |
| A37 | @wallstengine | Anthropic exploring in-house payments and billing | The Information | — | Unverified | None | [row](https://app.notion.com/p/3d431d4f7b77818897d3c8eae998e24d) |

### Bucket B — 25 rows, no link, all Verification = Unverified

Publisher on every row = the account itself. Underlying Source URL and Source Date blank.

| # | Account(s) | Headline | Owned | Notion |
|---|---|---|---|---|
| B01 | @pequityresearch | Goldman: global server revenue ~$1.1tn in 2028, mostly NVL72 | NVDA | [row](https://app.notion.com/p/3d431d4f7b77819d9505fe5bd8f5911c) |
| B02 | @pequityresearch | Goldman: Samsung revenue >1tn KRW in 2028E, +47% CAGR | MU | [row](https://app.notion.com/p/3d431d4f7b77817299aaf1d1b444d700) |
| B03 | @pequityresearch | 1.6T and 3.2T datacom optical interconnects will be strong | COHR | [row](https://app.notion.com/p/3d431d4f7b7781b397cbf445778c7c76) |
| B04 | @pequityresearch | Evercore ISI: 2027 WFE base case to $215bn from $180bn | ASML | [row](https://app.notion.com/p/3d431d4f7b778102bc5cc4315f4ad7a4) |
| B05 | @pequityresearch | Evercore ISI: CPO at scale not before 2027/2028 | NVDA, COHR | [row](https://app.notion.com/p/3d431d4f7b77812590e4f876d0a7093f) |
| B06 | @QQ_Timmy | UBS cuts Largan to Sell, NT$5,000 target, on CPO re-rating | NVDA, COHR | [row](https://app.notion.com/p/3d431d4f7b7781d798a8d9aaed9c1ed3) |
| B07 | @TheValueist | Asian chip stocks rally after Astra; KB bullish on memory | TSM | [row](https://app.notion.com/p/3d431d4f7b77813ba3b6e701b17349b2) |
| B08 | @QQ_Timmy | NYT: blacklisted Inspur buying US AI chips via Aivres, ~$5.6bn | NVDA | [row](https://app.notion.com/p/3d431d4f7b7781e6a253cbf410ee78fc) |
| B09 | @pequityresearch | Account solicits a collaborative Substack piece on memory/optics | MU | [row](https://app.notion.com/p/3d431d4f7b77813b9ea2f26ccc2b0352) |
| B10 | @pequityresearch, @DrNHJ | Goldman raises optical transceiver shipments 21/31/31%, 1.6T+ 29/61/50% | NVDA, COHR | [row](https://app.notion.com/p/3d431d4f7b778141baf5e57304d4b35c) |
| B11 | @TheValueist | Nothing trained on Rubin yet, let alone Feynman | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b77814abb80ea2edfa7b8de) |
| B12 | @pequityresearch, @jukan05, @DrNHJ, @QQ_Timmy | GF Securities turns positive on DRAM; blended px ~+10% q/q in 4Q26 | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b778177b5d9f43e25b04147) |
| B13 | @dnystedt | Graphics card prices rising; Nvidia cut consumer GPU shipments 15–20% | NVDA | [row](https://app.notion.com/p/3d431d4f7b7781469d3df81dd1094cdf) |
| B14 | @dnystedt | Taiwan fab builders' backlog >NT$880bn, visibility to 2027 | MU, TSM | [row](https://app.notion.com/p/3d431d4f7b77815f8704da0d32fc7bc0) |
| B15 | @QQ_Timmy | 7 Sep roundup: Aspeed BMC +20% from December; Largan downgrade | NVDA, AVGO | [row](https://app.notion.com/p/3d431d4f7b77815e8875e0d6f93509a4) |
| B16 | @dnystedt | TSMC 3nm output passes 5nm, >NT$400bn, ~30% of revenue | NVDA, TSM | [row](https://app.notion.com/p/3d431d4f7b7781fbbaaae1a6036e21b2) |
| B17 | @QQ_Timmy | Taiflex approves NT$2bn capex; PTFE CCL capacity early 2027 | NVDA | [row](https://app.notion.com/p/3d431d4f7b7781c2b553c9b6b79fa17a) |
| B18 | @pequityresearch | Ciena slide: actual CSP capex outpacing forecasts | GOOGL | [row](https://app.notion.com/p/3d431d4f7b778179828dc524f2d6994a) |
| B19 | @wallstengine, @DrNHJ, @jukan05 | Jensen Huang: Astra trained on 100K+ Grace Blackwell NVLink72 | NVDA | [row](https://app.notion.com/p/3d431d4f7b77815e8245e7661eb7a7cc) |
| B20 | @pequityresearch | 1.6T transceiver market $39bn by 2030, ~35% annual growth | NVDA, COHR | [row](https://app.notion.com/p/3d431d4f7b778155b9d7c71d8471660a) |
| B21 | @pequityresearch | Mirae: SK hynix peak operating margin 79.1% in 2027 | MU | [row](https://app.notion.com/p/3d431d4f7b77818d817fd14376538f7e) |
| B22 | @TheValueist | One-line post pairing DRAM and refining positioning | MU, NVDA | [row](https://app.notion.com/p/3d431d4f7b7781ceb567c1da13cf2540) |
| B23 | @pequityresearch | UBS: DRAM/NAND EBITDA nearly 10x industry capex | MU | [row](https://app.notion.com/p/3d431d4f7b7781a098e4d2a8b6eaa9c2) |
| B24 | @dnystedt | Epoch AI: Huawei almost certainly will not catch Nvidia by 2030 | NVDA | [row](https://app.notion.com/p/3d431d4f7b7781d1a6b4e89be1ea3c75) |
| B25 | @QQ_Timmy | Nvidia cuts Rubin Ultra HBM 12-Hi → 8-Hi on $/bandwidth | NVDA | [row](https://app.notion.com/p/3d431d4f7b77816aa1b4fa6305d264b4) |

## Anthropic Flag

Ticked on 5 rows: A07 (compute contracts), A11 (post body references Anthropic's Mythos release), A33 (post body alleges Moonshot distilled an Anthropic model), A34 (IPO timing), A37 (in-house payments).

A11 and A33 would both have been missed by a headline-level read — the trigger string is buried in the note body. That is the flag working as intended.

## Step 4 — fetch failures (9 of 38)

| URL | Result |
|---|---|
| reuters.com ×3 (ship fuel, US-China AI safety, Anthropic IPO) | HTTP 401 |
| openai.com financial-services page | HTTP 403 |
| umc.com monthly sales revenue | HTTP 403, Cloudflare interstitial |
| theinformation.com Anthropic payments | HTTP 403, Cloudflare interstitial |
| goldmansachs.com optical networking report.pdf | HTTP 200 but a 572-byte stub, no report body |
| finance.sina.com.cn GPU rental prices | connection failed, no HTTP response |
| `https://300308.SZ` | not a resolvable URL — see decision (c) |

All nine filed Unverified with the URL kept, per Step 4.

## Step 7c — bridge

**No-op.** Zero Signal Inbox rows with Status = "Routed to TMF". No write to any TMF database. No blocked bridges.

## Decisions taken, not followed from the prompt

1. **(a) Digit-led suffix only.** The prompt's suffix rule ("a term ending in a letter also matches a trailing digit/letter suffix") was narrowed to suffixes that *start with a digit*. All three of the prompt's own examples (HBM3E, HBM4, LPDDR6, DDR5) are digit-led. An unrestricted alphanumeric suffix makes `Meta` match *metal*, `PIC` match *Picture*, `UPS` match *upside* and `ASE` match nothing but noise — which directly contradicts the barred-substring examples two lines above it in the same prompt. **This needs a ruling; it changes what gates bucket B.**
2. **(b) Asymmetric leading boundary.** Non-letter for letter-initial terms, so `500MW` matches `MW`. Non-alphanumeric for digit-initial terms, so `12nm` does *not* match `2nm`. Side effect: `MWh` and `GWh` do not match `MW`/`GW`.
3. **(c) Bogus expanded URL.** X expanded the in-text ticker `300308.SZ` into `https://300308.SZ`. Reclassified that candidate A → B rather than file a URL that cannot exist.
4. **(d) Shortener resolved.** A `tinyurl.com` link was filed at its resolved target (`home.imeritz.com/.../20260907073604796K_02.pdf`), not the shortener. A shortener is not a source and will never dedup.
5. **(e) Fragment stripped.** `#from=ios` removed from the wallstreetcn URL. The prompt lists `from` as a query parameter; this was a fragment. Same tracking intent.
6. **(f) Cross-bucket merge keeps the source URL.** Where dedup joined a bucket-B post to a bucket-A post (clusters 2, 4, 10, 11), the surviving row kept the bucket-A Underlying Source URL *and* the earliest post's Post URL. Step 6 only specifies which Post URL survives; read literally it would have discarded a resolved source in favour of a no-link row. **This is the fix for dry run 1's defect 1 and should be written into the prompt.**
7. **(g) "Source fetched" means read and confirmed.** PDFs that downloaded cleanly but could not be read (Meritz, Tokyo Electron) are Unverified, not Source fetched.
8. **(h) Translated From left blank** for English posts rather than set to "None — English", per the prompt. The option stays unused — dry run 1's defect 12 is still open.

## Defects — status against dry run 1

| # | Dry run 1 defect | Status |
|---|---|---|
| 1 | Split-story double row | **Fixed** by Step 2 merge + decision (f). Only works when the reply lands in the same pull. |
| 2 | Link-only replies carry no text | **Fixed** — merged text now carries the parent's body. |
| 3 | Non-Latin text defeats the match table | **Still open.** Chinese posts naming 輝達/博通 match. Korean posts naming 엔비디아 in body text matched only via the `$NVDA` cashtag. |
| 4 | Layer assigned by name, not subject | Not applicable — Layer left blank on all 62 rows. |
| 5 | Plurals | **Fixed** — optional trailing `s` implemented. |
| 6 | Digit suffixes | **Fixed**, but narrowed — see decision (a). |
| 7 | Tracking params | **Fixed** — 5 URLs cleaned. |
| 8 | Translated From under-fires | **Still open.** English posts pointing at Korean sources stay blank. |
| 9 | Anthropic Flag | Working — 5 rows ticked, 2 of them from buried body text. |
| 10 | Dedup tie-break unspecified | **Still open in the prompt.** Used earliest post throughout; recommend writing that in. |
| 11 | High-value sources filed link-free | **Still open.** The copper story was again pasted with no link by two accounts, and was dropped by the cap this time. |
| 12 | Unused Layer / Owned-Name options | **Still open.** "Outside layer map" never used; "None" used on 14 rows. |

## New for CEO ruling

1. **The cap is the binding constraint, not the filter.** 77 bucket-B rows against a cap of 25. 24 rows carrying a live owned-name hit were dropped. On a nightly one-page run that never happens; on a three-page catch-up it drops more signal than it keeps.
2. **The List was not exhausted at 3 pages.** 265 posts across roughly 3 days of List activity, with `next_token` still live. A first scheduled run with no high-water mark will need more than 3 pages, or an explicit "start from here" mark.
3. **Bucket C is 84 of 214 candidates (39%).** Mostly retweets of chart images, one-line reactions, and cashtag-only posts. That is the filter working, but worth confirming nothing valuable sits in there.
4. **Suffix-matching rule needs to be written down properly** — see decision (a). Two readings of one sentence give materially different bucket-B sets.

## Notes on how this row was filed

- `Routine = Manual dry run`, not `X Sweep` — this row does not enter the X Sweep run history.
- `Rows Filed = 62` and those rows are **live in the Signal Inbox** at Status = Pending Review. This run wrote to Notion; dry run 1 did not.
- `Discarded = 136` = 84 bucket C + 52 over cap. The 15 dedup-collapsed candidates are counted as merges, not discards.
- High-water mark recorded as `2097042216405631260`, flagged in the row as **not a clean stopping point** — the run stopped at the page override, not at the end of the List.
