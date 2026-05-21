"""Duval County (City of Jacksonville / JaxGIS) parcel enrichment adapter.

Source id : gis_parcels   (see config/counties/duval_fl.json)
Portal    : https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer
Layer     : 0  ("Parcels" — 405,716 polygon features, 74 fields)
Role      : ENRICHMENT_SOURCE. This adapter NEVER originates a lead
            (13_lead_origination_contract.md §13.4.1). It produces parcel
            STATE that decorates leads created by primary event sources.

This is the Phase 2 first adapter for the Duval County build — the easiest
source in the recon Source-of-Record Matrix: an open, documented ArcGIS REST
API, reachable with the standard library (no browser, no SPA, no hidden API).

Contract
--------
Per MASTER_PROMPT §4.32 (scraper-to-translator data contract), this scraper
NORMALIZES the COJ field names into framework-canonical lowercase field names
and writes one wrapped JSON record per line to data/raw/gis_parcels.jsonl:

    {
      "raw_record_id":   "gis_parcels:<re_nospace>",
      "source_id":       "gis_parcels",
      "source_url":      "<ArcGIS query deep-link to this feature>",
      "source_fetched_at": "<ISO 8601 UTC>",
      "parser_confidence": <0..100>,
      "raw_payload":     { <framework-canonical normalized fields> }
    }

A downstream translator consumes data/raw/gis_parcels.jsonl; this adapter does
not emit signals or leads.

COJ field -> canonical mapping
------------------------------
    RE_NOSPACE                  -> parcel_id
    LNAMEOWNER (+ LNAME2)       -> owner_name
    LONGNAME (+ UNIT_NO)        -> situs_address
    ADDRCITY                    -> situs_city
    ZIPCODE                     -> situs_zip
    MAILADDR1/2/3               -> owner_mailing_addr1
    MAILCITY/MAILSTATE/MAILZIP  -> owner_mailing_city/state/zip
    CAMA_VAL                    -> assessed_value
    TOT_LND_VA                  -> land_value
    TOT_IMPR_V                  -> improvement_value
    SALESLYY/MM/DD              -> last_sale_date  (YYYY-MM-DD)
    DESCPU / PUSE               -> property_class / land_use_code
    ACRES                       -> acreage
    LEGAL1..LEGAL5              -> legal_description
    LAT / LONG                  -> latitude / longitude
The COJ Parcels layer carries no year-built or sale-price field; those
canonical fields are emitted as null (resolved later from parcel_master).

Exit codes
----------
    0  success
    4  source blocked / session expired (per engineering/04 + §05 fixture 7)
    1  other error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scaffold.scrapers._arcgis_featureserver import (  # noqa: E402
    ArcGISFeatureServer,
    ArcGISServerError,
)

SOURCE_ID = "gis_parcels"
SERVICE_URL = "https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer"
LAYER_ID = 0
USER_AGENT = "xcerebro-duval-gis-parcels/0.1 (+private repo)"

# COJ attribute names requested from the layer.
FIELD_LIST = (
    "OBJECTID,RE,RE_NOSPACE,LNAMEOWNER,LNAME2,LONGNAME,UNIT_NO,ADDRCITY,"
    "ZIPCODE,MAILADDR1,MAILADDR2,MAILADDR3,MAILCITY,MAILSTATE,MAILZIP,"
    "PUSE,DESCPU,ACRES,CAMA_VAL,TOT_LND_VA,TOT_BLD_VA,TOT_IMPR_V,CURREXEMPT,"
    "SALESLDD,SALESLMM,SALESLYY,NBBLDGS,LEGAL1,LEGAL2,LEGAL3,LEGAL4,LEGAL5,"
    "LAT,LONG"
)

# Canonical fields a usable parcel record must carry. A record missing any of
# these is routed to review with parser_confidence < 80 (§05 fixture 8).
REQUIRED_FIELDS = ("parcel_id", "situs_address", "owner_name")


class SourceBlockedError(RuntimeError):
    """Raised when the ArcGIS endpoint returns a blocked / token-gated envelope."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean(value) -> str:
    """COJ encodes empty strings as a single space. Normalize to ''."""
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.upper() in ("", "NULL", "NONE") else s


def _num(value):
    """Return a float for a real numeric value, else None. 0 is preserved."""
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def _int_or_none(value):
    f = _num(value)
    return int(f) if f is not None else None


def _sale_date(a: dict):
    """Compose SALESLYY/MM/DD into an ISO date, or None if not a real date."""
    yy, mm, dd = _int_or_none(a.get("SALESLYY")), _int_or_none(a.get("SALESLMM")), _int_or_none(a.get("SALESLDD"))
    if not yy or yy < 1900 or not mm or not 1 <= mm <= 12 or not dd or not 1 <= dd <= 31:
        return None
    return f"{yy:04d}-{mm:02d}-{dd:02d}"


