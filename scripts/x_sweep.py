#!/usr/bin/env python3
"""X Sweep - the mechanical half of prompts/x-sweep.md (Steps 1 through 6).

This script does the parts of the sweep that have one right answer: pulling the
List, merging same-author reply chains, bucketing, fetching and parsing the
underlying source, cleaning URLs, deduping on URL, and applying the no-link cap.

It decides nothing a model should decide. It does NOT write Headline or Dated
Claim. It never sets Layer - there is no Layer key anywhere in its output.

Output is one candidates.json: {"meta": {...}, "records": [...]}.

Standard library only. Python 3.8+.
"""

import argparse
import hashlib
import html
import io
import json
import os
import re
import signal
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from html.parser import HTMLParser

# --------------------------------------------------------------------------
# Constants from the prompt. Keep these in sync with prompts/x-sweep.md.
# --------------------------------------------------------------------------

X_LIST_ID = os.environ.get("X_LIST_ID", "1764453609561825483")
NIGHTLY_CAP_NOLINK = int(os.environ.get("NIGHTLY_CAP_NOLINK", "25"))

OWNED_NAMES = OrderedDict([
    ("MU", ["Micron", "$MU", "마이크론", "微技"]),
    ("NVDA", ["Nvidia", "NVIDIA", "$NVDA", "엔비디아", "輝達", "英伟达"]),
    ("TSM", ["TSMC", "Taiwan Semiconductor", "$TSM", "대만반도체", "台積電", "台积电"]),
    ("ASML", ["ASML", "$ASML", "에이에스엠엘", "阿斯麦"]),
    ("GEV", ["GE Vernova", "$GEV"]),
    ("CRWD", ["CrowdStrike", "Falcon", "$CRWD", "크라우드스트라이크"]),
    ("AVGO", ["Broadcom", "VMware", "$AVGO", "브로드컴", "博通", "博康"]),
    ("COHR", ["Coherent", "$COHR", "코히런트"]),
    ("VRT", ["Vertiv", "$VRT", "버티브"]),
    ("GOOGL", ["Google", "Alphabet", "GCP", "TPU", "$GOOGL", "$GOOG", "구글", "谷歌"]),
])

LAYER_KEYWORDS = [
    # Companies
    "Samsung", "SK hynix", "Hynix", "Kioxia", "Sandisk", "Applied Materials",
    "Lam Research", "Tokyo Electron", "KLA", "Advantest", "Amkor",
    "ASE Technology", "Ibiden", "Shinko", "Unimicron", "FormFactor",
    "King Slide", "Intel", "AMD", "Marvell", "Arista", "Cisco", "Lumentum",
    "Fabrinet", "Innolight", "Eoptolink", "Amphenol", "Credo", "Schneider",
    "Eaton", "Siemens Energy", "Hitachi Energy", "Quanta", "Microsoft",
    "Azure", "AWS", "Amazon", "Meta Platforms", "Oracle", "OpenAI",
    "Anthropic", "CoreWeave", "Nebius", "xAI", "Huawei", "CXMT", "YMTC",
    "Rapidus", "삼성전자", "하이닉스", "三星", "海力士",
    # Terms
    "HBM", "DRAM", "NAND", "DDR", "LPDDR", "GDDR", "CoWoS", "SoIC", "EUV",
    "High-NA", "DUV", "wafer", "substrate", "ABF", "glass core", "packaging",
    "OSAT", "probe station", "foundry", "2nm", "3nm", "N2", "A16", "18A",
    "14A", "GPU", "TPU", "XPU", "ASIC", "accelerator", "Blackwell", "Rubin",
    "Vera", "Instinct", "Trainium", "Maia", "MTIA", "Tomahawk", "Jericho",
    "Ethernet", "InfiniBand", "NVLink", "UALink", "optical", "transceiver",
    "CPO", "co-packaged", "silicon photonics", "photonic", "PIC", "laser",
    "EML", "800G", "1.6T", "3.2T", "AEC", "backplane", "liquid cooling",
    "CDU", "cold plate", "UPS", "transformer", "switchgear", "gas turbine",
    "gigawatt", "GW", "megawatt", "MW", "data center", "datacenter", "capex",
    "hyperscaler", "neocloud", "colocation", "PPA", "interconnection",
    "wafer fab equipment", "WFE",
]

# Step 5. Verbatim from the prompt. Two of these look like typos - see
# scripts/README.md, "Unruled carry-overs". They are implemented as written
# because correcting a match string is a rule change, and rule changes are
# Mitchell's call, not this script's.
ANTHROPIC_STRINGS = ["Anthropic", "Claude", "앱트로픽", "安人比"]

# Step 4.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "from", "fbclid", "gclid", "ref", "share_id",
}

X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com",
           "mobile.twitter.com", "t.co"}

USER_AGENT = ("Mozilla/5.0 (X Sweep intake clerk; +portfolio-routines) "
              "Python-urllib")


# --------------------------------------------------------------------------
# Matching (prompt: MATCHING RULES)
# --------------------------------------------------------------------------

