#!/usr/bin/env python3
"""Offline tests for scripts/x_sweep.py. No network, no API calls.

Run: python3 scripts/test_x_sweep.py

Scope note. Dry run 2's raw inputs - the 265 pulled posts and the saved source
pages - lived in that session's container and are gone; they were never
committed. So this is not an end-to-end replay of dry run 2. What it does:

  1. exercises every deterministic rule against the worked examples in
     prompts/x-sweep.md and both dry-run notes;
  2. runs the script end to end, offline, over a synthetic pull built to the
     shapes dry run 2 described (same-author link reply, cross-bucket dedup,
     bogus expanded URL, PDF, tracking params);
  3. replays Step 6's cap over dry run 2's real post-dedup bucket-B
     distribution (49 with an owned-name hit / 28 without) under both the v1.2
     and the v1.3 rule, and reports the difference;
  4. checks the 62 rows dry run 2 actually filed - read back from Notion into
     scripts/fixtures/dry-run-2-signal-inbox.json - against the script's
     record contract, field by field.
"""

import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import x_sweep as xs  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "dry-run-2-signal-inbox.json")

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append("%s %s" % (label, detail))


def eq(got, want, label):
    check(got == want, label, "-> got %r, want %r" % (got, want))


# --------------------------------------------------------------------------
# 1. Matching rules
# --------------------------------------------------------------------------

def test_matching():
    m = xs.Matcher()

    # Prompt v1.3 rule 1, positive: suffix that starts with a digit.
    for text, want in [("HBM3E base dies", ["HBM"]), ("HBM4 ramp", ["HBM"]),
                       ("LPDDR6 supply", ["LPDDR"]), ("DDR5 pricing", ["DDR"])]:
        hits = m.layer_hits(text)
        check(all(w in hits for w in want), "suffix-digit", "%r -> %r" % (text, hits))

    # Prompt v1.3 rule 1, negative: suffix that starts with a letter.
    for term, text in [("Meta", "metal prices"), ("PIC", "Picture this"),
                       ("ASE", "ASEAN summit"), ("ASE", "an increase"),
                       ("TPU", "the output"), ("UPS", "upside risk")]:
        rx = xs._build_term_regex(term)
        check(rx.search(text) is None, "suffix-letter-barred",
              "%r must not match %r" % (term, text))

    # Base term still matches on its own and in the plural.
    for term, text in [("Meta", "Meta said"), ("PIC", "PIC wafer testing"),
                       ("ASE", "ASE Technology"), ("HBM", "HBMs shipped")]:
        rx = xs._build_term_regex(term)
        check(rx.search(text) is not None, "base-term", "%r in %r" % (term, text))

    # A term ending in a digit gets no suffix extension.
    eq(xs._build_term_regex("N2").search("N2P node"), None, "digit-tail-no-suffix")
    check(xs._build_term_regex("N2").search("N2 node") is not None, "digit-tail-base")

    # Optional trailing 's' (dry run 1, defect 5).
    check("data center" in m.layer_hits("hyperscale data centers"), "plural-s")

    # Asymmetric leading boundary (dry run 2, decision (b)).
    check("MW" in m.layer_hits("a 500MW campus"), "lead-letter-term-after-digit")
    check("2nm" not in m.layer_hits("a 12nm node"), "lead-digit-term-after-digit")
    check("MW" not in m.layer_hits("300 MWh of storage"), "MWh-does-not-match-MW")
    check("DDR" not in m.layer_hits("LPDDR6 only"), "DDR-not-inside-LPDDR6")

    # Owned names, Latin and CJK.
    eq(m.owned_hits("Nvidia and Micron"), ["MU", "NVDA"], "owned-latin")
    eq(m.owned_hits("輝達與台積電"), ["NVDA", "TSM"], "owned-cjk-substring")
    eq(m.owned_hits("엔비디아 실적"), ["NVDA"], "owned-hangul")
    eq(m.owned_hits("$GOOGL up"), ["GOOGL"], "owned-cashtag")
    eq(m.owned_hits("nothing here"), [], "owned-none")

    # Barred substring: 'Meta' inside 'metal' must not tag anything.
    eq(m.owned_hits("copper and metal demand"), [], "no-false-owned-hit")

    # Translated From reads the post's script.
    eq(xs.detect_script("삼성 파운드리"), "Korean", "script-korean")
    eq(xs.detect_script("東京エレクトロン"), "Japanese", "script-japanese")
    eq(xs.detect_script("台積電產能"), "Chinese", "script-chinese")
    eq(xs.detect_script("Samsung foundry"), None, "script-english")
    # Korean text carrying Han still reads Korean.
    eq(xs.detect_script("삼성 4nm 半導體"), "Korean", "script-korean-with-han")


