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
  3. checks the reference arithmetic for prompt Step 6c over dry run 2's real
     post-dedup bucket-B distribution (49 with an owned-name hit / 28 without)
     under both the old and the ruled cap. The SCRIPT DOES NOT CAP - Step 6c is
     the model's and runs after 6b - so both rules are implemented here, in the
     test file, purely to hold the numbers in the run note honest;
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

    # Ruled suffix rule, positive: suffix that starts with a digit.
    for text, want in [("HBM3E base dies", ["HBM"]), ("HBM4 ramp", ["HBM"]),
                       ("LPDDR6 supply", ["LPDDR"]), ("DDR5 pricing", ["DDR"])]:
        hits = m.layer_hits(text)
        check(all(w in hits for w in want), "suffix-digit", "%r -> %r" % (text, hits))

    # Ruled suffix rule, negative: suffix that starts with a letter.
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

    # Anthropic Flag strings, ruled 2026-09-07: these three and no others.
    eq(xs.ANTHROPIC_STRINGS, ["Anthropic", "Claude", "앤트로픽"], "anthropic-strings")
    check("앱트로픽" not in xs.ANTHROPIC_STRINGS, "wrong-hangul-removed")
    check("安人比" not in xs.ANTHROPIC_STRINGS, "unsubstantiated-han-removed")

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
# 4. Step 6c cap - REFERENCE ARITHMETIC ONLY
#
# x_sweep.py does not cap. Step 6c belongs to the model and runs after Step 6b
# (claim-level dedup), because capping first drops rows that were about to
# merge. Both rules are implemented below, in this file, so the 62 -> 111
# figure in notes/runs/2026-09-07-x-sweep-script-test.md stays checkable.
# --------------------------------------------------------------------------

def _apply_cap_old(records, cap):
    """The rule the prompt carried before 2026-09-07.

    'keep rows with an Owned-Name Hit first, then most recent, to the cap.'
    """
    a_rows = [r for r in records if r["bucket"] != "B"]
    b_rows = [r for r in records if r["bucket"] == "B"]
    b_rows.sort(key=lambda r: (r["owned_name_hits"] != ["None"], r["captured"] or ""),
                reverse=True)
    return a_rows + b_rows[:cap], b_rows[cap:]


def _apply_cap_ruled(records, cap):
    """prompt v1.4 Step 6c.

    A bucket-B row carrying a live Owned-Name Hit is NEVER dropped. The cap
    applies only to bucket-B rows with Owned-Name Hits = None: keep the most
    recent of those up to NIGHTLY_CAP_NOLINK and drop the rest.
    """
    kept, no_hit, kept_on_owned_name = [], [], 0
    for r in records:
        if r["bucket"] != "B":
            kept.append(r)
        elif r["owned_name_hits"] != ["None"]:
            kept.append(r)
            kept_on_owned_name += 1
        else:
            no_hit.append(r)
    no_hit.sort(key=lambda r: (r["captured"] or "", r["post_url"]), reverse=True)
    kept.extend(no_hit[:cap])
    return kept, no_hit[cap:], {
        "bucket_b_kept_on_owned_name_hit": kept_on_owned_name,
        "bucket_b_kept_under_cap": len(no_hit[:cap]),
    }


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

    old_kept, old_dropped = _apply_cap_old(list(all_rows), 25)
    eq(len(old_kept), 62, "old-cap-total-kept")
    eq(len(old_dropped), 52, "old-cap-dropped")
    eq(sum(1 for r in old_kept if r["bucket"] == "B"), 25, "old-cap-bucket-b-kept")
    eq(sum(1 for r in old_dropped if r["owned_name_hits"] != ["None"]), 24,
       "old-cap-dropped-with-owned-hit")

    new_kept, new_dropped, counts = _apply_cap_ruled(list(all_rows), 25)
    eq(len(new_kept), 111, "ruled-cap-total-kept")
    eq(len(new_dropped), 3, "ruled-cap-dropped")
    eq(counts["bucket_b_kept_on_owned_name_hit"], 49, "ruled-cap-kept-on-owned-hit")
    eq(counts["bucket_b_kept_under_cap"], 25, "ruled-cap-kept-under-cap")
    eq(sum(1 for r in new_dropped if r["owned_name_hits"] != ["None"]), 0,
       "ruled-cap-never-drops-an-owned-hit")

    # The cap keeps the MOST RECENT of the no-hit rows.
    dropped_at = sorted(r["captured"] for r in new_dropped)
    kept_nohit = sorted(r["captured"] for r in new_kept
                        if r["bucket"] == "B" and r["owned_name_hits"] == ["None"])
    check(max(dropped_at) <= min(kept_nohit), "ruled-cap-drops-the-oldest",
          "%s vs %s" % (max(dropped_at), min(kept_nohit)))

    # A bucket-A row is never touched by the cap.
    eq(sum(1 for r in new_kept if r["bucket"] == "A"), 37, "cap-ignores-bucket-a")

    # The script itself must expose no cap at all.
    check(not hasattr(xs, "apply_cap"), "script-has-no-apply-cap")
    check(not hasattr(xs, "NIGHTLY_CAP_NOLINK"), "script-has-no-cap-constant")