def _is_cjk(text):
    """True if the term contains any CJK / Hangul / Kana character.

    Prompt: 'CJK strings match as substrings, since those scripts have no word
    boundaries.'
    """
    for ch in text:
        o = ord(ch)
        if (0x3040 <= o <= 0x30FF or       # Hiragana + Katakana
                0x3400 <= o <= 0x4DBF or   # CJK Ext A
                0x4E00 <= o <= 0x9FFF or   # CJK Unified
                0xAC00 <= o <= 0xD7AF or   # Hangul syllables
                0x1100 <= o <= 0x11FF or   # Hangul Jamo
                0xF900 <= o <= 0xFAFF):    # CJK compatibility
            return True
    return False


def _build_term_regex(term):
    """Compile one match-table term into a regex.

    Whole-word, case-insensitive, optional trailing 's'.

    Leading boundary is asymmetric (dry run 2, decision (b)):
      - term starts with a letter -> must not be preceded by a letter, so
        '500MW' matches 'MW'.
      - term starts with a digit  -> must not be preceded by a letter OR a
        digit, so '12nm' does not match '2nm'.

    Trailing: a term ENDING IN A LETTER also matches a suffix that starts with
    a digit (prompt v1.3): HBM -> HBM3E, HBM4; LPDDR -> LPDDR6; DDR -> DDR5.
    A suffix starting with a letter does NOT match: Meta does not match
    'metal', PIC does not match 'Picture', ASE does not match 'ASEAN'.
    A term ending in a digit gets no suffix extension.
    """
    if _is_cjk(term):
        return None  # handled as plain substring

    core = re.escape(term)

    if term[0].isdigit():
        lead = r"(?<![0-9A-Za-z])"
    else:
        lead = r"(?<![A-Za-z])"

    if term[-1].isalpha():
        # optional digit-led alphanumeric suffix, then optional plural 's'
        tail_body = r"(?:[0-9][0-9A-Za-z]*)?s?"
    else:
        tail_body = r"s?"

    trail = r"(?![0-9A-Za-z])"
    return re.compile(lead + core + tail_body + trail, re.IGNORECASE)


class Matcher:
    """Compiled owned-name and layer-keyword matchers."""

    def __init__(self):
        self.owned = []  # (ticker, term, regex_or_None)
        for ticker, terms in OWNED_NAMES.items():
            for term in terms:
                self.owned.append((ticker, term, _build_term_regex(term)))
        self.layer = [(t, _build_term_regex(t)) for t in LAYER_KEYWORDS]

    @staticmethod
    def _hit(text, term, rx):
        if rx is None:
            return term in text  # CJK substring
        return rx.search(text) is not None

    def owned_hits(self, text):
        """Tickers matched, in match-table order. [] if none."""
        found = []
        for ticker, term, rx in self.owned:
            if ticker in found:
                continue
            if self._hit(text, term, rx):
                found.append(ticker)
        return found

    def layer_hits(self, text):
        return [t for t, rx in self.layer if self._hit(text, t, rx)]


DIGIT_RE = re.compile(r"[0-9]")  # Step 3B: ASCII digits only.

HANGUL_RE = re.compile(r"[가-힯ᄀ-ᇿ]")
KANA_RE = re.compile(r"[぀-ヿ]")
HAN_RE = re.compile(r"[㐀-䶿一-鿿]")


def detect_script(text):
    """Step 5 Translated From, mechanical half only.

    Reads the POST's script. The 'or says it is a translation' arm of the rule
    is a reading judgment and is left to the model.
    """
    if HANGUL_RE.search(text):
        return "Korean"
    if KANA_RE.search(text):
        return "Japanese"
    if HAN_RE.search(text):
        return "Chinese"
    return None


# --------------------------------------------------------------------------
# URL handling (prompt: Step 4)
# --------------------------------------------------------------------------

def clean_url(url):
    """Strip tracking query params. Keep every other parameter.

    Also strips a fragment that is purely tracking key=value pairs
    (dry run 2, decision (e): '#from=ios'). An ordinary anchor is kept.
    """
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url

    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS]
    query = urllib.parse.urlencode(kept, doseq=True)

    fragment = parts.fragment
    if fragment and "=" in fragment:
        frag_pairs = urllib.parse.parse_qsl(fragment, keep_blank_values=True)
        if frag_pairs and all(k.lower() in TRACKING_PARAMS for k, _ in frag_pairs):
            fragment = ""

    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                    query, fragment))


def is_external(url):
    """Step 3A: an expanded_url not on x.com or twitter.com."""
    if not url:
        return False
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return False
    return host.lower() not in X_HOSTS


def looks_like_pdf(url, content_type, body):
    if body[:5] == b"%PDF-":
        return True
    if content_type and "application/pdf" in content_type.lower():
        return True
    return url.lower().split("?")[0].endswith(".pdf")


# --------------------------------------------------------------------------
# HTML parsing (html.parser, per-file signal.alarm timeout, PDF short-circuit)
# --------------------------------------------------------------------------

class ParseTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise ParseTimeout("parse exceeded the per-file timeout")