# --------------------------------------------------------------------------
# 2. URL cleaning (Step 4) - real URLs from dry run 2
# --------------------------------------------------------------------------

def test_urls():
    eq(xs.clean_url("https://money.udn.com/money/story/5710/9739533"
                    "?from=edn_newestlist_rank&utm_source=chatgpt.com"),
       "https://money.udn.com/money/story/5710/9739533", "strip-from-and-utm")

    # Keep parameters that carry the article ID.
    eq(xs.clean_url("https://ww2.money-link.com.tw/realtimenews/NewsContent.aspx"
                    "?PU=1002&SN=6282337001"),
       "https://ww2.money-link.com.tw/realtimenews/NewsContent.aspx"
       "?PU=1002&SN=6282337001", "keep-article-id-params")
    eq(xs.clean_url("https://zdnet.co.kr/view/?no=20260907110055"),
       "https://zdnet.co.kr/view/?no=20260907110055", "keep-no-param")

    # Tracking fragment (dry run 2, decision (e)).
    eq(xs.clean_url("https://wallstreetcn.com/articles/3781148#from=ios"),
       "https://wallstreetcn.com/articles/3781148", "strip-tracking-fragment")
    # An ordinary anchor survives.
    eq(xs.clean_url("https://example.com/a#section-3"),
       "https://example.com/a#section-3", "keep-real-anchor")

    check(xs.is_external("https://x.com/DrNHJ/status/1") is False, "x-not-external")
    check(xs.is_external("https://t.co/abc") is False, "tco-not-external")
    check(xs.is_external("https://reuters.com/x") is True, "reuters-external")


# --------------------------------------------------------------------------
# 3. Parser: html.parser, PDF short-circuit, timeout guard
# --------------------------------------------------------------------------

HTML_PAGE = b"""<!doctype html><html><head>
<title>King Slide August revenue - Economic Daily News</title>
<meta property="og:site_name" content="&#32147;&#28639;&#26085;&#22577;">
<meta property="article:published_time" content="2026-09-07T08:12:00+08:00">
</head><body>
<article><p>King Slide reported August revenue of NT$6.466 billion.</p></article>
<aside><p>Related: Anthropic IPO</p></aside>
<script>var x = "Anthropic";</script>
</body></html>"""