def _owner_name(a: dict) -> str:
    primary = _clean(a.get("LNAMEOWNER"))
    secondary = _clean(a.get("LNAME2"))
    if primary and secondary:
        return f"{primary} & {secondary}"
    return primary or secondary


def _situs_address(a: dict) -> str:
    base = _clean(a.get("LONGNAME"))
    unit = _clean(a.get("UNIT_NO"))
    if base and unit and unit not in base.split():
        return f"{base} {unit}"
    return base


def _mailing_addr(a: dict) -> str:
    lines = [_clean(a.get(k)) for k in ("MAILADDR1", "MAILADDR2", "MAILADDR3")]
    return " ".join(x for x in lines if x)


def _legal(a: dict) -> str:
    parts = [_clean(a.get(k)) for k in ("LEGAL1", "LEGAL2", "LEGAL3", "LEGAL4", "LEGAL5")]
    return " ".join(x for x in parts if x)


def normalize_feature(feature: dict) -> dict:
    """Map one ArcGIS feature into the canonical wrapped raw-record shape.

    Returns the §4.32 wrapped record. parser_confidence drops below 80 when a
    REQUIRED_FIELDS value is missing, routing the record to review rather than
    crashing or fabricating a value.
    """
    a = feature.get("attributes", {}) or {}
    oid = a.get("OBJECTID") or feature.get("_object_id")
    re_nospace = _clean(a.get("RE_NOSPACE")) or _clean(a.get("RE")).replace(" ", "")

    zip_raw = _clean(a.get("ZIPCODE"))
    payload = {
        "parcel_id": re_nospace,
        "re_number": _clean(a.get("RE")),
        "owner_name": _owner_name(a),
        "owner_mailing_addr1": _mailing_addr(a),
        "owner_mailing_city": _clean(a.get("MAILCITY")),
        "owner_mailing_state": _clean(a.get("MAILSTATE")),
        "owner_mailing_zip": _clean(a.get("MAILZIP")),
        "situs_address": _situs_address(a),
        "situs_city": _clean(a.get("ADDRCITY")),
        "situs_state": "FL",
        "situs_zip": zip_raw,
        "year_built": None,                       # not exposed by this layer
        "assessed_value": _num(a.get("CAMA_VAL")),
        "land_value": _num(a.get("TOT_LND_VA")),
        "improvement_value": _num(a.get("TOT_IMPR_V")),
        "building_value": _num(a.get("TOT_BLD_VA")),
        "current_exemption": _num(a.get("CURREXEMPT")),
        "last_sale_date": _sale_date(a),
        "last_sale_price": None,                  # not exposed by this layer
        "deed_book": None,
        "deed_page": None,
        "property_class": _clean(a.get("DESCPU")),
        "land_use_code": _clean(a.get("PUSE")),
        "acreage": _num(a.get("ACRES")),
        "num_buildings": _int_or_none(a.get("NBBLDGS")),
        "legal_description": _legal(a),
        "latitude": _num(a.get("LAT")),
        "longitude": _num(a.get("LONG")),
    }

    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    confidence = 95 if not missing else 55

    deep_link = (
        f"{SERVICE_URL}/{LAYER_ID}/query?objectIds={oid}&outFields=*&f=json"
        if oid is not None
        else f"about:blank/{SOURCE_ID}/{re_nospace or 'unknown'}"
    )
    rec = {
        "raw_record_id": f"{SOURCE_ID}:{re_nospace or ('oid-' + str(oid))}",
        "source_id": SOURCE_ID,
        "source_url": deep_link,
        "source_fetched_at": _now_iso(),
        "parser_confidence": confidence,
        "raw_payload": payload,
    }
    if missing:
        rec["_review_reason"] = "missing required fields: " + ", ".join(missing)
    return rec


def _detect_block(response: dict) -> None:
    """Raise SourceBlockedError on an ArcGIS token / auth error envelope."""
    err = response.get("error") if isinstance(response, dict) else None
    if err and int(err.get("code", 0)) in (499, 498, 403):
        raise SourceBlockedError(f"ArcGIS access blocked: {err.get('message')}")


# --------------------------------------------------------------------------
# Fixture entry point — §05 verification_and_rollback.md "Scraper fixture
# requirement". The harness (tests/test_scrapers.py) calls parse_fixture().
# --------------------------------------------------------------------------

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / SOURCE_ID