class PageParser(HTMLParser):
    """Pulls the mechanical facts off a fetched page.

    Collects: <title>, og:title / og:site_name, published-time metadata,
    JSON-LD blocks, and the visible body text.

    Blocks that the prompt excludes from the Anthropic Flag - sidebars and
    related-links - are skipped for body text: <nav>, <aside>, <footer>,
    <script>, <style>, <template>, <noscript>.
    """

    SKIP_TEXT = {"script", "style", "template", "noscript", "nav", "aside",
                 "footer"}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.title_parts = []
        self.meta = {}
        self.jsonld = []
        self.times = []
        self._text = []
        self._skip_depth = 0
        self._in_title = False
        self._in_ldjson = False
        self._ld_buf = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.SKIP_TEXT:
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._in_ldjson = True
                self._ld_buf = []
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"].strip())

    def handle_startendtag(self, tag, attrs):
        if tag in ("meta", "time"):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self.SKIP_TEXT:
            if tag == "script" and self._in_ldjson:
                self.jsonld.append("".join(self._ld_buf))
                self._in_ldjson = False
            if self._skip_depth:
                self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_ldjson:
            self._ld_buf.append(data)
            return
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        elif data.strip():
            self._text.append(data)

    def body_text(self):
        return re.sub(r"\s+", " ", " ".join(self._text)).strip()

    def title(self):
        return re.sub(r"\s+", " ", "".join(self.title_parts)).strip()


DATE_META_KEYS = [
    "article:published_time", "og:published_time", "datepublished",
    "publishdate", "pubdate", "date", "dc.date", "dc.date.issued",
    "sailthru.date", "parsely-pub-date", "article:modified_time",
]

DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


def _norm_date(raw):
    if not raw:
        return None
    m = DATE_RE.search(raw)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return "%04d-%02d-%02d" % (y, mo, d)


def parse_page(url, content_type, body, timeout_seconds):
    """Parse one fetched page. Returns (info_dict, error_or_None).

    PDF short-circuit: a PDF is recorded and NOT parsed. Per dry run 2
    decision (g), a PDF that downloaded but could not be read is not evidence
    the claim was confirmed, so nothing is extracted from it.

    Per-file timeout via signal.alarm, so one pathological page cannot hang the
    run. Only armed on the main thread of a Unix process.
    """
    info = {"kind": None, "page_title": None, "publisher": None,
            "source_date": None, "body_text": ""}

    if looks_like_pdf(url, content_type, body):
        info["kind"] = "pdf"
        return info, "pdf-short-circuit"

    info["kind"] = "html"

    can_alarm = (hasattr(signal, "SIGALRM")
                 and hasattr(signal, "alarm")
                 and _on_main_thread())
    prev = None
    if can_alarm:
        prev = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(max(1, int(timeout_seconds)))
    try:
        text = _decode(body, content_type)
        p = PageParser()
        p.feed(text)
        p.close()
    except ParseTimeout:
        return info, "parse-timeout"
    except Exception as exc:  # a malformed page must not kill the run
        return info, "parse-error: %s: %s" % (type(exc).__name__, exc)
    finally:
        if can_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev)

    info["page_title"] = p.meta.get("og:title") or p.title() or None
    info["publisher"] = (p.meta.get("og:site_name")
                         or p.meta.get("application-name")
                         or p.meta.get("publisher")
                         or None)
    info["body_text"] = p.body_text()

    date = None
    for key in DATE_META_KEYS:
        date = _norm_date(p.meta.get(key))
        if date:
            break
    if not date:
        for raw in p.times:
            date = _norm_date(raw)
            if date:
                break
    if not date or not info["publisher"] or not info["page_title"]:
        ld_title, ld_pub, ld_date = _from_jsonld(p.jsonld)
        info["page_title"] = info["page_title"] or ld_title
        info["publisher"] = info["publisher"] or ld_pub
        date = date or ld_date
    info["source_date"] = date

    return info, None


def _on_main_thread():
    try:
        import threading
        return threading.current_thread() is threading.main_thread()
    except Exception:
        return False


def _decode(body, content_type):
    enc = None
    if content_type:
        m = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
        if m:
            enc = m.group(1)
    if not enc:
        m = re.search(br"charset=[\"']?([\w-]+)", body[:4096], re.IGNORECASE)
        if m:
            enc = m.group(1).decode("ascii", "ignore")
    for candidate in [enc, "utf-8", "cp949", "big5", "gb18030", "shift_jis"]:
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", "replace")


def _from_jsonld(blocks):
    title = publisher = date = None
    for raw in blocks:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for node in _walk_jsonld(data):
            if not isinstance(node, dict):
                continue
            title = title or _as_text(node.get("headline"))
            date = date or _norm_date(_as_text(node.get("datePublished")))
            pub = node.get("publisher")
            if publisher is None and isinstance(pub, dict):
                publisher = _as_text(pub.get("name"))
            elif publisher is None:
                publisher = _as_text(pub)
    return title, publisher, date


def _walk_jsonld(node):
    if isinstance(node, list):
        for item in node:
            for sub in _walk_jsonld(item):
                yield sub
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "mainEntityOfPage"):
            if key in node:
                for sub in _walk_jsonld(node[key]):
                    yield sub