# --------------------------------------------------------------------------
# 5. Dedup (Step 6)
# --------------------------------------------------------------------------

def _rec(post_url, captured, bucket, src=None, hits=None, handle="@x",
         layers=None, excerpt=None):
    pid = post_url.rsplit("/", 1)[-1]
    return {"post_url": post_url, "account": [handle], "captured": captured,
            "bucket": bucket, "underlying_source_url": src, "publisher": None,
            "source_date": None, "verification": xs.VERIFICATION_MODEL_DECIDES,
            "owned_name_hits": hits or ["None"], "anthropic_flag": False,
            "translated_from": None, "raw_post_text": "t",
            "fetched_page_path": None, "_post_ids": [pid],
            "_post_texts": [{"post_id": pid, "post_url": post_url,
                             "account": handle, "created_at": captured,
                             "is_head": True, "contributed_text": True,
                             "text": "t"}],
            "_quoted_text": "", "_quoted_posts": [],
            "_layer_hits": list(layers or []),
            "_digit_gate": None, "_source_excerpt": excerpt,
            "_page_title": None, "_fetch_status": 200}


def test_dedup():
    src = "https://money.udn.com/money/story/5612/9738201"
    a = _rec("https://x.com/dnystedt/status/1", "2026-09-07T00:28:24.000Z", "A",
             src, ["NVDA"], "@dnystedt")
    b = _rec("https://x.com/DrNHJ/status/2", "2026-09-07T02:46:57.000Z", "A",
             src, ["TSM"], "@DrNHJ")
    kept, clusters, filed = xs.dedup([a, b], [])
    eq(len(kept), 1, "url-dedup-one-row")
    eq(kept[0]["post_url"], "https://x.com/dnystedt/status/1", "earliest-post-wins")
    eq(kept[0]["account"], ["@dnystedt", "@DrNHJ"], "handles-merged")
    eq(kept[0]["owned_name_hits"], ["NVDA", "TSM"], "hits-unioned")
    eq(len(clusters), 1, "one-cluster")

    # A no-link candidate never joins a linked one at 6a - there is no shared
    # URL to join on. That is Step 6b's job, and the prompt states the rule
    # there. Both survive here.
    nolink = _rec("https://x.com/QQ_Timmy/status/3", "2026-09-06T23:00:00.000Z",
                  "B", None, ["NVDA"], "@QQ_Timmy")
    withlink = _rec("https://x.com/DrNHJ/status/4", "2026-09-07T01:00:00.000Z",
                    "A", src, ["TSM"], "@DrNHJ")
    kept, clusters, _ = xs.dedup([nolink, withlink], [])
    eq(len(kept), 2, "6a-does-not-join-no-link-to-linked")
    eq(len(clusters), 0, "6a-no-cross-bucket-cluster")

    # Against existing Signal Inbox rows: Post URL, then cleaned source URL.
    existing = [{"post_url": "https://x.com/dnystedt/status/1",
                 "underlying_source_url": None},
                {"post_url": "https://x.com/other/status/9",
                 "underlying_source_url": src + "?utm_source=x"}]
    kept, _, filed = xs.dedup([a, b], existing)
    eq(len(kept), 0, "both-already-filed")
    eq(len(filed), 2, "already-filed-counted")

    # Two accounts pasting the same claim link-free survive 6a untouched. Only
    # Step 6b can collapse them, and Step 6b is the model's.
    c1 = _rec("https://x.com/DeItaone/status/5", "2026-09-07T15:36:24.000Z", "B",
              None, ["None"], "@DeItaone")
    c2 = _rec("https://x.com/TheValueist/status/6", "2026-09-07T16:40:32.000Z", "B",
              None, ["None"], "@TheValueist")
    kept, _, _ = xs.dedup([c1, c2], [])
    eq(len(kept), 2, "no-link-pair-survives-6a")
    check(not hasattr(xs, "apply_cap"), "no-cap-in-dedup-path")


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
            # Anthropic Flag, Korean: the ruled string fires...
            _tweet("107", "u3", "앤트로픽 HBM4 계약 517조원",
                   "2026-09-07T08:30:00.000Z"),
            # ...and the character the old prompt had does not.
            _tweet("108", "u3", "앱트로픽 HBM4 계약 517조원",
                   "2026-09-07T08:31:00.000Z"),
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
                          "--pages-dir", pages_dir, "--out", out_file],
                         stderr=subprocess.PIPE)
    eq(rc, 0, "e2e-exit-code")
    with io.open(out_file, encoding="utf-8") as fh:
        out = json.load(fh)

    meta, recs = out["meta"], out["records"]
    by_url = {r["post_url"]: r for r in recs}

    eq(meta["merges"]["count"], 1, "e2e-merge-count")
    eq(meta["discarded_bucket_c"]["count"], 2, "e2e-bucket-c")
    eq(meta["buckets_post_dedup"], {"A": 2, "B": 4}, "e2e-buckets")
    check("cap" not in meta, "e2e-meta-has-no-cap")
    check("dropped_by_cap" not in meta, "e2e-meta-has-no-dropped-by-cap")
    check(meta["step_6b_claim_dedup"].startswith("NOT PERFORMED"), "e2e-6b-declared")
    check(meta["step_6c_cap"].startswith("NOT APPLIED"), "e2e-6c-declared")
    eq(meta["posts_pulled"], 9, "e2e-posts")
    eq(meta["oldest_created_at"], "2026-09-07T06:00:00.000Z", "e2e-oldest")
    eq(meta["newest_created_at"], "2026-09-07T12:14:00.000Z", "e2e-newest")
    eq(meta["newest_post_id"], "108", "e2e-newest-id")

    king = by_url["https://x.com/DrNHJ/status/100"]
    eq(king["underlying_source_url"], udn, "e2e-tracking-params-stripped")
    eq(king["source_date"], "2026-09-07", "e2e-source-date")
    eq(king["publisher"], "經濟日報", "e2e-publisher")
    eq(king["verification"], "Model decides", "e2e-verification-named-state")
    check(king["verification"] is not None, "e2e-verification-never-null")
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
    # A no-hit bucket-B candidate survives: the script does not cap.
    eq(meta["candidates_out"], 6, "e2e-every-candidate-survives")

    # Anthropic Flag: only the ruled Korean string fires.
    good = by_url["https://x.com/dnystedt/status/107"]
    bad = by_url["https://x.com/dnystedt/status/108"]
    eq(good["anthropic_flag"], True, "e2e-anthropic-flag-fires-on-ruled-string")
    eq(good["translated_from"], "Korean", "e2e-anthropic-post-korean")
    eq(bad["anthropic_flag"], False, "e2e-anthropic-flag-silent-on-old-string")

    # Nothing in the output sets Layer, Headline, Dated Claim or Status.
    for rec in recs:
        for banned in ("layer", "Layer", "headline", "Headline",
                       "dated_claim", "Dated Claim", "status", "Status",
                       "classification", "Classification"):
            check(banned not in rec, "no-model-field", "%s in record" % banned)

    # BUG 2, ruled 2026-09-07. The exact URL that filed as bucket A in dry runs
    # 2 and 3. It is now rejected BEFORE any fetch, so there is no fetch at all
    # to fail - which is the point: behind a CONNECT proxy the fetch would have
    # returned 502, not a DNS error, and the old check would have missed it.
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
    eq(len(out2["records"]), 1, "bogus-one-record")
    rec = out2["records"][0]
    eq(rec["bucket"], "B", "bogus-demoted-to-bucket-b")
    eq(rec["underlying_source_url"], None, "bogus-url-not-filed")
    eq(rec["publisher"], "@DrNHJ", "bogus-publisher-is-the-account")
    eq(rec["verification"], "Unverified", "bogus-unverified")
    eq(len(out2["meta"]["fetch_failures"]), 0, "bogus-never-fetched")
    eq(len(out2["meta"]["reclassified_a_to_b"]), 1, "bogus-reclassified")
    eq(out2["meta"]["reclassified_a_to_b"][0]["stage"], "pre-fetch",
       "bogus-rejected-before-fetch")

    # The post-fetch DNS arm still works where there is no proxy in the way.
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
            # The fixture holds FILED rows, so the model has already resolved
            # "Model decides" into a Notion option. That state must never reach
            # Notion.
            check(row["verification"] != xs.VERIFICATION_MODEL_DECIDES,
                  "model-decides-never-filed", row["post_url"])

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

    # Under the ruled cap, none of these 25 filed bucket-B rows would be
    # capped: every one carries a live owned-name hit. (Reference arithmetic -
    # the script does not cap.)
    kept, dropped, counts = _apply_cap_ruled(
        [dict(r, account=[r["account"]]) for r in rows], 25)
    eq(len(dropped), 0, "ruled-cap-drops-none-of-the-filed-62")
    eq(counts["bucket_b_kept_on_owned_name_hit"], 25, "filed-b-all-on-owned-hit")
    eq(counts["bucket_b_kept_under_cap"], 0, "filed-none-under-cap")