def test_parser():
    info, err = xs.parse_page("https://money.udn.com/x", "text/html; charset=utf-8",
                              HTML_PAGE, 5)
    eq(err, None, "html-parse-no-error")
    eq(info["kind"], "html", "html-kind")
    eq(info["source_date"], "2026-09-07", "html-date")
    eq(info["publisher"], "經濟日報", "html-publisher-og-site-name")
    check("King Slide reported" in info["body_text"], "html-body-text")
    # Sidebars and <script> are excluded, so they cannot raise the Anthropic Flag.
    check("Anthropic" not in info["body_text"], "aside-and-script-excluded")

    # PDF short-circuit: recorded, not parsed.
    info, err = xs.parse_page("https://home.imeritz.com/x.pdf", "application/pdf",
                              b"%PDF-1.7\n1 0 obj", 5)
    eq(err, "pdf-short-circuit", "pdf-short-circuit")
    eq(info["kind"], "pdf", "pdf-kind")
    eq(info["source_date"], None, "pdf-no-date")
    eq(info["body_text"], "", "pdf-no-body")

    # A .pdf URL served without a content-type still short-circuits.
    info, err = xs.parse_page("https://www.tel.co.jp/a/deck.pdf", "", b"\x00junk", 5)
    eq(err, "pdf-short-circuit", "pdf-by-extension")

    # Malformed HTML does not raise.
    info, err = xs.parse_page("https://e.com/x", "text/html",
                              b"<html><body><p>unclosed", 5)
    eq(err, None, "malformed-html-survives")

    # JSON-LD fallback.
    ld = (b'<html><head><script type="application/ld+json">'
          b'{"@type":"NewsArticle","headline":"H","datePublished":"2026-09-05",'
          b'"publisher":{"name":"Nikkei"}}</script></head><body>x</body></html>')
    info, err = xs.parse_page("https://nikkei.com/a", "text/html", ld, 5)
    eq(info["source_date"], "2026-09-05", "jsonld-date")
    eq(info["publisher"], "Nikkei", "jsonld-publisher")

    # The per-file timeout is armed and disarmed cleanly.
    import signal as _sig
    if hasattr(_sig, "SIGALRM"):
        eq(_sig.getsignal(_sig.SIGALRM), _sig.SIG_DFL, "alarm-handler-restored")


# --------------------------------------------------------------------------
# 4. Step 6 cap: v1.2 rule vs v1.3 rule, on dry run 2's real distribution
# --------------------------------------------------------------------------

def _apply_cap_v12(records, cap):
    """The rule prompt v1.2 carried, for comparison only.

    'keep rows with an Owned-Name Hit first, then most recent, to the cap.'
    """
    a_rows = [r for r in records if r["bucket"] != "B"]
    b_rows = [r for r in records if r["bucket"] == "B"]
    b_rows.sort(key=lambda r: (r["owned_name_hits"] != ["None"], r["captured"] or ""),
                reverse=True)
    return a_rows + b_rows[:cap], b_rows[cap:]


def _synth_b(n_hit, n_nohit):
    rows = []
    for i in range(n_hit):
        rows.append({"post_url": "https://x.com/a/status/%d" % (1000 + i),
                     "account": ["@a"], "captured": "2026-09-07T%02d:00:00.000Z" % (i % 24),
                     "bucket": "B", "owned_name_hits": ["NVDA"]})
    for i in range(n_nohit):
        rows.append({"post_url": "https://x.com/b/status/%d" % (2000 + i),
                     "account": ["@b"], "captured": "2026-09-06T%02d:00:00.000Z" % (i % 24),
                     "bucket": "B", "owned_name_hits": ["None"]})
    return rows