def _as_text(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

class PageStore:
    """Saves every fetched page to disk and serves cached pages offline."""

    def __init__(self, directory):
        self.dir = directory
        self.manifest_path = os.path.join(directory, "manifest.json")
        self.manifest = {}
        if os.path.isdir(directory) and os.path.exists(self.manifest_path):
            with io.open(self.manifest_path, encoding="utf-8") as fh:
                self.manifest = json.load(fh)

    @staticmethod
    def key(url):
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def get(self, url):
        entry = self.manifest.get(self.key(url))
        if not entry:
            return None
        path = os.path.join(self.dir, entry["file"])
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            entry = dict(entry)
            entry["body"] = fh.read()
            entry["path"] = path
        return entry

    def put(self, url, entry, body):
        if not os.path.isdir(self.dir):
            os.makedirs(self.dir)
        name = self.key(url) + (".pdf" if entry.get("is_pdf") else ".html")
        with open(os.path.join(self.dir, name), "wb") as fh:
            fh.write(body)
        record = {k: v for k, v in entry.items() if k not in ("body", "path")}
        record["file"] = name
        record["url"] = url
        self.manifest[self.key(url)] = record
        with io.open(self.manifest_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.manifest, ensure_ascii=False, indent=1))
        return os.path.join(self.dir, name)


class _Redirects(urllib.request.HTTPRedirectHandler):
    pass


def fetch(url, store, offline, timeout, max_bytes):
    """Fetch one URL. Returns a dict with status, final_url, body, path.

    Follows redirects, so a shortener is recorded at its resolved target
    (dry run 2, decision (d)).
    """
    # Pages are saved under whatever URL was fetched, so a cache lookup tries
    # the raw URL and then its cleaned form.
    for key in (url, clean_url(url)):
        cached = store.get(key) if store else None
        if cached:
            cached["cached"] = True
            return cached
    if offline:
        return {"status": None, "error": "offline: no cached page for this URL",
                "final_url": url, "body": b"", "path": None, "cached": False}

    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,ko;q=0.8,zh;q=0.7,ja;q=0.6",
    })
    opener = urllib.request.build_opener(_Redirects)
    entry = {"status": None, "error": None, "final_url": url, "cached": False}
    body = b""
    try:
        with opener.open(req, timeout=timeout) as resp:
            entry["status"] = resp.getcode()
            entry["final_url"] = resp.geturl()
            entry["content_type"] = resp.headers.get("Content-Type", "")
            body = resp.read(max_bytes)
    except urllib.error.HTTPError as exc:
        entry["status"] = exc.code
        entry["content_type"] = exc.headers.get("Content-Type", "") if exc.headers else ""
        entry["error"] = "HTTP %s" % exc.code
        try:
            body = exc.read(max_bytes)
        except Exception:
            body = b""
    except urllib.error.URLError as exc:
        entry["error"] = _urlerror_text(exc)
        entry["dns_failure"] = _is_dns_failure(exc)
    except Exception as exc:
        entry["error"] = "%s: %s" % (type(exc).__name__, exc)

    entry["bytes"] = len(body)
    entry["is_pdf"] = looks_like_pdf(entry["final_url"],
                                     entry.get("content_type", ""), body)
    path = store.put(url, entry, body) if (store and body) else None
    entry["body"] = body
    entry["path"] = path
    return entry


def _urlerror_text(exc):
    reason = getattr(exc, "reason", exc)
    return "%s: %s" % (type(reason).__name__, reason)


def _is_dns_failure(exc):
    """True when the host does not resolve at all.

    Dry run 2, decision (c): X expanded the in-text ticker '300308.SZ' into
    'https://300308.SZ', a URL that cannot exist. A host that does not resolve
    is not an external source, so the candidate falls back to bucket B rather
    than filing a URL that will never dedup or verify. A connection that is
    refused, reset, or times out is a real host and stays in bucket A,
    Unverified - which is what dry run 2 did with the Sina Finance URL.
    """
    reason = getattr(exc, "reason", None)
    text = str(reason if reason is not None else exc).lower()
    if isinstance(reason, OSError) and getattr(reason, "errno", None) in (-2, -3, -5, 8):
        return True
    return ("name or service not known" in text
            or "nodename nor servname" in text
            or "temporary failure in name resolution" in text
            or "no address associated with hostname" in text)


# --------------------------------------------------------------------------
# Step 1 - PULL
# --------------------------------------------------------------------------

LIST_FIELDS = ("max_results=100"
               "&tweet.fields=created_at,author_id,entities,note_tweet,"
               "referenced_tweets,in_reply_to_user_id,conversation_id"
               "&expansions=author_id,referenced_tweets.id"
               "&user.fields=username,name")