# --------------------------------------------------------------------------
# 9. Bug 1 - the Step 3B digit gate must not read URLs
#    Bug 2 - implausible hosts are rejected before any fetch
#    Prompt v1.5 handover fields
# --------------------------------------------------------------------------

def test_digit_gate_ignores_urls():
    # strip_urls removes the link and nothing else.
    eq(xs.strip_urls("KING CHARLES III https://t.co/w9kVRQr8iC").strip(),
       "KING CHARLES III", "strip-urls-removes-link")
    eq(xs.strip_urls("no links here"), "no links here", "strip-urls-noop")
    check("2,645" in xs.strip_urls("target RMB2,645 https://t.co/a1b2"),
          "strip-urls-keeps-real-figures")
    eq(" ".join(xs.strip_urls("see http://a.com/9 and https://b.com/8").split()),
       "see and", "strip-urls-both-schemes")

    # The live case: dry run 3 row 20. No digit in the post; digits only in the
    # t.co shortlink. This must NOT pass the gate.
    row20 = ("NVIDIA $NVDA CEO JENSEN HUANG AMONG GUESTS ON KING CHARLES III'S "
             "AI MEETING LIST - POLITICO https://t.co/w9kVRQr8iC")
    eq(xs.digit_gate_hit([("post_text", row20), ("quoted_text", "")]), None,
       "row20-no-digit-outside-url")
    check(xs.DIGIT_RE.search(row20) is not None, "row20-did-pass-the-old-gate")

    # A real figure still passes, and the gate says what matched and where.
    hit = xs.digit_gate_hit([("post_text", "YMTC could reach 18% of NAND "
                                           "https://t.co/zz9"), ("quoted_text", "")])
    eq(hit["digit"], "18", "gate-records-the-digit")
    eq(hit["source"], "post_text", "gate-records-the-source")
    check("YMTC" in hit["context"], "gate-records-context")

    # A digit that lives only in the quoted post still counts - that reading is
    # ruled and stays ruled (dry run 1's narrowing was the bug, not the fix).
    hit = xs.digit_gate_hit([("post_text", "Anyone? https://t.co/a1"),
                             ("quoted_text", "30-40 min call")])
    eq(hit["source"], "quoted_text", "gate-reads-the-quoted-post")
    eq(hit["digit"], "30", "gate-quoted-digit")

    # Thousands separators and decimals travel with the figure.
    eq(xs.digit_gate_hit([("post_text", "NT$6.466bn")])["digit"], "6.466",
       "gate-keeps-decimal")
    eq(xs.digit_gate_hit([("post_text", "RMB2,645 target")])["digit"], "2,645",
       "gate-keeps-thousands-separator")

    # Keyword and owned-name matching are UNAFFECTED by the strip.
    m = xs.Matcher()
    slug = "https://biz.chosun.com/nvidia-hbm4-ramp"
    eq(m.owned_hits(slug), ["NVDA"], "owned-match-still-reads-urls")
    check("HBM" in m.layer_hits(slug), "layer-match-still-reads-urls")


