"""Jacksonville Daily Record — Notice of Sale (Foreclosure) public-notice scraper.

Source id : jaxdailyrecord_foreclosures   (PRIMARY EVENT SOURCE)
Portal    : https://legals.jaxdailyrecord.com/  (Notice of Sale - Foreclosure)
Role      : PRIMARY_LEAD_SOURCE. Florida Statutes require a foreclosure sale
            to be advertised in a county newspaper of general circulation; the
            Jacksonville Daily Record is the designated publication for Duval
            County. Each notice carries case number, plaintiff, defendant(s),
            property description, and AUCTION SALE DATE — the latter is the
            field the clerk Official Records index does NOT carry.

Access (recon-confirmed)
------------------------
Server-rendered HTML, stdlib-reachable. Notices appear as <h3> blocks inside
the page; each <h3>Notice of Sale - Foreclosure NNN-NNNNNX</h3> is followed
by the full notice text until the next <h3>. Pagination is per-date; the
default URL serves "daily" notices (currently active publications).

  GET legals.jaxdailyrecord.com/public_notices/publicnotices.php
      ?Category=Notice+of+Sale+-+Foreclosure&mode=daily
  -> ~20-30 notices on the page, in plain text.

Each notice carries (extracted by regex/text-parse):
  - publication_id      (Daily Record's notice ID, e.g. "26-02935D")
  - case_no             (Florida case format "16-YYYY-CA-NNNNNN")
  - plaintiff           (text between "Plaintiff" and "vs.")
  - defendants          (text after "vs." up to "Defendants" / "Defendant")
  - sale_date           (often "on <DATE>", parsed)
  - sale_time
  - property_address    (when present in notice body)
  - legal_description
  - full notice text (kept for evidence)

Wraps each notice per §4.32 and writes to data/raw/<source_id>.jsonl. No
scaffold/ or knowledge_base/ edits. County-side adapter.
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "jaxdailyrecord_foreclosures"
BASE = "https://legals.jaxdailyrecord.com"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/"
              "537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
DEFAULT_TIMEOUT = 60

REQUIRED_FIELDS = ("publication_id",)


class SourceBlockedError(RuntimeError):
    """Raised when the portal returns a blocked / anti-bot response."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean(s: str | None) -> str:
    if not s:
        return ""
    t = htmllib.unescape(re.sub(r"\s+", " ", s)).strip()
    return t


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        body = r.read().decode("utf-8", "replace")
    if "<title>403" in body or "Access Denied" in body:
        raise SourceBlockedError("Jaxdailyrecord returned an access-denied page")
    return body


# Regex for the per-notice block.
_H3_PATTERN = re.compile(
    r"<h3[^>]*>\s*Notice of Sale - Foreclosure\s+([^<]+?)\s*</h3>(.*?)"
    r"(?=<h3|</table\s*>)", re.I | re.S)

_CASE_RE = re.compile(r"Case\s*(?:No\.?|#):?\s*(\d{2}-\d{4}-CA-\d{4,8})", re.I)
_PLAINTIFF_RE = re.compile(
    r"(?:Plaintiff|PLAINTIFF)\s*[\:\,]?\s*\n?\s*"
    r"vs\.?\s*\n", re.I)
_VS_SPLIT = re.compile(r"\bv(?:s|\.)\.?\b", re.I)
_SALE_DATE_RE = re.compile(
    r"(?:I\s*will\s*sell|sale\s*will\s*be\s*held|public\s*sale\s*to\s*the\s*"
    r"highest\s*and\s*best\s*bidder)[^.]*?on\s+"
    r"([A-Z][a-z]+\s+\d{1,2}(?:[a-z]{2})?,?\s+\d{4})",
    re.I | re.S)
_SALE_DATE_FALLBACK = re.compile(
    r"(?:Date of Sale|Sale Date|on)\s*[:\-]?\s*"
    r"([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})", re.I)
_SALE_TIME_RE = re.compile(
    r"at\s*(\d{1,2}:\d{2}\s*[AaPp]\.?\s*[Mm]\.?)", re.I)
_ADDRESS_RE = re.compile(
    r"\b(\d{1,6}\s+[A-Z][A-Za-z0-9\s\.\-/']+?,\s*[A-Z][A-Za-z\s]+?,?\s*FL\s*\d{5}"
    r"(?:-\d{4})?)\b")
_LEGAL_RE = re.compile(
    r"\b(LOT[S]?\s+[A-Z0-9\-,\s]+?(?:BLOCK|BLK)\s+[A-Z0-9\-,\s]+?,\s*[^.]+?\.)",
    re.I)