def pull_list(list_id, high_water_mark, max_pages, timeout):
    """Step 1b. Paginate until at or below the high-water mark, or max_pages.

    Returns (pages, notes). Each page is the raw API response body. On a 403
    or 429 the pull stops and the error is recorded verbatim - the prompt says
    do not retry in this run.
    """
    pages, notes = [], {"rate_limit": [], "errors": [], "stopped_on": None}
    token = None
    base = "https://api.x.com/2/lists/%s/tweets?%s" % (list_id, LIST_FIELDS)
    bearer = os.environ.get("X_BEARER_TOKEN")  # normally injected by the proxy

    for page_no in range(1, max_pages + 1):
        url = base + ("&pagination_token=%s" % token if token else "")
        headers = {"User-Agent": USER_AGENT}
        if bearer:
            headers["Authorization"] = "Bearer %s" % bearer
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                notes["rate_limit"].append({
                    "page": page_no,
                    "limit": resp.headers.get("x-rate-limit-limit"),
                    "remaining": resp.headers.get("x-rate-limit-remaining"),
                    "reset": resp.headers.get("x-rate-limit-reset"),
                    "access_level": resp.headers.get("x-access-level"),
                })
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            notes["errors"].append("HTTP %s on page %s: %s" % (exc.code, page_no, detail))
            notes["stopped_on"] = "http-%s" % exc.code
            break
        except Exception as exc:
            notes["errors"].append("page %s: %s: %s" % (page_no, type(exc).__name__, exc))
            notes["stopped_on"] = "error"
            break

        pages.append(payload)
        data = payload.get("data") or []
        if high_water_mark and any(_id_le(t.get("id"), high_water_mark) for t in data):
            notes["stopped_on"] = "high-water-mark"
            break
        token = (payload.get("meta") or {}).get("next_token")
        if not token:
            notes["stopped_on"] = "list-exhausted"
            break
    else:
        notes["stopped_on"] = notes["stopped_on"] or "page-limit"

    return pages, notes


def _id_le(a, b):
    """Snowflake IDs are decimal strings; compare numerically."""
    try:
        return int(a) <= int(b)
    except (TypeError, ValueError):
        return False


def flatten_pages(pages, high_water_mark=None):
    """Merge pages into (posts_by_id, users_by_id, included_by_id)."""
    posts, users, included = OrderedDict(), {}, {}
    for page in pages:
        for user in ((page.get("includes") or {}).get("users") or []):
            users[user["id"]] = user
        for tweet in ((page.get("includes") or {}).get("tweets") or []):
            included[tweet["id"]] = tweet
        for tweet in (page.get("data") or []):
            if high_water_mark and _id_le(tweet.get("id"), high_water_mark):
                continue
            posts[tweet["id"]] = tweet
    return posts, users, included


# --------------------------------------------------------------------------
# Step 2 - SAME-AUTHOR REPLY MERGE
# --------------------------------------------------------------------------

def post_text(tweet):
    """Full text of a post: note_tweet wins over the truncated text."""
    note = (tweet.get("note_tweet") or {}).get("text")
    return note or tweet.get("text") or ""


def external_urls(tweet):
    """Expanded URLs on the post that are not x.com / twitter.com."""
    out = []
    for url in ((tweet.get("entities") or {}).get("urls") or []):
        expanded = url.get("unwound_url") or url.get("expanded_url") or url.get("url")
        if expanded and is_external(expanded) and expanded not in out:
            out.append(expanded)
    return out


BARE_URL_RE = re.compile(r"^\s*(?:https?://\S+\s*)+$")


def carries_text_beyond_url(tweet):
    """Step 2: '...plus R's text if R carries any beyond a bare URL'."""
    text = post_text(tweet)
    stripped = re.sub(r"https?://\S+", " ", text).strip()
    return bool(stripped)


def merge_reply_chains(posts, included):
    """Step 2. Collapse same-author replied_to chains into single candidates.

    Chains deeper than two merge the same way. Returns (candidates, merges).
    """
    parent_of = {}
    for pid, tweet in posts.items():
        for ref in (tweet.get("referenced_tweets") or []):
            if ref.get("type") != "replied_to":
                continue
            parent_id = ref.get("id")
            parent = posts.get(parent_id) or included.get(parent_id)
            if parent and parent.get("author_id") == tweet.get("author_id"):
                if parent_id in posts:  # only merge inside this run's pull
                    parent_of[pid] = parent_id
            break

    def root(pid):
        seen = set()
        while pid in parent_of and pid not in seen:
            seen.add(pid)
            pid = parent_of[pid]
        return pid

    groups = OrderedDict()
    for pid in posts:
        groups.setdefault(root(pid), []).append(pid)

    candidates, merges = [], []
    for root_id, member_ids in groups.items():
        members = sorted(member_ids, key=lambda i: int(i))
        head = posts[members[0]]
        texts = [post_text(head)]
        for mid in members[1:]:
            if carries_text_beyond_url(posts[mid]):
                texts.append(post_text(posts[mid]))

        urls = []
        for mid in members:                       # first external URL in P, then R
            for u in external_urls(posts[mid]):
                if u not in urls:
                    urls.append(u)
        if not urls:                              # then either one's quoted post
            for mid in members:
                for ref in (posts[mid].get("referenced_tweets") or []):
                    if ref.get("type") == "quoted":
                        quoted = included.get(ref.get("id"))
                        if quoted:
                            for u in external_urls(quoted):
                                if u not in urls:
                                    urls.append(u)

        quoted_texts = []
        for mid in members:
            for ref in (posts[mid].get("referenced_tweets") or []):
                if ref.get("type") == "quoted":
                    quoted = included.get(ref.get("id"))
                    if quoted:
                        quoted_texts.append(post_text(quoted))

        candidates.append({
            "post_ids": members,
            "head_id": members[0],
            "author_id": head.get("author_id"),
            "created_at": head.get("created_at"),
            "raw_post_text": "\n\n".join(t for t in texts if t),
            "quoted_text": "\n\n".join(quoted_texts),
            "external_urls": urls,
        })
        if len(members) > 1:
            merges.append({"kept": members[0], "merged": members[1:]})

    candidates.sort(key=lambda c: (c["created_at"] or "", int(c["head_id"])))
    return candidates, merges