def test_cap():
    # Dry run 2, Step 6: post-dedup bucket B was 77 rows, 49 with an owned-name
    # hit and 28 without. Bucket A was 37.
    b_rows = _synth_b(49, 28)
    a_rows = [{"post_url": "https://x.com/c/status/%d" % (3000 + i), "account": ["@c"],
               "captured": "2026-09-05T00:00:00.000Z", "bucket": "A",
               "owned_name_hits": ["None"]} for i in range(37)]
    all_rows = a_rows + b_rows

    old_kept, old_dropped = _apply_cap_v12(list(all_rows), 25)
    eq(len(old_kept), 62, "v1.2-total-kept")
    eq(len(old_dropped), 52, "v1.2-dropped")
    eq(sum(1 for r in old_kept if r["bucket"] == "B"), 25, "v1.2-bucket-b-kept")
    eq(sum(1 for r in old_dropped if r["owned_name_hits"] != ["None"]), 24,
       "v1.2-dropped-with-owned-hit")

    new_kept, new_dropped, counts = xs.apply_cap(list(all_rows), 25)
    eq(len(new_kept), 111, "v1.3-total-kept")
    eq(len(new_dropped), 3, "v1.3-dropped")
    eq(counts["bucket_b_kept_on_owned_name_hit"], 49, "v1.3-kept-on-owned-hit")
    eq(counts["bucket_b_kept_under_cap"], 25, "v1.3-kept-under-cap")
    eq(sum(1 for r in new_dropped if r["owned_name_hits"] != ["None"]), 0,
       "v1.3-never-drops-an-owned-hit")

    # The cap keeps the MOST RECENT of the no-hit rows.
    dropped_at = sorted(r["captured"] for r in new_dropped)
    kept_nohit = sorted(r["captured"] for r in new_kept
                        if r["bucket"] == "B" and r["owned_name_hits"] == ["None"])
    check(max(dropped_at) <= min(kept_nohit), "v1.3-drops-the-oldest",
          "%s vs %s" % (max(dropped_at), min(kept_nohit)))

    # A bucket-A row is never touched by the cap.
    eq(sum(1 for r in new_kept if r["bucket"] == "A"), 37, "cap-ignores-bucket-a")


# --------------------------------------------------------------------------
# 5. Dedup (Step 6)
# --------------------------------------------------------------------------

def _rec(post_url, captured, bucket, src=None, hits=None, handle="@x"):
    return {"post_url": post_url, "account": [handle], "captured": captured,
            "bucket": bucket, "underlying_source_url": src, "publisher": None,
            "source_date": None, "verification": None,
            "owned_name_hits": hits or ["None"], "anthropic_flag": False,
            "translated_from": None, "raw_post_text": "t",
            "fetched_page_path": None, "_post_ids": [post_url.rsplit("/", 1)[-1]],
            "_quoted_text": "", "_page_title": None, "_fetch_status": 200}


def test_dedup():
    src = "https://money.udn.com/money/story/5612/9738201"
    a = _rec("https://x.com/dnystedt/status/1", "2026-09-07T00:28:24.000Z", "A",
             src, ["NVDA"], "@dnystedt")
    b = _rec("https://x.com/DrNHJ/status/2", "2026-09-07T02:46:57.000Z", "A",
             src, ["TSM"], "@DrNHJ")
    kept, clusters, filed = xs.dedup([a, b], [], None)
    eq(len(kept), 1, "url-dedup-one-row")
    eq(kept[0]["post_url"], "https://x.com/dnystedt/status/1", "earliest-post-wins")
    eq(kept[0]["account"], ["@dnystedt", "@DrNHJ"], "handles-merged")
    eq(kept[0]["owned_name_hits"], ["NVDA", "TSM"], "hits-unioned")
    eq(len(clusters), 1, "one-cluster")

    # Cross-bucket merge keeps the resolved source (dry run 2, decision (f)):
    # the earlier post is bucket B with no URL, and must not discard the URL.
    nolink = _rec("https://x.com/QQ_Timmy/status/3", "2026-09-06T23:00:00.000Z",
                  "B", None, ["NVDA"], "@QQ_Timmy")
    withlink = _rec("https://x.com/DrNHJ/status/4", "2026-09-07T01:00:00.000Z",
                    "A", src, ["TSM"], "@DrNHJ")
    kept, clusters, _ = xs.dedup([nolink, withlink], [],
                                 [["https://x.com/QQ_Timmy/status/3",
                                   "https://x.com/DrNHJ/status/4"]])
    eq(len(kept), 1, "cross-bucket-one-row")
    eq(kept[0]["post_url"], "https://x.com/QQ_Timmy/status/3", "cross-bucket-earliest-url")
    eq(kept[0]["underlying_source_url"], src, "cross-bucket-keeps-source")
    eq(kept[0]["bucket"], "A", "cross-bucket-becomes-a")

    # Against existing Signal Inbox rows: Post URL, then cleaned source URL.
    existing = [{"post_url": "https://x.com/dnystedt/status/1",
                 "underlying_source_url": None},
                {"post_url": "https://x.com/other/status/9",
                 "underlying_source_url": src + "?utm_source=x"}]
    kept, _, filed = xs.dedup([a, b], existing, None)
    eq(len(kept), 0, "both-already-filed")
    eq(len(filed), 2, "already-filed-counted")

    # The Dated-Claim arm is declared, not silently skipped.
    c1 = _rec("https://x.com/DeItaone/status/5", "2026-09-07T15:36:24.000Z", "B",
              None, ["None"], "@DeItaone")
    c2 = _rec("https://x.com/TheValueist/status/6", "2026-09-07T16:40:32.000Z", "B",
              None, ["None"], "@TheValueist")
    kept, _, _ = xs.dedup([c1, c2], [], None)
    eq(len(kept), 2, "no-link-pair-not-deduped-without-model")
    kept, _, _ = xs.dedup([c1, c2], [], [["https://x.com/DeItaone/status/5",
                                          "https://x.com/TheValueist/status/6"]])
    eq(len(kept), 1, "model-groups-fold-in")
    eq(kept[0]["account"], ["@DeItaone", "@TheValueist"], "model-group-handles")