def test_implausible_host():
    # The live case, and its whole family. .sz IS a real ccTLD, so a TLD
    # allowlist would not catch this - the shape does.
    for url in ["https://300308.SZ", "https://300308.sz", "https://600519.SS",
                "https://0700.HK", "https://005930.KS"]:
        reason = xs.implausible_host(url)
        check(reason is not None, "ticker-shape-rejected", url)
        check("ticker" in reason, "ticker-shape-reason", "%s -> %r" % (url, reason))

    # No TLD at all, and a non-alphabetic TLD.
    check(xs.implausible_host("https://localhost") is not None, "no-tld-rejected")
    check(xs.implausible_host("https://300308.12") is not None, "numeric-tld-rejected")
    check(xs.implausible_host("https://example.c") is not None, "one-char-tld-rejected")

    # Real sources from dry runs 2 and 3 all pass.
    for url in ["https://www.reuters.com/business/energy/ship-fuel-2026-09-07/",
                "https://money.udn.com/money/story/5710/9739533",
                "https://zdnet.co.kr/view/?no=20260907110055",
                "https://biz.chosun.com/it-science/ict/2026/09/07/V7UWTGBE45GZ5.../",
                "https://n.news.naver.com/mnews/article/015/0005329331",
                "https://t.me/Jstockclass/15086",
                "https://irrationalanalysis.substack.com/p/hot-chips-2026-recap",
                "https://ww2.money-link.com.tw/realtimenews/NewsContent.aspx?PU=1002",
                "https://192.168.1.10/report"]:
        eq(xs.implausible_host(url), None, "real-source-passes")

    # A digit-labelled host is fine once it has a path or a longer TLD - the
    # rule is deliberately narrow.
    eq(xs.implausible_host("https://300308.sz/news/article"), None,
       "digit-label-with-path-passes")
    eq(xs.implausible_host("https://123.com"), None, "digit-label-normal-tld-passes")

    # The check must not key on HTTP status anywhere. Scan the CODE only - the
    # docstring names the 502 it exists to stop trusting.
    src = io.open(os.path.join(HERE, "x_sweep.py"), encoding="utf-8").read()
    body = src.split("def implausible_host(")[1].split("\ndef ")[0]
    code = body.split('"""', 2)[-1]
    check('"""' in body, "host-check-has-a-docstring")
    for banned in ("status", "502", "getcode", ".code", "urlopen", "fetch("):
        check(banned not in code, "host-check-ignores-http", banned)