# --------------------------------------------------------------------------
# Steps 3 to 6
# --------------------------------------------------------------------------

def build_records(candidates, users, matcher, store, args):
    """Steps 3, 4 and 5 (mechanical fields only). Returns (records, discarded, meta bits)."""
    records, discarded = [], []
    fetch_failures, parse_failures = [], []
    reclassified = []

    for cand in candidates:
        user = users.get(cand["author_id"]) or {}
        handle = "@" + user.get("username", cand["author_id"] or "unknown")

        # Prompt: match against post text, note_tweet, AND the quoted post's text.
        match_text = "\n".join([cand["raw_post_text"], cand["quoted_text"]]).strip()
        owned = matcher.owned_hits(match_text)
        layers = matcher.layer_hits(match_text)

        url = cand["external_urls"][0] if cand["external_urls"] else None
        page = None
        bucket = "A" if url else "B"

        if bucket == "A":
            result = fetch(url, store, args.offline, args.fetch_timeout, args.max_bytes)
            if result.get("dns_failure"):
                # decision (c): the host does not exist, so this is not a source.
                reclassified.append({"post_url": _post_url(handle, cand["head_id"]),
                                     "url": url, "reason": "host does not resolve"})
                fetch_failures.append({"url": url, "status": None,
                                       "error": result.get("error"),
                                       "post_id": cand["head_id"]})
                bucket, url, page = "B", None, None
            else:
                final = result.get("final_url") or url
                cleaned = clean_url(final)
                body = result.get("body") or b""
                info, perr = ({"kind": None, "page_title": None, "publisher": None,
                               "source_date": None, "body_text": ""}, None)
                if body:
                    info, perr = parse_page(cleaned, result.get("content_type", ""),
                                            body, args.parse_timeout)
                status = result.get("status")
                ok = status == 200 and bool(body)
                if not ok:
                    fetch_failures.append({"url": cleaned, "status": status,
                                           "error": result.get("error") or "empty body",
                                           "post_id": cand["head_id"]})
                if perr:
                    parse_failures.append({"url": cleaned, "reason": perr,
                                           "post_id": cand["head_id"]})
                url = cleaned
                page = {"info": info, "status": status, "ok": ok,
                        "parse_error": perr, "path": result.get("path"),
                        "cached": result.get("cached", False)}

        if bucket == "B":
            # Step 3B gate: at least one digit AND at least one match-table or
            # layer-keyword string.
            if not (DIGIT_RE.search(match_text) and (owned or layers)):
                discarded.append({
                    "post_url": _post_url(handle, cand["head_id"]),
                    "account": handle,
                    "bucket": "C",
                    "reason": ("no digit" if not DIGIT_RE.search(match_text)
                               else "no owned-name or layer-keyword match"),
                })
                continue

        records.append(_record(cand, handle, bucket, url, page, owned,
                               match_text, args))

    return records, discarded, fetch_failures, parse_failures, reclassified


def _post_url(handle, post_id):
    return "https://x.com/%s/status/%s" % (handle.lstrip("@"), post_id)


def _record(cand, handle, bucket, url, page, owned, match_text, args):
    """Step 5, mechanical fields only.

    Headline and Dated Claim are NOT written - they are the model's, from
    raw_post_text and the fetched page. Layer never appears at all.
    """
    info = (page or {}).get("info") or {}
    page_body = info.get("body_text") or ""

    anthropic = any(s in match_text or s in page_body for s in ANTHROPIC_STRINGS)

    if bucket == "A":
        publisher = info.get("publisher")
        source_date = info.get("source_date")
        # Step 4: 'Fetch fails or is paywalled: file Unverified, keep the URL.'
        # 'Source fetched' means the fetch CONFIRMED the claim (dry run 2,
        # decision (g)) - that is a reading judgment, so the script leaves
        # verification null and the model decides. Where the prompt forces
        # Unverified mechanically, the script says Unverified.
        if not (page or {}).get("ok") or (page or {}).get("parse_error"):
            verification = "Unverified"
        else:
            verification = None
    else:
        publisher = handle
        source_date = None
        verification = "Unverified"   # Step 5, bucket B: always Unverified.

    return {
        "post_url": _post_url(handle, cand["head_id"]),
        "account": [handle],
        "captured": cand["created_at"],
        "bucket": bucket,
        "underlying_source_url": url,
        "publisher": publisher,
        "source_date": source_date,
        "verification": verification,
        "owned_name_hits": owned or ["None"],
        "anthropic_flag": anthropic,
        "translated_from": detect_script(cand["raw_post_text"]),
        "raw_post_text": cand["raw_post_text"],
        "fetched_page_path": (page or {}).get("path"),
        # Working fields the model needs; not Signal Inbox columns.
        "_post_ids": cand["post_ids"],
        "_quoted_text": cand["quoted_text"],
        "_page_title": info.get("page_title"),
        "_fetch_status": (page or {}).get("status"),
    }