def _html_to_text(html: str) -> str:
    """Lossy HTML→text. Preserve paragraph/line breaks; strip tags."""
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    s = re.sub(r"</p>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmllib.unescape(s)
    return s


def _parse_month_day_year(s: str) -> str | None:
    """Parse 'September 4, 2026' or 'Sep 4 2026' into ISO YYYY-MM-DD."""
    s = re.sub(r"(\d{1,2})(?:st|nd|rd|th)", r"\1", s)  # strip ordinals
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_notice(notice_id: str, html: str) -> dict:
    """Parse one notice block into canonical fields. Missing fields stay None/''."""
    text = _html_to_text(html)
    text_norm = re.sub(r"\s+", " ", text).strip()

    case_no = ""
    m = _CASE_RE.search(text_norm)
    if m:
        case_no = m.group(1)

    # Plaintiff vs Defendants splitter.
    plaintiff = defendants = ""
    # Heuristic: text around "Plaintiff, vs." pattern.
    sub = re.split(r"Plaintiff\s*,?\s*vs\.?", text_norm, maxsplit=1, flags=re.I)
    if len(sub) == 2:
        # plaintiff is the last segment of sub[0] before "Plaintiff"
        pre = sub[0]
        # Find the last comma-separated entity-like name
        # Often: "<COURT INFO> ... <PLAINTIFF NAME>, Plaintiff, vs. <DEF>, Defendant(s)"
        # Strip leading court junk by taking last ~250 chars before "Plaintiff".
        plaintiff = _clean(pre[-220:].split(",")[-2]) if "," in pre[-220:] else _clean(pre[-220:])
        # defendants: text from after "vs." up to "Defendant" (or first NOTICE/IS HEREBY)
        post = sub[1]
        end_m = re.search(r"\bDefendant[s]?\b|\bNOTICE\b", post, re.I)
        defendants = _clean(post[:end_m.start()].rstrip(", ")) if end_m else _clean(post[:300])

    # Sale date
    sale_date = ""
    m = _SALE_DATE_RE.search(text_norm)
    if not m:
        m = _SALE_DATE_FALLBACK.search(text_norm)
    if m:
        iso = _parse_month_day_year(m.group(1))
        if iso:
            sale_date = iso
    sale_time = ""
    m = _SALE_TIME_RE.search(text_norm)
    if m:
        sale_time = m.group(1)

    # Property address
    property_address = ""
    m = _ADDRESS_RE.search(text_norm)
    if m:
        property_address = m.group(1).strip()

    # Legal description (best effort)
    legal_description = ""
    m = _LEGAL_RE.search(text_norm)
    if m:
        legal_description = m.group(1).strip()

    return {
        "publication_id": notice_id.strip(),
        "case_no": case_no,
        "plaintiff": plaintiff,
        "defendants": defendants,
        "sale_date": sale_date,
        "sale_time": sale_time,
        "property_address": property_address,
        "legal_description": legal_description,
        "doc_type": "NOTICE OF SALE",
        "publication": "Jacksonville Daily Record",
        "county": "Duval",
        "state": "FL",
        "notice_text": text_norm[:6000],   # cap stored size
    }


def normalize_to_wrapped(notice: dict) -> dict:
    instrument = notice["publication_id"]
    missing = [f for f in REQUIRED_FIELDS if not notice.get(f)]
    confidence = 95 if not missing else 55
    if not notice.get("case_no") or not notice.get("sale_date"):
        confidence = min(confidence, 80)
    return {
        "raw_record_id": f"{SOURCE_ID}:{instrument}",
        "source_id": SOURCE_ID,
        "source_url": (f"{BASE}/public_notices/publicnotices.php"
                       f"?Category=Notice+of+Sale+-+Foreclosure&mode=daily"
                       f"#notice-{urllib.parse.quote(instrument)}"),
        "source_fetched_at": _now_iso(),
        "parser_confidence": confidence,
        "raw_payload": notice,
    }


def pull(*, output_path: Path | None = None) -> dict:
    output_path = output_path or REPO_ROOT / "data/raw" / f"{SOURCE_ID}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    url = (f"{BASE}/public_notices/publicnotices.php"
           f"?Category=Notice+of+Sale+-+Foreclosure&mode=daily")
    try:
        body = _fetch(url)
    except SourceBlockedError as e:
        return {"source_id": SOURCE_ID, "status": "BLOCKED", "error": str(e)}
    matches = list(_H3_PATTERN.finditer(body))
    count = 0
    review = 0
    tmp = output_path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for m in matches:
            notice_id = m.group(1).strip()
            html_block = m.group(2)
            notice = parse_notice(notice_id, html_block)
            rec = normalize_to_wrapped(notice)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
            if rec["parser_confidence"] < 80:
                review += 1
    tmp.replace(output_path)
    return {
        "source_id": SOURCE_ID,
        "portal": BASE,
        "url": url,
        "status": "OK",
        "records_written": count,
        "records_routed_to_review": review,
        "output_path": str(output_path.relative_to(REPO_ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Jaxdailyrecord Notice of Sale - Foreclosure adapter")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    out = Path(args.out) if args.out else None
    stats = pull(output_path=out)
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