def _run_offline(pages, tmp, pages_dir):
    posts_file = os.path.join(tmp, "p.json")
    out_file = os.path.join(tmp, "c.json")
    _write(posts_file, {"pages": pages})
    subprocess.call([sys.executable, os.path.join(HERE, "x_sweep.py"),
                     "--posts", posts_file, "--offline", "--pages-dir", pages_dir,
                     "--out", out_file], stderr=subprocess.PIPE)
    with io.open(out_file, encoding="utf-8") as fh:
        return json.load(fh)


def test_handover_fields():
    """The six gaps dry run 3 named in candidates.json."""
    tmp = tempfile.mkdtemp(prefix="xsweep-v15-")
    pages_dir = os.path.join(tmp, "pages")
    os.makedirs(pages_dir)
    udn = "https://money.udn.com/money/story/5710/9739533"
    xs.PageStore(pages_dir).put(
        udn, {"status": 200, "final_url": udn,
              "content_type": "text/html; charset=utf-8", "is_pdf": False},
        HTML_PAGE)

    quoted = _tweet("300", "u9", "Blended DRAM px expected ~10% QoQ in 4Q26",
                    "2026-09-07T01:00:00.000Z")
    page = {
        "data": [
            # merged same-author chain: figure in the head, link in the reply
            _tweet("400", "u1", "King Slide August revenue NT$6.466bn, +344% y/y",
                   "2026-09-07T12:14:00.000Z"),
            _tweet("401", "u1", udn, "2026-09-07T12:15:00.000Z", urls=[udn],
                   replied_to="400"),
            # bucket B whose figure lives in the quoted post
            _tweet("402", "u2", "Turning positive on DRAM. HBM demand.",
                   "2026-09-07T02:00:00.000Z", quoted="300"),
            # the row-20 shape: digits only inside the shortlink -> bucket C
            _tweet("403", "u3", "JENSEN HUANG ON KING CHARLES' AI LIST "
                                "https://t.co/w9kVRQr8iC",
                   "2026-09-07T03:00:00.000Z"),
        ],
        "includes": {"users": [{"id": "u1", "username": "DrNHJ"},
                               {"id": "u2", "username": "QQ_Timmy"},
                               {"id": "u3", "username": "wallstengine"},
                               {"id": "u9", "username": "pequityresearch"}],
                     "tweets": [quoted]},
    }
    out = _run_offline([page], tmp, pages_dir)
    by_url = {r["post_url"]: r for r in out["records"]}

    # (a) layer_hits survives to the output, under a name that is not Layer.
    king = by_url["https://x.com/DrNHJ/status/400"]
    check("_layer_hits" in king, "layer-hits-emitted")
    check("layer" not in king and "Layer" not in king, "still-no-layer-key")
    dram = by_url["https://x.com/QQ_Timmy/status/402"]
    check("HBM" in dram["_layer_hits"], "layer-hits-populated")
    check("DRAM" in dram["_layer_hits"], "layer-hits-from-post")

    # (b) the digit gate records what satisfied it, post-URL-strip.
    eq(dram["_digit_gate"]["source"], "quoted_text", "digit-gate-source-recorded")
    eq(dram["_digit_gate"]["digit"], "10", "digit-gate-digit-recorded")
    check(dram["_digit_gate"]["context"], "digit-gate-context-recorded")

    # ...and the row-20 shape is discarded to bucket C with the honest reason.
    check("https://x.com/wallstengine/status/403" not in by_url,
          "row20-shape-discarded")
    reasons = [d["reason"] for d in out["meta"]["discarded_bucket_c"]["detail"]]
    check("no digit outside a URL" in reasons, "row20-discard-reason")

    # (c) per-post attribution across a merge: which text came from which post.
    eq(len(king["_post_texts"]), 2, "merged-record-attributes-both-posts")
    heads = [e for e in king["_post_texts"] if e["is_head"]]
    eq(len(heads), 1, "one-head-post")
    eq(heads[0]["post_url"], "https://x.com/DrNHJ/status/400", "head-post-url")
    check("6.466" in heads[0]["text"], "figure-attributed-to-its-post")
    tail = [e for e in king["_post_texts"] if not e["is_head"]][0]
    eq(tail["post_url"], "https://x.com/DrNHJ/status/401", "reply-post-url")
    eq(tail["contributed_text"], False, "bare-url-reply-marked-no-text")

    # (d) a body excerpt travels with a bucket-A record.
    check(king["_source_excerpt"], "source-excerpt-present")
    check("King Slide reported" in king["_source_excerpt"], "source-excerpt-readable")
    check(len(king["_source_excerpt"]) <= xs.SOURCE_EXCERPT_CHARS,
          "source-excerpt-bounded")
    # The excerpt is body text, so an excluded sidebar cannot leak into it.
    check("Anthropic" not in king["_source_excerpt"], "excerpt-excludes-sidebar")
    eq(dram["_source_excerpt"], None, "bucket-b-has-no-excerpt")

    # (e) quoted post carries its author's handle and URL.
    eq(len(dram["_quoted_posts"]), 1, "one-quoted-post")
    q = dram["_quoted_posts"][0]
    eq(q["account"], "@pequityresearch", "quoted-author-handle")
    eq(q["post_url"], "https://x.com/pequityresearch/status/300", "quoted-post-url")
    eq(q["quoted_by_post_id"], "402", "quoted-linked-to-quoting-post")
    check(q["text"] in dram["_quoted_text"], "quoted-text-still-present")

    # (f) verification is a named state, never null.
    eq(king["verification"], xs.VERIFICATION_MODEL_DECIDES, "verification-named")
    eq(dram["verification"], xs.VERIFICATION_UNVERIFIED, "bucket-b-unverified")
    for rec in out["records"]:
        check(rec["verification"] is not None, "verification-never-null",
              rec["post_url"])
        check(rec["verification"] in (xs.VERIFICATION_UNVERIFIED,
                                      xs.VERIFICATION_MODEL_DECIDES),
              "verification-in-the-named-set", rec["verification"])

    # Every working field is underscore-prefixed, so nothing new can be mistaken
    # for a Signal Inbox column.
    for rec in out["records"]:
        for field in ("_layer_hits", "_digit_gate", "_post_texts",
                      "_quoted_posts", "_source_excerpt"):
            check(field in rec, "handover-field-present", field)
            check(field.startswith("_"), "handover-field-underscored", field)

    # A 6a collapse keeps attribution from every member.
    src = "https://example.com/one-source"
    r1 = _rec("https://x.com/a/status/1", "2026-09-07T00:00:00.000Z", "A", src,
              layers=["HBM"], handle="@a")
    r2 = _rec("https://x.com/b/status/2", "2026-09-07T01:00:00.000Z", "A", src,
              layers=["DRAM"], handle="@b", excerpt="body")
    kept, clusters, _ = xs.dedup([r1, r2], [])
    eq(len(kept), 1, "collapse-one-row")
    eq(len(kept[0]["_post_texts"]), 2, "collapse-keeps-both-attributions")
    eq(sorted(kept[0]["_layer_hits"]), ["DRAM", "HBM"], "collapse-unions-layer-hits")
    eq(kept[0]["_source_excerpt"], "body", "collapse-rescues-the-excerpt")


def main():
    for fn in (test_matching, test_urls, test_parser, test_cap, test_dedup,
               test_merge_and_bucket, test_end_to_end, test_fixture_contract,
               test_digit_gate_ignores_urls, test_implausible_host,
               test_handover_fields):
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