def dedup(records, existing, merged_groups):
    """Step 6, dedup arms this script can do mechanically.

    Against existing Signal Inbox rows: Post URL, then cleaned Underlying
    Source URL. Within this run: same cleaned Underlying Source URL.

    The 'same Dated Claim from different accounts' arm is NOT done here. The
    script does not write Dated Claim, so it cannot compare it. Feed the
    model's clusters back with --merged-groups to fold them in.

    Earliest post wins; its Post URL survives; all handles go in Account.
    """
    existing_posts = {r.get("post_url") for r in existing if r.get("post_url")}
    existing_srcs = {clean_url(r["underlying_source_url"])
                     for r in existing if r.get("underlying_source_url")}

    already_filed = []
    live = []
    for rec in records:
        if rec["post_url"] in existing_posts or (
                rec["underlying_source_url"]
                and rec["underlying_source_url"] in existing_srcs):
            already_filed.append({"post_url": rec["post_url"],
                                  "account": rec["account"][0],
                                  "underlying_source_url": rec["underlying_source_url"]})
            continue
        live.append(rec)

    # Group key: cleaned source URL, or a model-supplied group id.
    group_of = {}
    for gid, post_urls in enumerate(merged_groups or []):
        for pu in post_urls:
            group_of[pu] = "model:%d" % gid

    buckets = OrderedDict()
    for rec in live:
        key = group_of.get(rec["post_url"])
        if key is None and rec["underlying_source_url"]:
            key = "url:" + rec["underlying_source_url"]
        if key is None:
            key = "solo:" + rec["post_url"]
        buckets.setdefault(key, []).append(rec)

    kept, clusters = [], []
    for key, group in buckets.items():
        group.sort(key=lambda r: (r["captured"] or "", r["post_url"]))
        winner = group[0]
        if len(group) > 1:
            for other in group[1:]:
                for handle in other["account"]:
                    if handle not in winner["account"]:
                        winner["account"].append(handle)
                winner["_post_ids"] = winner["_post_ids"] + other["_post_ids"]
                # A cross-bucket merge keeps the resolved source (dry run 2,
                # decision (f)): a bucket-A row must not lose its URL to a
                # bucket-B row that happens to be earlier.
                if not winner["underlying_source_url"] and other["underlying_source_url"]:
                    winner["underlying_source_url"] = other["underlying_source_url"]
                    winner["bucket"] = "A"
                    winner["publisher"] = other["publisher"]
                    winner["source_date"] = other["source_date"]
                    winner["verification"] = other["verification"]
                    winner["fetched_page_path"] = other["fetched_page_path"]
                    winner["_page_title"] = other["_page_title"]
                    winner["_fetch_status"] = other["_fetch_status"]
                if other["anthropic_flag"]:
                    winner["anthropic_flag"] = True
                for hit in other["owned_name_hits"]:
                    if hit != "None" and hit not in winner["owned_name_hits"]:
                        if winner["owned_name_hits"] == ["None"]:
                            winner["owned_name_hits"] = []
                        winner["owned_name_hits"].append(hit)
                winner["raw_post_text"] = (winner["raw_post_text"] + "\n\n---\n\n"
                                           + other["raw_post_text"])
            clusters.append({
                "key": key,
                "kept": winner["post_url"],
                "collapsed": [r["post_url"] for r in group[1:]],
                "accounts": list(winner["account"]),
            })
        kept.append(winner)

    return kept, clusters, already_filed