# --------------------------------------------------------------------------
# 6. Step 2 merge and Step 3 bucketing
# --------------------------------------------------------------------------

def _tweet(tid, author, text, created, urls=None, replied_to=None, quoted=None):
    t = {"id": tid, "author_id": author, "text": text, "created_at": created}
    if urls:
        t["entities"] = {"urls": [{"expanded_url": u} for u in urls]}
    refs = []
    if replied_to:
        refs.append({"type": "replied_to", "id": replied_to})
    if quoted:
        refs.append({"type": "quoted", "id": quoted})
    if refs:
        t["referenced_tweets"] = refs
    return t


def test_merge_and_bucket():
    # The 24-chain pattern dry run 2 named: story post, then a bare-link reply.
    posts = {
        "10": _tweet("10", "u1", "King Slide August revenue NT$6.466bn, +344% y/y",
                     "2026-09-07T12:14:00.000Z"),
        "11": _tweet("11", "u1", "https://money.udn.com/money/story/5710/9739533",
                     "2026-09-07T12:15:00.000Z",
                     urls=["https://money.udn.com/money/story/5710/9739533"
                           "?from=edn_newestlist_rank"],
                     replied_to="10"),
        "12": _tweet("12", "u2", "no numbers here", "2026-09-07T12:16:00.000Z"),
    }
    cands, merges = xs.merge_reply_chains(posts, {})
    eq(len(cands), 2, "merge-collapses-chain")
    eq(len(merges), 1, "one-merge")
    head = [c for c in cands if c["head_id"] == "10"][0]
    eq(head["created_at"], "2026-09-07T12:14:00.000Z", "captured-is-parents")
    check("King Slide" in head["raw_post_text"], "merged-text-carries-parent")
    # A bare-URL reply adds no text (Step 2).
    check("https://money.udn.com" not in head["raw_post_text"], "bare-url-reply-adds-no-text")
    eq(len(head["external_urls"]), 1, "url-lifted-from-reply")

    # Chains deeper than two.
    posts["13"] = _tweet("13", "u1", "and a third", "2026-09-07T12:17:00.000Z",
                         replied_to="11")
    cands, merges = xs.merge_reply_chains(posts, {})
    eq(len(cands), 2, "deep-chain-collapses")
    eq(len(merges[0]["merged"]), 2, "deep-chain-two-merged")

    # A reply by a DIFFERENT author is not merged.
    posts2 = {"20": _tweet("20", "u1", "story", "2026-09-07T00:00:00.000Z"),
              "21": _tweet("21", "u9", "reply", "2026-09-07T00:01:00.000Z",
                           replied_to="20")}
    cands, merges = xs.merge_reply_chains(posts2, {})
    eq(len(cands), 2, "different-author-not-merged")
    eq(len(merges), 0, "no-cross-author-merge")

    # Quoted text is read for matching (prompt MATCHING RULES).
    included = {"30": _tweet("30", "u5", "LPDDR6 shipments up 12%",
                             "2026-09-06T00:00:00.000Z")}
    posts3 = {"31": _tweet("31", "u1", "Anyone?", "2026-09-07T00:00:00.000Z",
                           quoted="30")}
    cands, _ = xs.merge_reply_chains(posts3, included)
    eq(cands[0]["quoted_text"], "LPDDR6 shipments up 12%", "quoted-text-captured")