def _features_from_pages(pages: list) -> list:
    """Replay one or more ArcGIS response pages through the FeatureServer
    pagination logic using an injected fetch_fn, returning wrapped records."""
    state = {"i": 0}

    def fetch_fn(url: str, params: dict) -> dict:
        # After the real pages are exhausted, return an empty page so the
        # FeatureServer pagination loop terminates cleanly.
        if state["i"] >= len(pages):
            return {"features": []}
        page = pages[state["i"]]
        state["i"] += 1
        _detect_block(page)
        return page

    server = ArcGISFeatureServer(SERVICE_URL, fetch_fn=fetch_fn, page_size=2)
    return [normalize_feature(f) for f in server.iter_features(LAYER_ID, out_fields=FIELD_LIST, return_geometry=False)]


def parse_fixture(fixture_name: str):
    """Parse a saved fixture from tests/fixtures/gis_parcels/.

    Returns a list of wrapped records for the data fixtures. For
    blocked_session.json it raises SourceBlockedError (the harness maps this to
    exit code 4). For document_download.json it returns a not-applicable marker
    — the COJ Parcels layer is a metadata API with no document payload.
    """
    path = FIXTURE_DIR / fixture_name
    data = json.loads(path.read_text(encoding="utf-8"))

    if fixture_name == "blocked_session.json":
        _detect_block(data)                       # raises SourceBlockedError
        return []

    if fixture_name == "document_download.json":
        # ArcGIS enrichment API — no document layer. Honest N/A marker.
        return [{"_not_applicable": True,
                 "text_extraction_skipped": True,
                 "reason": data.get("reason", "enrichment API has no documents")}]

    if fixture_name == "pagination.json":
        return _features_from_pages(data["pages"])

    # empty / single / multiple / record_detail / malformed
    return [normalize_feature(f) for f in data.get("features", [])]


# --------------------------------------------------------------------------
# Live run
# --------------------------------------------------------------------------

def run(*, output_path: Path | None = None, limit: int | None = None,
        re_numbers: list | None = None, where: str | None = None,
        fetch_fn=None) -> dict:
    """Pull COJ parcels and write wrapped records to data/raw/gis_parcels.jsonl.

    limit       — cap on features pulled (bounded sample / Phase 2 testing).
    re_numbers  — pull only these RE_NOSPACE parcels (targeted enrichment).
    where       — raw ArcGIS WHERE clause override.
    """
    output_path = output_path or REPO_ROOT / "data" / "raw" / f"{SOURCE_ID}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if where:
        where_clause = where
    elif re_numbers:
        quoted = ",".join("'" + r.replace("'", "''") + "'" for r in re_numbers)
        where_clause = f"RE_NOSPACE IN ({quoted})"
    else:
        where_clause = "1=1"

    server = ArcGISFeatureServer(SERVICE_URL, user_agent=USER_AGENT, fetch_fn=fetch_fn)
    stats = {"source_id": SOURCE_ID, "service_url": SERVICE_URL,
             "layer_id": LAYER_ID, "where": where_clause,
             "output_path": str(output_path.relative_to(REPO_ROOT))}

    tmp = output_path.with_suffix(".jsonl.tmp")
    count = review = 0
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for feat in server.iter_features(LAYER_ID, where=where_clause,
                                             out_fields=FIELD_LIST,
                                             return_geometry=False,
                                             max_features=limit):
                rec = normalize_feature(feat)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
                if rec["parser_confidence"] < 80:
                    review += 1
    except ArcGISServerError as e:
        tmp.unlink(missing_ok=True)
        if int(getattr(e, "code", 0)) in (499, 498, 403):
            stats["status"] = "BLOCKED"
            stats["error"] = str(e)
            return stats
        stats["status"] = "ERROR"
        stats["error"] = str(e)
        return stats

    tmp.replace(output_path)
    stats.update({"status": "OK", "records_written": count,
                  "records_routed_to_review": review})
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Duval County JaxGIS parcel enrichment adapter "
                    "(maps.coj.net CityBiz/Parcels/MapServer layer 0).")
    parser.add_argument("--out", default=None,
                        help="Output JSONL path. Default: data/raw/gis_parcels.jsonl")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap on parcels pulled (bounded sample / testing).")
    parser.add_argument("--re", action="append", default=None, dest="re_numbers",
                        help="Pull only this RE_NOSPACE parcel. Repeat for many.")
    parser.add_argument("--where", default=None,
                        help="Raw ArcGIS WHERE clause override.")
    args = parser.parse_args()

    try:
        stats = run(output_path=Path(args.out) if args.out else None,
                    limit=args.limit, re_numbers=args.re_numbers, where=args.where)
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