def apply_cap(records, cap):
    """Step 6 cap, prompt v1.3.

    A bucket-B row carrying a live Owned-Name Hit is NEVER dropped. The cap
    applies only to bucket-B rows with Owned-Name Hits = None: keep the most
    recent of those up to NIGHTLY_CAP_NOLINK and drop the rest.
    """
    kept, dropped = [], []
    no_hit = []
    kept_on_owned_name = 0

    for rec in records:
        if rec["bucket"] != "B":
            kept.append(rec)
        elif rec["owned_name_hits"] != ["None"]:
            kept.append(rec)
            kept_on_owned_name += 1
        else:
            no_hit.append(rec)

    no_hit.sort(key=lambda r: (r["captured"] or "", r["post_url"]), reverse=True)
    kept.extend(no_hit[:cap])
    for rec in no_hit[cap:]:
        dropped.append({"post_url": rec["post_url"],
                        "account": rec["account"],
                        "captured": rec["captured"],
                        "bucket": rec["bucket"],
                        "owned_name_hits": rec["owned_name_hits"]})

    kept.sort(key=lambda r: (r["captured"] or "", r["post_url"]))
    return kept, dropped, {
        "bucket_b_kept_on_owned_name_hit": kept_on_owned_name,
        "bucket_b_kept_under_cap": len(no_hit[:cap]),
        "bucket_b_dropped_by_cap": len(dropped),
        "cap": cap,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="candidates.json")
    ap.add_argument("--pages-dir", default="pages",
                    help="where fetched pages are saved and read back")
    ap.add_argument("--posts", help="JSON file of already-pulled API pages; "
                                    "skips Step 1 entirely")
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network; serve fetches from --pages-dir")
    ap.add_argument("--existing", help="JSON file of existing Signal Inbox rows "
                                       "for the cross-run dedup arm")
    ap.add_argument("--merged-groups", help="JSON file: list of lists of Post URLs "
                                            "the model deduped on Dated Claim")
    ap.add_argument("--high-water-mark", default=os.environ.get("X_HIGH_WATER_MARK"))
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--cap", type=int, default=NIGHTLY_CAP_NOLINK)
    ap.add_argument("--list-id", default=X_LIST_ID)
    ap.add_argument("--fetch-timeout", type=float, default=30.0)
    ap.add_argument("--parse-timeout", type=int, default=20,
                    help="per-file signal.alarm timeout, seconds")
    ap.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    args = ap.parse_args(argv)

    # Step 1
    if args.posts:
        with io.open(args.posts, encoding="utf-8") as fh:
            payload = json.load(fh)
        pages = payload["pages"] if isinstance(payload, dict) else payload
        pull_notes = {"rate_limit": [], "errors": [],
                      "stopped_on": "loaded-from-file", "source": args.posts}
    elif args.offline:
        sys.stderr.write("--offline requires --posts\n")
        return 2
    else:
        pages, pull_notes = pull_list(args.list_id, args.high_water_mark,
                                      args.max_pages, args.fetch_timeout)

    posts, users, included = flatten_pages(pages, args.high_water_mark)

    # Step 2
    candidates, merges = merge_reply_chains(posts, included)

    # Steps 3 to 5
    store = PageStore(args.pages_dir) if args.pages_dir else None
    matcher = Matcher()
    records, discarded, fetch_failures, parse_failures, reclassified = build_records(
        candidates, users, matcher, store, args)

    pre_dedup_buckets = _count_buckets(records)

    # Step 6
    existing = []
    if args.existing:
        with io.open(args.existing, encoding="utf-8") as fh:
            data = json.load(fh)
        existing = data["rows"] if isinstance(data, dict) else data
    merged_groups = None
    if args.merged_groups:
        with io.open(args.merged_groups, encoding="utf-8") as fh:
            merged_groups = json.load(fh)

    records, clusters, already_filed = dedup(records, existing, merged_groups)
    post_dedup_buckets = _count_buckets(records)
    records, dropped_by_cap, cap_counts = apply_cap(records, args.cap)

    created = [c["created_at"] for c in candidates if c.get("created_at")]
    meta = {
        "prompt_version": "x-sweep v1.3",
        "list_id": args.list_id,
        "high_water_mark_in": args.high_water_mark,
        "newest_post_id": max(posts, key=lambda i: int(i)) if posts else None,
        "pages_pulled": len(pages),
        "posts_pulled": len(posts),
        "pull": pull_notes,
        "merges": {"count": len(merges), "detail": merges},
        "buckets_pre_dedup": pre_dedup_buckets,
        "buckets_post_dedup": post_dedup_buckets,
        "buckets_final": _count_buckets(records),
        "discarded_bucket_c": {"count": len(discarded), "detail": discarded},
        "reclassified_a_to_b": reclassified,
        "dedup": {
            "clusters": clusters,
            "cluster_count": len(clusters),
            "already_filed": already_filed,
            "dated_claim_arm": "NOT PERFORMED - the script does not write Dated "
                               "Claim. Re-run with --merged-groups to fold in "
                               "the model's Dated-Claim clusters.",
        },
        "cap": cap_counts,
        "dropped_by_cap": dropped_by_cap,
        "fetch_failures": fetch_failures,
        "parse_failures": parse_failures,
        "oldest_created_at": min(created) if created else None,
        "newest_created_at": max(created) if created else None,
        "rows_out": len(records),
        "left_to_the_model": ["Headline", "Dated Claim", "Layer (never set)",
                              "Verification where it is null",
                              "Translated From from a stated translation",
                              "Dated-Claim dedup"],
    }

    out = {"meta": meta, "records": records}
    with io.open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")

    sys.stderr.write(
        "pages=%d posts=%d merges=%d A=%d B=%d C=%d clusters=%d "
        "kept_on_owned_name=%d kept_under_cap=%d dropped=%d rows=%d\n" % (
            len(pages), len(posts), len(merges),
            meta["buckets_final"].get("A", 0), meta["buckets_final"].get("B", 0),
            len(discarded), len(clusters),
            cap_counts["bucket_b_kept_on_owned_name_hit"],
            cap_counts["bucket_b_kept_under_cap"],
            cap_counts["bucket_b_dropped_by_cap"], len(records)))
    return 0


def _count_buckets(records):
    counts = {}
    for rec in records:
        counts[rec["bucket"]] = counts.get(rec["bucket"], 0) + 1
    return counts


if __name__ == "__main__":
    sys.exit(main())