# --------------------------------------------------------------------------
# 7. End-to-end, offline
# --------------------------------------------------------------------------

def _write(path, data):
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False))


def test_end_to_end():
    tmp = tempfile.mkdtemp(prefix="xsweep-")
    pages_dir = os.path.join(tmp, "pages")
    os.makedirs(pages_dir)

    udn = "https://money.udn.com/money/story/5710/9739533"
    store = xs.PageStore(pages_dir)
    store.put(udn, {"status": 200, "final_url": udn,
                    "content_type": "text/html; charset=utf-8", "is_pdf": False},
              HTML_PAGE)
    pdf = "https://home.imeritz.com/a/deck.pdf"
    store.put(pdf, {"status": 200, "final_url": pdf,
                    "content_type": "application/pdf", "is_pdf": True},
              b"%PDF-1.7 body")

    api_page = {
        "data": [
            # bucket A, same-author link reply, tracking params on the URL
            _tweet("100", "u1", "King Slide August revenue NT$6.466bn, +344% y/y",
                   "2026-09-07T12:14:00.000Z"),
            _tweet("101", "u1", udn + "?utm_source=chatgpt.com",
                   "2026-09-07T12:15:00.000Z",
                   urls=[udn + "?utm_source=chatgpt.com"], replied_to="100"),
            # bucket A, PDF -> short-circuit, Unverified
            _tweet("102", "u2", "메리츠 HBM4 노트",
                   "2026-09-07T10:00:00.000Z", urls=[pdf]),
            # bucket B: digit + layer keyword, owned-name hit
            _tweet("103", "u3", "Nvidia cuts Rubin Ultra HBM to 8-Hi",
                   "2026-09-07T09:00:00.000Z"),
            # bucket B: digit + layer keyword, NO owned-name hit
            _tweet("104", "u3", "Copper set a record $14,533 a ton, data center demand",
                   "2026-09-07T08:00:00.000Z"),
            # bucket C: digits, no owned name, no layer keyword
            _tweet("105", "u4", "$FCX entry around 62", "2026-09-07T07:00:00.000Z"),
            # bucket C: keyword but no digit anywhere
            _tweet("106", "u4", "CXMT and Apple", "2026-09-07T06:00:00.000Z"),
        ],
        "includes": {"users": [
            {"id": "u1", "username": "DrNHJ"}, {"id": "u2", "username": "jukan05"},
            {"id": "u3", "username": "dnystedt"}, {"id": "u4", "username": "TheValueist"},
        ]},
        "meta": {"next_token": "abc"},
    }
    posts_file = os.path.join(tmp, "posts.json")
    _write(posts_file, {"pages": [api_page]})
    out_file = os.path.join(tmp, "candidates.json")

    rc = subprocess.call([sys.executable, os.path.join(HERE, "x_sweep.py"),
                          "--posts", posts_file, "--offline",
                          "--pages-dir", pages_dir, "--out", out_file,
                          "--cap", "25"],
                         stderr=subprocess.PIPE)
    eq(rc, 0, "e2e-exit-code")
    with io.open(out_file, encoding="utf-8") as fh:
        out = json.load(fh)

    meta, recs = out["meta"], out["records"]
    by_url = {r["post_url"]: r for r in recs}

    eq(meta["merges"]["count"], 1, "e2e-merge-count")
    eq(meta["discarded_bucket_c"]["count"], 2, "e2e-bucket-c")
    eq(meta["buckets_final"], {"A": 2, "B": 2}, "e2e-buckets")
    eq(meta["posts_pulled"], 7, "e2e-posts")
    eq(meta["oldest_created_at"], "2026-09-07T06:00:00.000Z", "e2e-oldest")
    eq(meta["newest_created_at"], "2026-09-07T12:14:00.000Z", "e2e-newest")
    eq(meta["newest_post_id"], "106", "e2e-newest-id")

    king = by_url["https://x.com/DrNHJ/status/100"]
    eq(king["underlying_source_url"], udn, "e2e-tracking-params-stripped")
    eq(king["source_date"], "2026-09-07", "e2e-source-date")
    eq(king["publisher"], "經濟日報", "e2e-publisher")
    eq(king["verification"], None, "e2e-verification-left-to-model")
    eq(king["bucket"], "A", "e2e-bucket-a")
    check(king["fetched_page_path"] is not None, "e2e-page-path")
    check("King Slide" in king["raw_post_text"], "e2e-raw-text")

    meritz = by_url["https://x.com/jukan05/status/102"]
    eq(meritz["verification"], "Unverified", "e2e-pdf-unverified")
    eq(meritz["source_date"], None, "e2e-pdf-no-date")
    eq(meritz["translated_from"], "Korean", "e2e-translated-from")
    eq(len(meta["parse_failures"]), 1, "e2e-one-parse-failure")
    eq(meta["parse_failures"][0]["reason"], "pdf-short-circuit", "e2e-parse-reason")

    rubin = by_url["https://x.com/dnystedt/status/103"]
    eq(rubin["bucket"], "B", "e2e-bucket-b")
    eq(rubin["owned_name_hits"], ["NVDA"], "e2e-owned-hit")
    eq(rubin["publisher"], "@dnystedt", "e2e-bucket-b-publisher")
    eq(rubin["verification"], "Unverified", "e2e-bucket-b-unverified")
    eq(rubin["underlying_source_url"], None, "e2e-bucket-b-no-url")

    copper = by_url["https://x.com/dnystedt/status/104"]
    eq(copper["owned_name_hits"], ["None"], "e2e-no-owned-hit")

    # Nothing in the output sets Layer, Headline, Dated Claim or Status.
    for rec in recs:
        for banned in ("layer", "Layer", "headline", "Headline",
                       "dated_claim", "Dated Claim", "status", "Status",
                       "classification", "Classification"):
            check(banned not in rec, "no-model-field", "%s in record" % banned)

    # A bogus expanded URL falls back to bucket B, not a filed URL (decision (c)).
    bogus_page = {
        "data": [_tweet("200", "u1", "300308.SZ up 8% on HBM demand",
                        "2026-09-07T05:00:00.000Z", urls=["https://300308.SZ"])],
        "includes": {"users": [{"id": "u1", "username": "DrNHJ"}]},
    }
    _write(posts_file, {"pages": [bogus_page]})
    subprocess.call([sys.executable, os.path.join(HERE, "x_sweep.py"),
                     "--posts", posts_file, "--offline", "--pages-dir", pages_dir,
                     "--out", out_file], stderr=subprocess.PIPE)
    with io.open(out_file, encoding="utf-8") as fh:
        out2 = json.load(fh)
    # Offline, an uncached URL cannot be resolved, so it is a fetch failure and
    # the row files with the URL kept (Step 4). The DNS reclassification is
    # exercised as a unit below.
    eq(len(out2["records"]), 1, "bogus-one-record")
    eq(len(out2["meta"]["fetch_failures"]), 1, "bogus-fetch-failure")

    class _Reason(OSError):
        pass
    err = __import__("urllib.error", fromlist=["URLError"]).URLError(
        _Reason(-2, "Name or service not known"))
    check(xs._is_dns_failure(err) is True, "dns-failure-detected")
    err2 = __import__("urllib.error", fromlist=["URLError"]).URLError(
        OSError(104, "Connection reset by peer"))
    check(xs._is_dns_failure(err2) is False, "conn-reset-is-not-dns-failure")


