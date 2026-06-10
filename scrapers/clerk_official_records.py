"""Duval County Clerk of Courts — Official Records adapter (PRIMARY EVENT SOURCE).

Source id : clerk_official_records   (see config/counties/duval_fl.json)
Portal    : https://or.duvalclerk.com/   (Acclaim — ASP.NET MVC + Kendo UI)
Role      : PRIMARY_LEAD_SOURCE / PRIMARY_EVENT_SOURCE. This is the Phase 3
            first primary event source for the Duval build — recorded distress
            instruments (lis pendens, liens, judgments, tax deeds, certificates
            of title, probate, etc.). Lead rows ORIGINATE here (§13.2). Unlike
            the Phase 2 gis_parcels enrichment adapter, this source can and does
            originate leads.

Access (recon-confirmed, Phase 3)
---------------------------------
The Official Records search is reachable with the Python standard library —
no browser, no SPA wall, no WAF/403, no CAPTCHA. The drive sequence is:

  1. GET  https://or.duvalclerk.com/            -> disclaimer page
  2. POST /search/Disclaimer  (Disclaimer=true) -> sets session cookies
  3. POST /search/SearchTypeRecordDate (RecordDate=M/D/YYYY)
                                                -> stores the search, returns
                                                   the results-grid page
  4. POST /Search/GridResults  (Kendo aspnetmvc-ajax paging params)
                                                -> JSON {"Data":[...],"Total":N}

Each GridResults row is one recorded instrument. The recording index carries
the instrument number, doc type, recording date, the direct/indirect parties,
book/page, and a legal description — but NO street address or parcel id
(clerk records are indexed by name + legal description). The Phase 4 matcher
joins these events to parcels via the gis_parcels enrichment layer.

Contract
--------
Per MASTER_PROMPT §4.32, this scraper NORMALIZES the Acclaim field names into
framework-canonical lowercase fields and writes one wrapped JSON record per
line to data/raw/clerk_official_records.jsonl:

    raw_record_id · source_id · source_url · source_fetched_at ·
    parser_confidence · raw_payload{ canonical recording-event fields }

This adapter pulls the FULL recording index for each requested date. It does
NOT decide which doc types are leads — doc-type -> canonical-type -> source
class (lead / enrichment / negative_signal) classification is the downstream
normalize + translator layer's job (§13, §17, canonical_doc_types.json). An
optional --doc-type filter supports targeted pulls.

Exit codes:  0 success · 4 source blocked / session lost · 1 other error
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ID = "clerk_official_records"
BASE = "https://or.duvalclerk.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# County recorder portals (Acclaim under load) are routinely slow — a short
# per-request timeout guarantees intermittent failures. The daily-refresh that
# motivated this hardening died on a single `URLError: timed out` against a 60s
# ceiling. Default to a generous per-request timeout, and on a transient
# network/timeout/5xx error retry with an INCREASING timeout (v5.5.0 §6.7
# source-resilience pattern). A hard block (403/401) is NOT transient and
# fails fast.
DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 3
BACKOFF_BASE = 2.0          # seconds; doubles each retry (2s, 4s, 8s, ...)
RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})
DEFAULT_PAGE_SIZE = 100

REQUIRED_FIELDS = ("instrument_number", "doc_type", "record_date")


class SourceBlockedError(RuntimeError):
    """Raised when the portal loses the session / returns a blocked response."""


def _log(msg: str) -> None:
    """Diagnostic to stderr — stdout is reserved for the run-stats JSON."""
    print(f"[{SOURCE_ID}] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.upper() in ("", "NULL", "NONE") else s


def _iso_date(raw) -> str:
    """Acclaim RecordDate is 'YYYY/MM/DD'. Normalize to ISO 'YYYY-MM-DD'."""
    s = _clean(raw)
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


# --------------------------------------------------------------------------
# Normalization — Acclaim GridResults row -> §4.32 wrapped record
# --------------------------------------------------------------------------

def normalize_row(row: dict) -> dict:
    """Map one Acclaim GridResults row into the canonical wrapped raw-record."""
    instrument = _clean(row.get("InstrumentNumber"))
    record_date = _iso_date(row.get("RecordDate"))
    doc_type = _clean(row.get("DocTypeDescription"))

    rec_year = rec_month = None
    if record_date:
        rec_year = int(record_date[0:4])
        rec_month = int(record_date[5:7])

    payload = {
        "instrument_number": instrument,
        "doc_type": doc_type,                       # raw label; canonicalized downstream
        "record_date": record_date,
        "recording_year": rec_year,
        "recording_month": rec_month,
        "book_type": _clean(row.get("BookType")),
        "book_page": _clean(row.get("BookPage")),
        # Clerk recordings index two parties. Which one carries the debtor
        # identity is doc-type-specific — the §17 debtor party rules in the
        # translator decide; the scraper just normalizes both sides.
        "direct_name": _clean(row.get("DirectName")),
        "indirect_name": _clean(row.get("IndirectName")),
        "legal_description": _clean(row.get("DocLegalDescription")),
        "case_number": _clean(row.get("CaseNumber")),
        "num_pages": row.get("NumberOfPages") if isinstance(row.get("NumberOfPages"), int) else None,
        "transaction_id": row.get("TransactionId"),
        "transaction_item_id": row.get("TransactionItemId"),
        "county": "Duval",
        "state": "FL",
        # No situs address / parcel id in the recording index — resolved by
        # the Phase 4 matcher against gis_parcels enrichment.
        "situs_address": "",
        "parcel_id": "",
    }

    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    confidence = 95 if not missing else 55

    rec = {
        "raw_record_id": f"{SOURCE_ID}:{instrument or ('txn-' + str(row.get('TransactionItemId')))}",
        "source_id": SOURCE_ID,
        "source_url": (
            f"{BASE}/search/SearchTypeInstrumentNumber#instrument={instrument}"
            if instrument else f"about:blank/{SOURCE_ID}/unknown"
        ),
        "source_fetched_at": _now_iso(),
        "parser_confidence": confidence,
        "raw_payload": payload,
    }
    if missing:
        rec["_review_reason"] = "missing required fields: " + ", ".join(missing)
    return rec


def _detect_block(text: str) -> None:
    """Raise SourceBlockedError on an Acclaim session-lost / blocked response."""
    low = text.lower()
    if ("disclaimer" in low and "schfrm" not in low and len(text) < 4000) \
            or "session has expired" in low or "request blocked" in low:
        raise SourceBlockedError("Official Records session lost or access blocked.")


# --------------------------------------------------------------------------
# Live session
# --------------------------------------------------------------------------

class ClerkSession:
    """A disclaimer-accepted Acclaim Official Records browsing session."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES):
        self.timeout = timeout
        self.retries = max(1, retries)
        cj = http.cookiejar.CookieJar()
        self._op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        self._op.addheaders = [("User-Agent", USER_AGENT)]
        self._cj = cj

    def _req(self, path: str, data: bytes | None = None, ajax: bool = False) -> str:
        url = path if path.startswith("http") else BASE + path
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Referer"] = BASE + "/search/SearchTypeRecordDate"

        last_err: Exception | None = None
        for attempt in range(1, self.retries + 1):
            # Grow the per-request timeout on each retry — a portal that's slow
            # right now is often just slow, not down, so give it more time
            # rather than giving up. (HTTPError is a URLError subclass, so the
            # HTTPError handler must come first.)
            timeout = self.timeout * attempt
            req = urllib.request.Request(url, data=data, headers=headers)
            try:
                with self._op.open(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                # A hard block / auth wall is not transient — fail fast.
                if e.code in (403, 401):
                    raise SourceBlockedError(f"HTTP {e.code} from {url}") from e
                if e.code in RETRYABLE_HTTP and attempt < self.retries:
                    last_err = e
                else:
                    raise
            except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
                # urllib wraps a socket timeout in URLError — this is the exact
                # `URLError: timed out` that killed the daily refresh. Retry.
                if attempt < self.retries:
                    last_err = e
                else:
                    raise

            sleep_s = BACKOFF_BASE * (2 ** (attempt - 1))
            _log(f"{url} failed ({last_err}); retry "
                 f"{attempt + 1}/{self.retries} in {sleep_s:.0f}s "
                 f"(next timeout {self.timeout * (attempt + 1)}s)")
            time.sleep(sleep_s)

        # Unreachable — the final attempt re-raises — but keeps type-checkers happy.
        raise last_err if last_err else RuntimeError(f"request to {url} failed")

    def open_session(self) -> None:
        """GET the landing page and POST the records-search disclaimer."""
        self._req("/")
        self._req("/search/Disclaimer", data=b"Disclaimer=true")

    def search_record_date(self, mdy: str) -> None:
        """POST a single-date Record Date search (mdy = 'M/D/YYYY')."""
        body = urllib.parse.urlencode([("RecordDate", mdy)]).encode()
        resp = self._req("/search/SearchTypeRecordDate", data=body, ajax=True)
        if resp.strip().startswith("ShowError"):
            raise RuntimeError(f"Record Date search rejected: {resp.strip()[:160]}")

    def iter_grid_results(self, page_size: int = DEFAULT_PAGE_SIZE, max_rows: int | None = None):
        """Paginate /Search/GridResults, yielding raw Acclaim rows."""
        page, emitted, total = 1, 0, None
        while True:
            body = urllib.parse.urlencode([
                ("sort", ""), ("page", str(page)), ("pageSize", str(page_size)),
                ("group", ""), ("filter", ""), ("aggregate", ""),
            ]).encode()
            raw = self._req("/Search/GridResults", data=body, ajax=True)
            _detect_block(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"GridResults did not return JSON: {e}") from e
            rows = payload.get("Data") or []
            if total is None:
                total = int(payload.get("Total") or 0)
            if not rows:
                return
            for row in rows:
                yield row
                emitted += 1
                if max_rows and emitted >= max_rows:
                    return
            if emitted >= total or len(rows) < page_size:
                return
            page += 1


# --------------------------------------------------------------------------
# Fixture entry point — §05 "Scraper fixture requirement"
# --------------------------------------------------------------------------

FIXTURE_DIR = REPO_ROOT / "scrapers" / "fixtures" / SOURCE_ID


def parse_fixture(fixture_name: str):
    """Parse a saved fixture from scrapers/fixtures/clerk_official_records/.

    Data fixtures are Acclaim GridResults JSON ({"Data":[...],"Total":N}); the
    pagination fixture carries {"pages":[...]}. blocked_session raises
    SourceBlockedError; document_download returns an N/A marker (this adapter
    builds the lead index from recording metadata, not document images).
    """
    path = FIXTURE_DIR / fixture_name
    data = json.loads(path.read_text(encoding="utf-8"))

    if fixture_name == "blocked_session.json":
        _detect_block(data.get("body", ""))
        raise SourceBlockedError("blocked_session fixture did not trip the detector")

    if fixture_name == "document_download.json":
        return [{"_not_applicable": True, "text_extraction_skipped": True,
                 "reason": data.get("reason", "lead index is built from recording "
                                     "metadata; document images not pulled in Phase 3")}]

    if fixture_name == "pagination.json":
        out = []
        for pg in data["pages"]:
            out.extend(normalize_row(r) for r in pg.get("Data", []))
        return out

    return [normalize_row(r) for r in data.get("Data", [])]


# --------------------------------------------------------------------------
# Live run
# --------------------------------------------------------------------------

def _record_dates(date: str | None, days_back: int) -> list[str]:
    """Return the list of 'M/D/YYYY' record dates to pull."""
    if date:
        return [date]
    today = datetime.now(timezone.utc).date()
    return [f"{(today - timedelta(days=n)).month}/"
            f"{(today - timedelta(days=n)).day}/"
            f"{(today - timedelta(days=n)).year}" for n in range(1, days_back + 1)]


def run(*, output_path: Path | None = None, date: str | None = None,
        days_back: int = 1, doc_type: str | None = None,
        max_rows: int | None = None, page_size: int = DEFAULT_PAGE_SIZE,
        timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> dict:
    """Pull recorded instruments and write wrapped records to data/raw/."""
    output_path = output_path or REPO_ROOT / "data" / "raw" / f"{SOURCE_ID}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dates = _record_dates(date, days_back)
    stats = {"source_id": SOURCE_ID, "portal": BASE, "dates": dates,
             "doc_type_filter": doc_type or "(all)",
             "request_timeout_s": timeout, "max_retries": retries,
             "output_path": str(output_path.relative_to(REPO_ROOT))}

    session = ClerkSession(timeout=timeout, retries=retries)
    tmp = output_path.with_suffix(".jsonl.tmp")
    count = review = filtered = deduped = 0
    by_doc_type: dict[str, int] = {}
    # The Acclaim GridResults index returns the SAME instrument more than once
    # when a document is cross-indexed under multiple parties — byte-identical
    # rows that share an instrument number. Our raw_record_id (and the
    # downstream evidence_id) is keyed on that instrument number, which must
    # identify exactly one evidence object (evidence_ledger enforces this), so
    # we collapse repeats here: one recorded instrument -> one wrapped record,
    # as this adapter's §4.32 contract promises. First occurrence wins.
    seen_ids: set[str] = set()
    try:
        session.open_session()
        with open(tmp, "w", encoding="utf-8") as fh:
            for d in dates:
                session.search_record_date(d)
                for row in session.iter_grid_results(page_size=page_size, max_rows=max_rows):
                    rec = normalize_row(row)
                    dt = rec["raw_payload"]["doc_type"]
                    if doc_type and doc_type.upper() not in dt.upper():
                        filtered += 1
                        continue
                    rid = rec["raw_record_id"]
                    if rid in seen_ids:
                        deduped += 1
                        continue
                    seen_ids.add(rid)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    count += 1
                    by_doc_type[dt] = by_doc_type.get(dt, 0) + 1
                    if rec["parser_confidence"] < 80:
                        review += 1
    except SourceBlockedError as e:
        tmp.unlink(missing_ok=True)
        stats.update({"status": "BLOCKED", "error": str(e)})
        return stats
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        stats.update({"status": "ERROR", "error": f"{type(e).__name__}: {e}"})
        return stats

    tmp.replace(output_path)
    if deduped:
        _log(f"collapsed {deduped} duplicate cross-indexed grid row(s) "
             f"(same instrument number returned more than once).")
    stats.update({"status": "OK", "records_written": count,
                  "records_routed_to_review": review,
                  "records_filtered_out": filtered,
                  "records_deduped": deduped,
                  "doc_type_distribution": dict(sorted(by_doc_type.items(),
                                                       key=lambda kv: -kv[1]))})
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Duval County Clerk Official Records adapter "
                    "(or.duvalclerk.com — recorded distress instruments).")
    parser.add_argument("--out", default=None,
                        help="Output JSONL. Default: data/raw/clerk_official_records.jsonl")
    parser.add_argument("--date", default=None,
                        help="Single record date, M/D/YYYY. Overrides --days-back.")
    parser.add_argument("--days-back", type=int, default=1,
                        help="Pull this many days ending yesterday (default 1).")
    parser.add_argument("--doc-type", default=None,
                        help="Optional doc-type substring filter (e.g. 'LIS PENDENS').")
    parser.add_argument("--max-rows", type=int, default=None,
                        help="Cap on rows per date (bounded sample / testing).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-request timeout in seconds (default {DEFAULT_TIMEOUT}; "
                             "grows on each retry).")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                        help=f"Attempts per request before giving up "
                             f"(default {DEFAULT_RETRIES}, with exponential backoff).")
    args = parser.parse_args()

    try:
        stats = run(output_path=Path(args.out) if args.out else None,
                    date=args.date, days_back=args.days_back,
                    doc_type=args.doc_type, max_rows=args.max_rows,
                    timeout=args.timeout, retries=args.retries)
    except SourceBlockedError as e:
        print(json.dumps({"source_id": SOURCE_ID, "status": "BLOCKED",
                          "error": str(e)}, indent=2))
        return 4

    print(json.dumps(stats, indent=2))
    if stats.get("status") == "BLOCKED":
        return 4
    return 0 if stats.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