# --------------------------------------------------------------------------
# 8. Diff against the 62 rows dry run 2 filed
# --------------------------------------------------------------------------

MECHANICAL_FIELDS = ["post_url", "account", "captured", "bucket",
                     "underlying_source_url", "publisher", "source_date",
                     "verification", "owned_name_hits", "anthropic_flag",
                     "translated_from"]


def test_fixture_contract():
    with io.open(FIXTURE, encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]
    eq(len(rows), 62, "fixture-row-count")

    a = [r for r in rows if r["bucket"] == "A"]
    b = [r for r in rows if r["bucket"] == "B"]
    eq(len(a), 37, "fixture-bucket-a")
    eq(len(b), 25, "fixture-bucket-b")
    eq(sum(1 for r in b if r["owned_name_hits"] == ["None"]), 0,
       "fixture-every-filed-b-row-has-an-owned-hit")

    # Every mechanical field the script emits exists on every filed row, and
    # nothing the model owns leaked into the fixture.
    sample = _rec("https://x.com/a/status/1", "2026-09-07T00:00:00.000Z", "A",
                  "https://e.com/a")
    for field in MECHANICAL_FIELDS:
        check(field in sample, "script-emits-field", field)
    for row in rows:
        for field in MECHANICAL_FIELDS:
            check(field in row, "fixture-has-field", "%s on %s" % (field, row["post_url"]))
        check("layer" not in row and "Layer" not in row, "fixture-no-layer")

    # Rule-shape checks the script must reproduce on this data.
    for row in rows:
        if row["bucket"] == "B":
            eq(row["underlying_source_url"], None, "filed-b-no-url")
            eq(row["verification"], "Unverified", "filed-b-unverified")
            check(row["publisher"].startswith("@"), "filed-b-publisher-is-handle",
                  row["post_url"])
        else:
            check(row["underlying_source_url"], "filed-a-has-url")
            check(row["verification"] in ("Source fetched", "Unverified"),
                  "filed-a-verification")

    # No filed Underlying Source URL carries a tracking parameter: clean_url is
    # idempotent over every one of them.
    for row in rows:
        url = row["underlying_source_url"]
        if url:
            eq(xs.clean_url(url), url, "filed-url-already-clean")

    # Owned-Name Hits use match-table tickers or the explicit "None".
    valid = set(xs.OWNED_NAMES) | {"None"}
    for row in rows:
        for hit in row["owned_name_hits"]:
            check(hit in valid, "filed-hit-is-a-ticker", "%s on %s" % (hit, row["post_url"]))

    # Translated From uses only the three allowed values.
    for row in rows:
        check(row["translated_from"] in (None, "Korean", "Chinese", "Japanese"),
              "filed-translated-from", row["post_url"])

    # Under the v1.3 cap, none of these 25 filed bucket-B rows would be capped:
    # every one carries a live owned-name hit.
    kept, dropped, counts = xs.apply_cap(
        [dict(r, account=[r["account"]]) for r in rows], 25)
    eq(len(dropped), 0, "v1.3-drops-none-of-the-filed-62")
    eq(counts["bucket_b_kept_on_owned_name_hit"], 25, "v1.3-filed-b-all-on-owned-hit")
    eq(counts["bucket_b_kept_under_cap"], 0, "v1.3-filed-none-under-cap")


def main():
    for fn in (test_matching, test_urls, test_parser, test_cap, test_dedup,
               test_merge_and_bucket, test_end_to_end, test_fixture_contract):
        fn()
    print("checks run: %d" % CHECKS[0])
    if FAILURES:
        print("FAILURES: %d" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
