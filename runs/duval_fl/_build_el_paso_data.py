"""Adapter — Duval v5.4.0 staged-pipeline output → operator-dashboard record shape.

Reads:
  runs/duval_fl/build/staged/scored_leads.json   (full scored_lead records)
  runs/duval_fl/build/staged/matched_leads.json  (signals[] per lead)
  data/raw/clerk_official_records.jsonl          (raw doc_type per evidence_id)
  data/raw/gis_parcels.jsonl                     (legal_description, situs_zip)
  data/raw/pa_tax_roll*.jsonl                    (PA enrichment + estate origination)
  data/raw/duval_tax_collector*.jsonl            (TC delinquency origination)
  data/raw/realforeclose*.jsonl, realtaxdeed*.jsonl (RealAuction events)

Writes:
  dashboard/data.json                            (operator-board payload)
  dashboard/data.js                              (window.LEADS = ... for the
                                                  <script src=data.js> path)

Field-naming note: the v5 renderer originated in the El Paso TX build and
ships with `epcad_enrichment_status` keys. We KEEP the key names so the
renderer's enrichment-badge / detail-panel branches work unchanged, but the
DISPLAYED text on the dashboard is rebranded to the Duval source names
("JaxGIS enriched" / "PA tax-roll enriched"). No scaffold/ or
knowledge_base/ edits — county-side only.
"""
from __future__ import annotations
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Import the PA tax-roll owner classifiers so the enrichment-side owner
# attachment uses the same logic as primary origination.
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from scrapers.pa_tax_roll import (   # noqa: E402
    classify_estate_name as _classify_estate_name,
    ENTITY_KEYWORDS_PATTERN as _PA_ENTITY_PAT,
    TRUST_KEYWORDS_PATTERN as _PA_TRUST_PAT,
)


PLACEHOLDER_OWNER_PAT = re.compile(r"unidentified party", re.I)


def _normalize_parcel_id(s: str) -> str:
    """RealAuction "127483-0000" → "1274830000" (PA RE_NOSPACE format)."""
    return re.sub(r"[^0-9]", "", (s or "").strip())


def _is_valid_parcel_id(s: str) -> bool:
    """A valid Duval RE_NOSPACE parcel id is exactly 10 digits. The
    RealAuction scraper occasionally captures the link-button label
    ("Property Appraiser", "MULTIPLE PARCELS") instead of the actual
    parcel number when the auction page hides it behind a JS lookup —
    those strings are rejected here."""
    n = _normalize_parcel_id(s)
    return bool(n) and len(n) == 10 and n.isdigit()


# Street-address normalization for PA address-index lookup.
_ADDR_TOKEN_PAT = re.compile(r"[^A-Z0-9 ]+")
_STREET_ABBR = {
    "AVENUE": "AVE", "STREET": "ST", "DRIVE": "DR", "ROAD": "RD",
    "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR", "BOULEVARD": "BLVD",
    "PLACE": "PL", "PARKWAY": "PKWY", "HIGHWAY": "HWY",
    "TERRACE": "TER", "TRAIL": "TRL",
}
_STREET_ABBR_RE = re.compile(
    r"\b(" + "|".join(_STREET_ABBR) + r")\b", re.I)


def _normalize_street(addr: str) -> str:
    """Normalize a street string for cross-source matching:
       'Property Address:\t2503 Summerfield Ln.' → '2503 SUMMERFIELD LN'.
    Strips punctuation, collapses whitespace, uppercases, abbreviates
    full street-type words to PA-style tokens."""
    if not addr:
        return ""
    s = addr.upper()
    if "PROPERTY ADDRESS:" in s:
        s = s.split("PROPERTY ADDRESS:", 1)[1]
    # Drop city/state/zip tail beyond the first comma (PA address is
    # street-only; jaxdailyrecord includes city/state — strip the tail).
    if "," in s:
        s = s.split(",", 1)[0]
    s = _ADDR_TOKEN_PAT.sub(" ", s)
    s = _STREET_ABBR_RE.sub(lambda m: _STREET_ABBR[m.group(1).upper()], s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_case_suffix(case_no: str) -> str:
    """RealAuction case '16-2018-CA-007777-XXXX-MA' →
    jaxdailyrecord '16-2018-CA-007777' base."""
    if not case_no:
        return ""
    return re.sub(r"-[A-Z]+-[A-Z]+$", "", case_no.strip().upper())


# ---------- legal-description → parcel resolver ----------
# The Acclaim clerk feed gives a compact legal description per recorded
# instrument (e.g. "L 359 WINCHESTER RIDGE PHASE 2 U 5") but no parcel_id.
# The PA tax-roll legal_description carries the same identity in a verbose
# form ("ASHLEY WOODS UNIT ONE LOT 1"). Joining clerk → PA by parsed
# (subdivision, lot, unit, block) recovers the parcel_id for clerk leads
# whose §17 routed REVIEW_REQUIRED for lack of named owner — the lookup
# then drives PA-tax-roll owner enrichment, same pattern as the
# RealForeclose join (owner_source = "jaxgis_legal_description_match",
# i.e. resolution via the JaxGIS-aligned PA legal description).

_NUM_WORDS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
    "ELEVEN": "11", "TWELVE": "12", "THIRTEEN": "13", "FOURTEEN": "14",
    "FIFTEEN": "15", "SIXTEEN": "16", "SEVENTEEN": "17",
    "EIGHTEEN": "18", "NINETEEN": "19", "TWENTY": "20",
    "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6",
    "VII": "7", "VIII": "8", "IX": "9", "X": "10",
}
_PIN_PAT = re.compile(r"\b(?:PIN\s+)?(\d{6}-\d{4})\b", re.I)
# Clerk uses three lot conventions in the wild:
#   "L 359"   (space) — most common
#   "L6"      (no space, run-together)
#   "LOT 25"  (full word)
_CLERK_LOT_PAT = re.compile(
    r"\b(?:LOT\s+|L\s+|L)([0-9]+|[0-9A-Z\-/]{2,})\b", re.I)
_CLERK_BLOCK_PAT = re.compile(
    r"\b(?:BLOCK\s+|BLK\s+|B\s+)([0-9A-Z\-/]+)\b", re.I)
_CLERK_UNIT_PAT = re.compile(
    r"\b(?:UNIT\s+|U\s+)([0-9A-Z\-/]+)\b", re.I)
_PA_LOT_PAT = re.compile(r"\bLOT\s+([0-9A-Z\-/]+)\b", re.I)
_PA_BLOCK_PAT = re.compile(r"\bBLK\s+([0-9A-Z\-/]+)\b", re.I)
_PA_UNIT_PAT = re.compile(
    r"\bUNIT\s+([0-9A-Z\-/]+|" + "|".join(_NUM_WORDS.keys()) + r")\b", re.I)


def _norm_num(s: str) -> str:
    s = (s or "").strip().upper()
    # Strip leading zeros from numeric-only tokens so "01" matches "1".
    if s.isdigit():
        return str(int(s))
    return _NUM_WORDS.get(s, s)


def parse_clerk_legal(legal: str) -> dict | None:
    """Extract {pin, lot, block, unit, subdivision} from a clerk legal-
    description string. Returns None if the string is empty."""
    if not legal:
        return None
    L = legal.upper().strip()
    if L.startswith("PT "):
        L = L[3:]
    pin_m = _PIN_PAT.search(L)
    lot_m = _CLERK_LOT_PAT.search(L)
    block_m = _CLERK_BLOCK_PAT.search(L)
    unit_m = _CLERK_UNIT_PAT.search(L)
    sub = L
    if lot_m:
        sub = L[lot_m.end():].strip()
    if block_m and lot_m and block_m.start() > lot_m.end():
        sub = L[block_m.end():].strip()
    for cut in (" U ", " UNIT ", " SEC ", " SECTION "):
        if cut in sub:
            sub = sub.split(cut)[0].strip()
            break
    sub = re.sub(r"\s+", " ", sub).strip()
    return {
        "pin":         pin_m.group(1) if pin_m else "",
        "lot":         _norm_num(lot_m.group(1)) if lot_m else "",
        "block":       _norm_num(block_m.group(1)) if block_m else "",
        "unit":        _norm_num(unit_m.group(1)) if unit_m else "",
        "subdivision": sub,
    }


def parse_pa_legal(legal: str) -> dict | None:
    """Extract {lot, block, unit, subdivision} from a PA legal-description
    string. Strips the plat-page / section-twp-rng / acreage preamble."""
    if not legal:
        return None
    L = legal.upper().strip()
    L = re.sub(r"^\d+-\d+\s+", "", L)               # plat-page
    L = re.sub(r"^\d+-?\d+[SN]-?\d+[EW]\s+", "", L)  # sec-twp-rng
    L = re.sub(r"^[\d\.]+\s+", "", L)               # acreage
    lot_m = _PA_LOT_PAT.search(L)
    block_m = _PA_BLOCK_PAT.search(L)
    unit_m = _PA_UNIT_PAT.search(L)
    sub = L
    cuts = [m.start() for m in (lot_m, block_m, unit_m) if m]
    if cuts:
        sub = L[:min(cuts)].strip()
    sub = re.sub(r"\s+", " ", sub).strip()
    return {
        "lot":         _norm_num(lot_m.group(1)) if lot_m else "",
        "block":       _norm_num(block_m.group(1)) if block_m else "",
        "unit":        _norm_num(unit_m.group(1)) if unit_m else "",
        "subdivision": sub,
    }


_PHASE_SUFFIX_PAT = re.compile(
    r"\s+(?:PHASE|SEC|SECTION|UNIT)\s+\S+\s*$", re.I)


def _strip_phase_suffix(s: str) -> str:
    """Strip trailing "PHASE X" / "SEC X" / "UNIT X" suffix from a
    subdivision name. Used for the fuzzy fallback when the clerk says
    "LEXINGTON PARK PHASE TWO" but PA records have it as "LEXINGTON PARK"
    or vice-versa."""
    prev = None
    cur = s
    while cur != prev:
        prev = cur
        cur = _PHASE_SUFFIX_PAT.sub("", cur).strip()
    return cur


def build_pa_legal_index(pa_by_pid: dict) -> tuple[dict, dict, dict]:
    """Build three layered indexes over the PA tax-roll legal descriptions:

      strict  : (subdivision, lot, unit) → [parcel_ids]
      no_unit : (subdivision, lot, "")   → [parcel_ids]
      condo   : (subdivision, "", unit)  → [parcel_ids]
      fuzzy   : (subdivision_phase_stripped, lot) → [parcel_ids]

    The resolver tries strict first, then no_unit, then condo, then fuzzy
    — only accepting a hit when exactly one parcel matches the chosen key.
    """
    strict: dict = {}
    no_unit: dict = {}
    condo: dict = {}
    fuzzy: dict = {}
    for pid, p in pa_by_pid.items():
        parsed = parse_pa_legal(p.get("legal_description") or "")
        if not parsed or not parsed["subdivision"]:
            continue
        sub = parsed["subdivision"]
        lot = parsed["lot"]
        unit = parsed["unit"]
        if lot:
            strict.setdefault((sub, lot, unit), []).append(pid)
            no_unit.setdefault((sub, lot, ""), []).append(pid)
            fuzzy.setdefault((_strip_phase_suffix(sub), lot), []).append(pid)
        if unit and not lot:
            condo.setdefault((sub, "", unit), []).append(pid)
    return strict, no_unit, condo, fuzzy


def resolve_parcel_via_legal(
    clerk_legal: str,
    pa_legal_indexes: tuple[dict, dict, dict, dict],
    pa_by_pid: dict,
) -> tuple[str, str]:
    """Resolve a clerk legal-description string to a single parcel_id.

    Returns (parcel_id, resolution_method) where resolution_method is one of:
      "pin"               — explicit PIN in the legal description
      "lot_subdiv_unit"   — matched on subdivision + lot + unit (strict)
      "lot_subdiv"        — matched on subdivision + lot (unit-less)
      "condo_subdiv_unit" — subdivision + unit (condo / no-lot case)
      "fuzzy_subdiv_lot"  — phase-stripped subdivision + lot
      ""                  — no match
    """
    strict, no_unit, condo, fuzzy = pa_legal_indexes
    parsed = parse_clerk_legal(clerk_legal)
    if not parsed:
        return "", ""
    if parsed["pin"]:
        pid = re.sub(r"[^0-9]", "", parsed["pin"])
        if pid and pid in pa_by_pid:
            return pid, "pin"
    sub = parsed["subdivision"]
    lot = parsed["lot"]
    unit = parsed["unit"]
    if sub and lot:
        if unit:
            hits = strict.get((sub, lot, unit), [])
            if len(hits) == 1:
                return hits[0], "lot_subdiv_unit"
        hits = no_unit.get((sub, lot, ""), [])
        if len(hits) == 1:
            return hits[0], "lot_subdiv"
    if sub and unit and not lot:
        hits = condo.get((sub, "", unit), [])
        if len(hits) == 1:
            return hits[0], "condo_subdiv_unit"
    if sub and lot:
        # Phase-stripped fallback — clerk's "LEXINGTON PARK PHASE TWO"
        # may resolve to PA's "LEXINGTON PARK" or vice-versa.
        stripped = _strip_phase_suffix(sub)
        if stripped and stripped != sub:
            hits = fuzzy.get((stripped, lot), [])
            if len(hits) == 1:
                return hits[0], "fuzzy_subdiv_lot"
    return "", ""


def _owner_type_from_name(name: str) -> str:
    """Re-classify owner_type from a name string. Same rules the PA adapter
    uses for estate origination, mirrored here so enrichment-side owners
    surface with a consistent owner_type."""
    if not name:
        return "UNKNOWN"
    if _classify_estate_name(name) == "individual_estate":
        return "ESTATE"
    if _PA_ENTITY_PAT.search(name):
        return "ENTITY"
    if _PA_TRUST_PAT.search(name):
        return "TRUST"
    return "INDIVIDUAL"


SCORED = REPO / "runs/duval_fl/build/staged/scored_leads.json"
MATCHED = REPO / "runs/duval_fl/build/staged/matched_leads.json"
CLERK = REPO / "data/raw/clerk_official_records.jsonl"
JAXDAILY = REPO / "data/raw/jaxdailyrecord_foreclosures.jsonl"
REALFORECLOSE = REPO / "data/raw/realforeclose_duval.jsonl"
REALTAXDEED = REPO / "data/raw/realtaxdeed_duval.jsonl"
GIS = REPO / "data/raw/gis_parcels.jsonl"
OUT_JSON = REPO / "dashboard/data.json"
OUT_JS = REPO / "dashboard/data.js"

# The El Paso renderer keys its "Foreclosure sale window" filter (and the
# soonest-sale-first sort) off signal_type == "foreclosure_notice" AND
# signal.sale_date. Duval's canonical doc types include `notice_of_sale`
# (Florida judicial-foreclosure publication notices). Alias canonicals
# that should render as Foreclosure for the dashboard's purpose.
DASHBOARD_SIGNAL_TYPE_ALIAS = {
    "notice_of_sale": "foreclosure_notice",
    "final_judgment_of_foreclosure": "foreclosure_notice",
    "lis_pendens": "lis_pendens",            # keep distinct; not a sale itself
    "tax_deed": "tax_deed",                  # tax-deed auction (Ch. 197 FS)
    "tax_sale_certificate": "tax_default",   # TC baseline unpaid → cert next
    "tax_foreclosure_notice": "tax_foreclosure",  # TC deed-app in progress
}

SIGNAL_LABELS = {
    "lis_pendens": "Lis Pendens", "lien": "Lien",
    "claim_of_lien": "Claim of Lien", "construction_lien": "Construction Lien",
    "federal_tax_lien": "Federal Tax Lien", "state_tax_lien": "State Tax Lien",
    "judgment_lien": "Judgment Lien", "abstract_of_judgment": "Abstract of Judgment",
    "tax_deed": "Tax Deed", "tax_foreclosure_notice": "Tax Foreclosure Notice",
    "tax_sale_certificate": "Tax Sale Certificate",
    "tax_default": "Tax Default",            # baseline TC delinquency
    "tax_foreclosure": "Tax Foreclosure",    # TC deed-app in progress
    "notice_of_sale": "Notice of Sale", "notice_of_default": "Notice of Default",
    "probate": "Probate", "affidavit_of_heirship": "Affidavit of Heirship",
    "executors_deed": "Executor's Deed",
    # The PA tax-roll estate-origination path maps to administrators_deed
    # canonical (closest universal STRUCTURED rule with GR debtor). On the
    # dashboard, label honestly — it's an estate-titled OWNER name from the
    # tax roll, NOT a recorded administrator's deed.
    "administrators_deed": "Estate-Titled Owner",
    "personal_representative_deed": "Personal Representative's Deed",
    "code_lien": "Code Lien", "mechanics_lien": "Mechanic's Lien",
    "municipal_lien": "Municipal Lien", "hoa_lien": "HOA Lien",
    "hospital_lien": "Hospital Lien", "water_lien": "Water Lien",
    "sheriff_deed": "Sheriff's Deed",
    "sheriff_sale": "Sheriff Sale",
    "eviction_filing": "Eviction Filing",
    "bankruptcy_petition": "Bankruptcy Petition",
    "judgment": "Judgment", "civil_judgment": "Civil Judgment",
    "certificate_of_title_deed": "Certificate of Title (Foreclosure)",
    "code_violation_notice": "Code Violation Notice",
    "notice_contest_of_lien": "Notice of Contest of Lien",
}


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path, "r", encoding="utf-8") if l.strip()]


def _compose_full_addr(street, city, state, zipc):
    parts = [p for p in (street, city, state) if p]
    s = ", ".join(parts) if parts else ""
    if zipc:
        s = (s + " " + str(zipc)).strip() if s else str(zipc)
    return s


def _parse_iso_date(s: str) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def main() -> int:
    print("# Duval -> El Paso renderer adapter")
    scored = json.load(open(SCORED))
    matched = json.load(open(MATCHED))
    print(f"  scored_leads : {len(scored)}")
    print(f"  matched_leads: {len(matched)}")

    # Recency anchor — keys off TODAY (the county refresh date), not the
    # scrape-clock. Every record gets is_new + days_since_event computed
    # against the most recent event date carried on the lead's signals or
    # the lead's primary_event_date.
    refresh_date = date.today()
    cutoff_30d = refresh_date.toordinal() - 30
    print(f"  refresh_date          : {refresh_date.isoformat()}")

    matched_by_id = {m["lead_id"]: m for m in matched}

    # Raw clerk events → doc_type_raw per evidence_id
    raw_doc_type_by_evidence: dict[str, str] = {}
    for rec in _read_jsonl(CLERK):
        rid = rec.get("raw_record_id")
        if rid:
            raw_doc_type_by_evidence[rid] = (
                (rec.get("raw_payload") or {}).get("doc_type", ""))
    print(f"  clerk raw rows indexed: {len(raw_doc_type_by_evidence)}")

    # Jacksonville Daily Record foreclosure notices → sale_date + property_address
    # + case_no by evidence_id, so the renderer's foreclosure-window filter
    # has real sale_dates to filter on.
    jaxdaily_by_evidence: dict[str, dict] = {}
    for rec in _read_jsonl(JAXDAILY):
        rid = rec.get("raw_record_id")
        if rid:
            jaxdaily_by_evidence[rid] = rec.get("raw_payload") or {}
            raw_doc_type_by_evidence[rid] = "NOTICE OF SALE"
    print(f"  jaxdailyrecord rows indexed: {len(jaxdaily_by_evidence)}")

    # PA tax-roll estate-titled-owner index — keyed by evidence_id. These are
    # status-not-event signals; the dashboard suppresses NEW / last-30-days
    # recency for them. is_snapshot_event drives that suppression.
    PA_ESTATES = REPO / "data/raw/pa_tax_roll_estates.jsonl"
    pa_estate_evidence: set[str] = set()
    for rec in _read_jsonl(PA_ESTATES):
        rid = rec.get("raw_record_id")
        if rid:
            pa_estate_evidence.add(rid)
            raw_doc_type_by_evidence[rid] = "ESTATE TITLED OWNER"
    print(f"  pa_tax_roll estate rows    : {len(pa_estate_evidence)}")

    # Tax Collector delinquency index — same snapshot-event suppression
    # applies (the file is a single-year tax-roll snapshot; NEW today would
    # be misleading). Carry per-row balance / deed status / years floor so
    # the dashboard renders + filters on them.
    TC_RAW_PATHS = [
        REPO / "data/raw/duval_tax_collector.jsonl",
        REPO / "data/raw/duval_tax_collector_foreclosure.jsonl",
        REPO / "data/raw/duval_tax_collector_sale.jsonl",
    ]
    tc_by_evidence: dict[str, dict] = {}
    for path in TC_RAW_PATHS:
        for rec in _read_jsonl(path):
            rid = rec.get("raw_record_id")
            if rid:
                tc_by_evidence[rid] = rec.get("raw_payload") or {}
                raw_doc_type_by_evidence[rid] = (
                    rec.get("raw_payload") or {}).get("doc_type", "")
    print(f"  tax_collector rows         : {len(tc_by_evidence)}")

    # RealAuction (foreclosure + tax deed) → sale_date + parcel_id + address +
    # case/cert # by evidence_id, so the foreclosure-window + tax-deed filters
    # have real sale_dates to filter on. Index doc_type_raw too.
    realauction_by_evidence: dict[str, dict] = {}
    for rec in _read_jsonl(REALFORECLOSE):
        rid = rec.get("raw_record_id")
        if rid:
            p = rec.get("raw_payload") or {}
            realauction_by_evidence[rid] = p
            raw_doc_type_by_evidence[rid] = p.get("doc_type") or "FORECLOSURE SALE"
    rf_count = len(realauction_by_evidence)
    for rec in _read_jsonl(REALTAXDEED):
        rid = rec.get("raw_record_id")
        if rid:
            p = rec.get("raw_payload") or {}
            realauction_by_evidence[rid] = p
            raw_doc_type_by_evidence[rid] = p.get("doc_type") or "TAX DEED SALE"
    print(f"  realauction rows indexed   : {len(realauction_by_evidence)} "
          f"(foreclosure={rf_count}, taxdeed={len(realauction_by_evidence)-rf_count})")

    # gis_parcels by parcel_id (for legal_description, situs_zip)
    gis_by_pid: dict[str, dict] = {}
    for rec in _read_jsonl(GIS):
        p = rec.get("raw_payload") or {}
        pid = p.get("parcel_id")
        if pid:
            gis_by_pid[pid] = p
    print(f"  gis_parcels indexed   : {len(gis_by_pid)}")

    # PA tax-roll enrichment by parcel_id — used downstream to attach an
    # owner_of_record to leads whose §17 routed to REVIEW_REQUIRED with a
    # placeholder owner (e.g. "notice_of_sale against unidentified party").
    # Same pattern greene-ny uses for AAR auctions.
    PA_TAX_ROLL = REPO / "data/raw/pa_tax_roll.jsonl"
    pa_by_pid: dict[str, dict] = {}
    for rec in _read_jsonl(PA_TAX_ROLL):
        p = rec.get("raw_payload") or {}
        pid = p.get("parcel_id")
        if pid:
            pa_by_pid[pid] = p
    print(f"  pa_tax_roll enrichment: {len(pa_by_pid)}")

    # Index clerk raw by raw_record_id so we can recover parcel_id from the
    # event-doc when §17 routed to REVIEW (the §19 aggregator drops
    # parcel_id from the lead when the parcel-resolution status is
    # REVIEW_REQUIRED; we re-recover here for ENRICHMENT, not §17).
    clerk_by_evidence: dict[str, dict] = {}
    for rec in _read_jsonl(CLERK):
        rid = rec.get("raw_record_id")
        if rid:
            p = rec.get("raw_payload") or {}
            clerk_by_evidence[rid] = {
                "parcel_id":         (p.get("parcel_id") or "").strip(),
                "situs_address":     (p.get("situs_address") or "").strip(),
                "legal_description": (p.get("legal_description") or "").strip(),
                "instrument_number": (p.get("instrument_number") or "").strip(),
            }

    # Build the PA legal-description → parcel_id index. The clerk feed
    # provides 0% parcel_id but a legal description for distress
    # instruments (LIEN 41%, CERTIFICATE OF TITLE DEED 100%, LIS PENDENS,
    # PROBATE with embedded PIN). Parsing both sides into
    # (subdivision, lot, unit) yields a deterministic join — same identity
    # the JaxGIS Parcels MapServer would expose via its FREE_FORM_LEGAL /
    # PARCEL_LEGAL search fields (we use the local PA copy to avoid 400+
    # ArcGIS round trips).
    pa_legal_indexes = build_pa_legal_index(pa_by_pid)
    print(f"  pa_legal_index keys   : strict={len(pa_legal_indexes[0])}, "
          f"no_unit={len(pa_legal_indexes[1])}, "
          f"condo={len(pa_legal_indexes[2])}, "
          f"fuzzy={len(pa_legal_indexes[3])}")

    # PA address index — normalized street → list[parcel_id]. Used when an
    # event-doc carries a property_address but the parcel_id is missing
    # or invalid (the RealForeclose scraper occasionally captures the
    # "Property Appraiser" link-text instead of the number when the
    # auction page hides it behind a JS lookup).
    pa_by_norm_addr: dict[str, list[str]] = {}
    for pid, p in pa_by_pid.items():
        norm = _normalize_street(p.get("situs_address") or "")
        if norm:
            pa_by_norm_addr.setdefault(norm, []).append(pid)
    print(f"  pa_address_index keys : {len(pa_by_norm_addr)}")

    # jaxdailyrecord cross-source index — RealForeclose carries the long
    # court-case format ("16-2018-CA-007777-XXXX-MA"); jaxdailyrecord
    # publishes the same notice in shorter base form ("16-2018-CA-007777").
    # Joining by base case lifts the property address from the newspaper
    # notice onto the RealForeclose lead when the auction page hid the
    # parcel + address. Both sources are PRIMARY EVENT — this is a
    # cross-source merge, not an enrichment-stage rule violation.
    jaxdaily_by_case_base: dict[str, dict] = {}
    for rec in _read_jsonl(JAXDAILY):
        p = rec.get("raw_payload") or {}
        base = _strip_case_suffix(p.get("case_no") or "")
        if base:
            jaxdaily_by_case_base[base] = p
    print(f"  jaxdaily case_base    : {len(jaxdaily_by_case_base)}")

    records: list[dict] = []
    enriched_count = unenriched_count = review_count = approved_count = 0
    owner_enriched_via_pa = 0
    owner_still_unresolved = 0

    for sl in scored:
        lead_id = sl.get("lead_id")
        ml = matched_by_id.get(lead_id) or {}
        owner_name = sl.get("owner_name") or ""
        owner_type = sl.get("owner_type") or "UNKNOWN"
        parcel_id = sl.get("primary_parcel_id") or ""
        parcel_display = dict(sl.get("parcel_display") or {})
        attributes = sl.get("attributes") or []
        gis = gis_by_pid.get(parcel_id, {}) if parcel_id else {}
        # Always promote the freshest PA tax-roll address / mailing /
        # assessed-value onto parcel_display when the lead has a known
        # parcel. The seam's cached parcel_display in scored_leads.json
        # was built when the upstream PA adapter still dropped house
        # numbers — the dashboard build always trusts the live PA file,
        # so a re-run of the dashboard build (without a full pipeline
        # re-run) still picks up the corrected addresses.
        if parcel_id and parcel_id in pa_by_pid:
            pa_live = pa_by_pid[parcel_id]
            for src_k, dst_k in [
                ("situs_address", "situs_address"),
                ("situs_city", "situs_city"),
                ("situs_state", "situs_state"),
                ("situs_zip", "situs_zip"),
                ("owner_mailing_addr1", "owner_mailing_address"),
                ("owner_mailing_city", "owner_mailing_city"),
                ("owner_mailing_state", "owner_mailing_state"),
                ("owner_mailing_zip", "owner_mailing_zip"),
                ("assessed_value", "assessed_value"),
                ("year_built", "year_built"),
            ]:
                v = pa_live.get(src_k)
                if v not in (None, ""):
                    parcel_display[dst_k] = v

        # ENRICHMENT-side owner resolution. When §17 placed a placeholder
        # owner on the lead ("X against unidentified party" — i.e. the
        # event-document does not name the property owner), join the lead
        # to the PA tax roll by parcel_id and surface the owner of record
        # as ENRICHMENT. §17 stage boundary preserved: §17 still reads
        # only event-document parties; the resolved owner is tracked
        # separately with owner_source recording the resolution path.
        owner_source = "event_document"
        is_placeholder = bool(PLACEHOLDER_OWNER_PAT.search(owner_name))
        if is_placeholder:
            # Step A — recover parcel_id from the raw event-doc directly.
            # The RealAuction adapter occasionally captures the page's
            # "Property Appraiser" link-text instead of the parcel
            # number when the auction page hid it behind JS — we reject
            # any non-10-digit string here.
            recovered_pid_raw = ""
            recovered_situs = ""
            recovered_legal = ""
            recovered_case = ""
            for ev_id in sl.get("evidence_ids") or []:
                if ev_id in realauction_by_evidence:
                    r = realauction_by_evidence[ev_id]
                    if not recovered_pid_raw and _is_valid_parcel_id(
                            r.get("parcel_id") or ""):
                        recovered_pid_raw = r.get("parcel_id") or ""
                    if not recovered_situs:
                        addr = r.get("property_address") or ""
                        if addr.startswith("Property Address:"):
                            addr = addr.split("\t", 1)[-1].replace("\t", " ").strip()
                        recovered_situs = addr
                    if not recovered_case:
                        recovered_case = r.get("case_number") or ""
                elif ev_id in clerk_by_evidence:
                    c = clerk_by_evidence[ev_id]
                    if not recovered_pid_raw and _is_valid_parcel_id(
                            c.get("parcel_id") or ""):
                        recovered_pid_raw = c.get("parcel_id") or ""
                    if not recovered_situs:
                        recovered_situs = c.get("situs_address") or ""
                    if not recovered_legal:
                        recovered_legal = c.get("legal_description") or ""
                elif ev_id in jaxdaily_by_evidence:
                    j = jaxdaily_by_evidence[ev_id]
                    if not recovered_situs:
                        recovered_situs = j.get("property_address") or ""
                    if not recovered_case:
                        recovered_case = j.get("case_no") or ""
            recovered_pid = _normalize_parcel_id(recovered_pid_raw)
            resolution_method = "event_doc_parcel_id" if recovered_pid else ""

            # Step B — legal-description → PA legal index match (clerk).
            if not recovered_pid and recovered_legal:
                resolved_pid, resolution_method = resolve_parcel_via_legal(
                    recovered_legal, pa_legal_indexes, pa_by_pid)
                if resolved_pid:
                    recovered_pid = resolved_pid

            # Step C — jaxdailyrecord cross-source by case base. The
            # RealForeclose auction page sometimes hides BOTH the parcel
            # and the address behind JS; the Jacksonville Daily Record
            # publishes the same Ch. 45 sale notice with the address in
            # plain text. Both are PRIMARY EVENT sources for the same
            # foreclosure — joining by base case lifts the address onto
            # the RealForeclose lead.
            if not recovered_situs and recovered_case:
                base = _strip_case_suffix(recovered_case)
                if base in jaxdaily_by_case_base:
                    jd = jaxdaily_by_case_base[base]
                    recovered_situs = jd.get("property_address") or ""

            # Step D — address-based PA lookup (when parcel still missing).
            # Normalized street match against the PA situs_address index;
            # only accept a UNIQUE match to avoid wrong-house false hits.
            if not recovered_pid and recovered_situs:
                norm = _normalize_street(recovered_situs)
                if norm:
                    hits = pa_by_norm_addr.get(norm, [])
                    if len(hits) == 1:
                        recovered_pid = hits[0]
                        resolution_method = "address_match"

            # Step C — attach PA owner of record when we have any parcel_id.
            if recovered_pid:
                if not parcel_id:
                    parcel_id = recovered_pid
                    gis = gis_by_pid.get(parcel_id, gis)
                pa = pa_by_pid.get(recovered_pid)
                if pa and pa.get("owner_name"):
                    owner_name = pa["owner_name"]
                    owner_type = _owner_type_from_name(owner_name)
                    method_to_source = {
                        "event_doc_parcel_id": "pa_tax_roll",
                        "pin":                 "pa_tax_roll_via_clerk_pin",
                        "lot_subdiv_unit":     "pa_tax_roll_via_legal_strict",
                        "lot_subdiv":          "pa_tax_roll_via_legal_lot",
                        "condo_subdiv_unit":   "pa_tax_roll_via_legal_condo",
                        "fuzzy_subdiv_lot":    "pa_tax_roll_via_legal_fuzzy",
                        "address_match":       "pa_tax_roll_via_address",
                    }
                    owner_source = method_to_source.get(
                        resolution_method,
                        "pa_tax_roll_via_legal_description")
                    is_placeholder = False
                    owner_enriched_via_pa += 1
                    if not parcel_display.get("situs_address"):
                        parcel_display["situs_address"] = pa.get("situs_address")
                        parcel_display["situs_city"] = pa.get("situs_city")
                        parcel_display["situs_state"] = pa.get("situs_state")
                    if not parcel_display.get("owner_mailing_address"):
                        parcel_display["owner_mailing_address"] = pa.get("owner_mailing_addr1")
                        parcel_display["owner_mailing_city"] = pa.get("owner_mailing_city")
                        parcel_display["owner_mailing_state"] = pa.get("owner_mailing_state")
                        parcel_display["owner_mailing_zip"] = pa.get("owner_mailing_zip")
                    if not parcel_display.get("assessed_value"):
                        parcel_display["assessed_value"] = pa.get("assessed_value")
            if is_placeholder:
                # No parcel join, no enrichment recovery — surface the
                # event-doc address (if any) and keep the lead in review.
                if recovered_situs and not parcel_display.get("situs_address"):
                    parcel_display["situs_address"] = recovered_situs
                    parcel_display["situs_state"] = "FL"
                owner_source = "unresolved"
                owner_still_unresolved += 1

        # A lead is in REVIEW only when it is GENUINELY under-resolved
        # after enrichment attempts — no resolved owner. A foreclosure with
        # enrichment-resolved owner + address + sale date is actionable,
        # not "review required". §17's REVIEW routing remains the audit
        # trail (the operator can still see which leads §17 couldn't
        # resolve from the event document alone via owner_source).
        is_owner_resolved = not bool(PLACEHOLDER_OWNER_PAT.search(owner_name))
        underlying_review = (
            sl.get("lead_status") == "REVIEW_REQUIRED"
            or ml.get("parcel_resolution_status") == "REVIEW_REQUIRED"
            or any("review" in (f or "").lower()
                   for f in sl.get("review_flags") or [])
        )
        # is_review (the dashboard's badge / filter trigger) =
        #   §17/§19 said review AND we still don't have an owner.
        is_review = underlying_review and not is_owner_resolved
        parcel_res = (
            "REVIEW_REQUIRED" if is_review
            else "RESOLVED" if parcel_id
            else "UNRESOLVED"
        )

        enrichment = sl.get("enrichment_status") or "UNENRICHED"
        if enrichment == "ENRICHED":
            enriched_count += 1
        else:
            unenriched_count += 1
        if is_review:
            review_count += 1
        if sl.get("lead_status") == "APPROVED_FOR_DASHBOARD":
            approved_count += 1

        # Build signals[] from matched_lead.signals[].
        signals_out = []
        signal_types: list[str] = []
        all_source_urls: set[str] = set()
        all_instruments: list[str] = []
        latest_event_date = sl.get("primary_event_date") or ""
        for s in ml.get("signals", []) or []:
            canon = s.get("canonical_doc_type") or ""
            # Alias certain canonicals to the renderer's expected signal_type
            # name (so the "Foreclosure sale window" filter + the soonest-sale
            # sort work on canonicals that are functionally "foreclosure").
            rendered_type = DASHBOARD_SIGNAL_TYPE_ALIAS.get(canon, canon)
            # Label preference: aliased type label (renderer-facing) wins,
            # then canonical label, then the type itself. That way the
            # dashboard says "Tax Default" not "Tax Sale Certificate" when
            # tax_sale_certificate has been aliased to tax_default.
            label = (SIGNAL_LABELS.get(rendered_type)
                     or SIGNAL_LABELS.get(canon)
                     or s.get("signal_type") or canon)
            evs = s.get("evidence_ids") or []
            # raw doc_type + sale_date lookup by evidence. jaxdailyrecord
            # notices carry sale_date directly in raw_payload.
            doc_type_raw = ""
            sale_date = ""
            jaxd_addr = ""
            jaxd_case = ""
            ra_addr = ""
            ra_case = ""
            ra_cert = ""
            ra_parcel = ""
            ra_status = ""
            ra_opening = None
            ra_assessed = None
            tc_balance = None
            tc_years_floor = None
            tc_deed_status = ""
            tc_deed_app_no = ""
            tc_bankrupt = False
            tc_litigation = False
            tc_tax_year = ""
            for ev in evs:
                if ev in raw_doc_type_by_evidence and not doc_type_raw:
                    doc_type_raw = raw_doc_type_by_evidence[ev]
                if ev in jaxdaily_by_evidence and not sale_date:
                    j = jaxdaily_by_evidence[ev]
                    sale_date = j.get("sale_date") or ""
                    jaxd_addr = j.get("property_address") or ""
                    jaxd_case = j.get("case_no") or ""
                if ev in realauction_by_evidence and not sale_date:
                    r = realauction_by_evidence[ev]
                    sale_date = r.get("sale_date") or r.get("auction_date") or ""
                    raw_addr = r.get("property_address") or ""
                    if raw_addr.startswith("Property Address:"):
                        raw_addr = raw_addr.split("\t", 1)[-1].replace("\t", " ").strip()
                    ra_addr = raw_addr
                    ra_case = r.get("case_number") or ""
                    ra_cert = r.get("certificate_number") or ""
                    ra_parcel = r.get("parcel_id") or ""
                    ra_status = r.get("auction_status") or ""
                    ra_opening = r.get("opening_bid")
                    ra_assessed = r.get("assessed_value")
                if ev in tc_by_evidence:
                    t = tc_by_evidence[ev]
                    if tc_balance is None:
                        tc_balance = t.get("balance_amount")
                        tc_years_floor = t.get("years_delinquent_floor")
                        tc_deed_status = t.get("parcel_deed_status") or ""
                        tc_deed_app_no = t.get("deed_application_no") or ""
                        tc_bankrupt = bool(t.get("bankrupt"))
                        tc_litigation = bool(t.get("litigation"))
                        tc_tax_year = t.get("tax_year") or ""
            urls = s.get("source_urls") or []
            insts = s.get("instrument_numbers") or []
            signal_out = {
                "signal_type": rendered_type,           # renderer-facing
                "canonical_doc_type": canon,            # provenance
                "signal_label": label,
                "signal_confidence": "HIGH",
                "source_id": (s.get("source_ids") or ["clerk_official_records"])[0],
                "count": s.get("count") or 1,
                "source_urls": urls,
                "evidence_ids": evs,
                "instrument_numbers": insts,
                "doc_type_raw": doc_type_raw,
                "recorded_date": s.get("latest_recorded_date") or "",
                "earliest_recorded_date": s.get("earliest_recorded_date") or "",
            }
            if sale_date:
                signal_out["sale_date"] = sale_date
            if jaxd_case and not signal_out.get("case_number"):
                signal_out["case_number"] = jaxd_case
            if ra_case and not signal_out.get("case_number"):
                signal_out["case_number"] = ra_case
            if ra_cert:
                signal_out["certificate_number"] = ra_cert
            if ra_status:
                signal_out["auction_status"] = ra_status
            if ra_opening is not None:
                signal_out["opening_bid"] = ra_opening
            if ra_assessed is not None:
                signal_out["assessed_value"] = ra_assessed
            if tc_balance is not None:
                signal_out["balance_amount"] = tc_balance
                signal_out["years_delinquent_floor"] = tc_years_floor
                signal_out["tax_year"] = tc_tax_year
            if tc_deed_status:
                signal_out["parcel_deed_status"] = tc_deed_status
            if tc_deed_app_no:
                signal_out["deed_application_no"] = tc_deed_app_no
            if tc_bankrupt:
                signal_out["bankrupt"] = True
            if tc_litigation:
                signal_out["litigation"] = True
            signals_out.append(signal_out)
            if rendered_type:
                signal_types.append(rendered_type)
            for u in urls:
                all_source_urls.add(u)
            for ins in insts:
                all_instruments.append(ins)
            # If the row has no property_full_address yet but jaxdailyrecord
            # supplied one in the notice text, promote it onto the record so
            # the dashboard renders an address.
            if jaxd_addr and not parcel_display.get("situs_address"):
                # Promote into the record-level address; this happens AFTER
                # the loop sets street/city/state below. Stash here.
                parcel_display.setdefault("_jaxd_address", jaxd_addr)
            # RealAuction address fallback — same pattern.
            if ra_addr and not parcel_display.get("situs_address"):
                parcel_display.setdefault("_jaxd_address", ra_addr)
            # RealAuction parcel_id fallback for the record-level parcel_id
            # (so the row's display + filter use it).
            if ra_parcel and not parcel_id:
                # Normalize RealAuction parcel "127483-0000" to RE_NOSPACE
                # "1274830000" so it matches gis_by_pid keys.
                parcel_id = ra_parcel.replace("-", "")
                gis = gis_by_pid.get(parcel_id, gis)

        # property + mailing addresses from parcel_display (ENRICHED) or gis;
        # jaxdailyrecord notices carry the address in plain text, used as a
        # fallback when no parcel was matched.
        street = (parcel_display.get("situs_address")
                  or gis.get("situs_address")
                  or parcel_display.get("_jaxd_address") or "")
        city = parcel_display.get("situs_city") or gis.get("situs_city") or ""
        state = parcel_display.get("situs_state") or gis.get("situs_state") or "FL"
        zip_ = gis.get("situs_zip") or ""
        property_full = _compose_full_addr(street, city, state, zip_)

        mail_street = parcel_display.get("owner_mailing_address") or ""
        mail_city = parcel_display.get("owner_mailing_city") or ""
        mail_state = parcel_display.get("owner_mailing_state") or ""
        mail_zip = parcel_display.get("owner_mailing_zip") or ""
        mailing_full = _compose_full_addr(mail_street, mail_city, mail_state,
                                          mail_zip)

        legal = gis.get("legal_description") or ""
        if not legal:
            # fallback: pull from raw clerk event if evidence_id resolvable
            for ev in sl.get("evidence_ids") or []:
                if ev in raw_doc_type_by_evidence:
                    # we don't index legal description from clerk; skip
                    pass

        # Recency — keys off the county recorded/event date, never the scrape
        # clock. The most-recent event date wins (signals[].recorded_date and
        # signals[].sale_date both qualify). is_new == matches the refresh
        # date exactly; recorded_within_30_days == within 30 days backward.
        # Future-dated sale notices are NOT "new" (they describe a future
        # event); they qualify on the sale-window filter instead.
        snapshot_evidence = pa_estate_evidence | set(tc_by_evidence.keys())
        candidate_dates: list[date] = []
        for s in signals_out:
            # PA estate-titled-owner + Tax-Collector delinquency rows are
            # status, not events — their dates are the snapshot date and
            # would falsely flag NEW. Skip them in the recency compute; if
            # the same lead ALSO carries a real recorded signal (lis_pendens,
            # foreclosure_notice, judgment), that signal's date drives NEW
            # / last-30-days correctly.
            ev_ids = s.get("evidence_ids") or []
            if ev_ids and all(e in snapshot_evidence for e in ev_ids):
                continue
            for k in ("recorded_date", "earliest_recorded_date"):
                d_ = _parse_iso_date(s.get(k) or "")
                if d_:
                    candidate_dates.append(d_)
        # latest_event_date carries the lead-level seam-derived primary date.
        # When the lead is snapshot-only, latest_event_date is the snapshot;
        # when it has a non-snapshot primary, that real date drives recency.
        evs = sl.get("evidence_ids") or []
        if not (evs and all(e in snapshot_evidence for e in evs)):
            d_ = _parse_iso_date(latest_event_date)
            if d_:
                candidate_dates.append(d_)
        most_recent_event_date = (max([d for d in candidate_dates
                                       if d <= refresh_date], default=None)
                                  if candidate_dates else None)
        is_new = (most_recent_event_date is not None
                  and most_recent_event_date == refresh_date)
        if most_recent_event_date is not None:
            days_since_event = (refresh_date - most_recent_event_date).days
        else:
            days_since_event = None
        recorded_within_30_days = (
            most_recent_event_date is not None
            and most_recent_event_date.toordinal() >= cutoff_30d
        )

        # has_street_address — true when the lead has a house-number-bearing
        # street (a usable mail-to / drive-by address), not just city/state.
        # A street is considered "real" when it carries at least one digit
        # (PA + clerk addresses all carry the house number on real
        # residential/commercial properties; "US 301 HWY" is a state road
        # without a number and still works — accept any non-blank street
        # token longer than 3 chars).
        has_street_address = bool((street or "").strip()
                                  and len(street.strip()) >= 3)

        rec = {
            "lead_id": lead_id,
            "parcel_resolution_status": parcel_res,
            "epcad_enrichment_status": enrichment,
            "filer_entity": ml.get("filer_entity") or "",
            "parcel_id": parcel_id,
            "owner_name": owner_name,
            "owner_source": owner_source,
            "owner_type": owner_type,
            "has_street_address": has_street_address,
            "property_full_address": property_full,
            "property_street": street,
            "property_city": city,
            "property_state": state,
            "property_zip": str(zip_) if zip_ else "",
            "mailing_full_address": mailing_full,
            "mailing_city": mail_city,
            "mailing_state": mail_state,
            "assessed_value": parcel_display.get("assessed_value"),
            "appraised_value": parcel_display.get("assessed_value"),
            "homestead": None,           # Duval gis_parcels doesn't expose this
            "absentee_owner_flag": "absentee" in attributes,
            "out_of_state_owner_flag": "out_of_state" in attributes,
            "legal_description": legal,
            "signals": signals_out,
            "signal_types": signal_types,
            "source_urls": sorted(all_source_urls),
            "signal_count": len(signals_out),
            "primary_signal": signal_types[0] if signal_types else "",
            "latest_event_date": latest_event_date,
            "most_recent_event_date": (most_recent_event_date.isoformat()
                                       if most_recent_event_date else ""),
            "days_since_event": days_since_event,
            "is_new": is_new,
            "recorded_within_30_days": recorded_within_30_days,
        }
        # Tax-default surface — aggregate TC fields across all signals on
        # the lead so the dashboard can render + filter on them.
        tc_signals = [s for s in signals_out
                      if s.get("balance_amount") is not None
                      or s.get("years_delinquent_floor") is not None]
        if tc_signals:
            total_bal = sum((s.get("balance_amount") or 0) for s in tc_signals)
            max_years = max(
                (s.get("years_delinquent_floor") or 0) for s in tc_signals)
            deed_statuses = {s.get("parcel_deed_status") for s in tc_signals
                             if s.get("parcel_deed_status")}
            rec.update({
                "tax_default": True,
                "tax_balance_due": total_bal,
                "years_delinquent_floor": max_years,
                "parcel_deed_status": (next(iter(deed_statuses))
                                        if deed_statuses else None),
                "tax_bankrupt": any(s.get("bankrupt") for s in tc_signals),
                "tax_litigation": any(s.get("litigation") for s in tc_signals),
            })
        else:
            rec.update({
                "tax_default": False,
                "tax_balance_due": None,
                "years_delinquent_floor": None,
            })
        records.append(rec)

    new_count = sum(1 for r in records if r.get("is_new"))
    last_30d_count = sum(1 for r in records if r.get("recorded_within_30_days"))
    owner_source_dist: dict = {}
    for r in records:
        src = r.get("owner_source") or "event_document"
        owner_source_dist[src] = owner_source_dist.get(src, 0) + 1
    addr_resolved = sum(1 for r in records if r.get("has_street_address"))
    addr_unresolved = len(records) - addr_resolved

    # Tax-default surface for top-stats + filters.
    tax_default_count = sum(1 for r in records if r.get("tax_default"))
    tax_balance_total = round(sum(
        (r.get("tax_balance_due") or 0) for r in records if r.get("tax_default")
    ), 2)
    years_dist: dict = {}
    for r in records:
        if not r.get("tax_default"):
            continue
        y = r.get("years_delinquent_floor") or 0
        bucket = "5+" if y >= 5 else str(y)
        years_dist[bucket] = years_dist.get(bucket, 0) + 1
    tax_fcl_count = sum(
        1 for r in records
        if any(s.get("signal_type") == "tax_foreclosure"
               for s in (r.get("signals") or [])))
    tax_sale_count = sum(
        1 for r in records
        if any(s.get("signal_type") == "tax_deed"
               for s in (r.get("signals") or [])))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        "refresh_date": refresh_date.isoformat(),
        "new_leads": new_count,
        "last_30d_leads": last_30d_count,
        "owner_source_distribution": dict(sorted(owner_source_dist.items())),
        "address_resolved_leads": addr_resolved,
        "address_unresolved_leads": addr_unresolved,
        "tax_default_leads": tax_default_count,
        "tax_balance_total_owed": tax_balance_total,
        "tax_default_years_distribution": dict(sorted(years_dist.items())),
        "tax_foreclosure_leads": tax_fcl_count,
        "tax_sale_leads": tax_sale_count,
        "county": "Duval County",
        "state": "FL",
        "build_label": "PARTIAL_BUILD",
        "build_label_reason": (
            "v5.4.0 staged pipeline. Primary event sources: or.duvalclerk.com "
            "(Acclaim clerk recorder) + jaxdailyrecord.com (Ch. 45 sale "
            "notices) + duval.realforeclose.com (Ch. 45 foreclosure auction "
            "calendar) + duval.realtaxdeed.com (Ch. 197 tax-deed auction "
            "calendar) + Duval Property Appraiser tax roll (estate-titled-"
            "owner origination) + Duval Tax Collector delinquency export "
            "(county-taxes.net real-estate report — tax_default / "
            "tax_foreclosure / tax_sale origination per the five-criteria "
            "qualification gate). Enrichment: PA tax roll (canonical) + "
            "JaxGIS Parcels (fallback). Delinquency export is a single-year "
            "snapshot (Tax Yr 2025); years-delinquent floor is implied by "
            "Parcel Deed Status (Applied/Sold ≥ 2 yr, Escheated ≥ 4 yr)."
        ),
        "lead_total": len(records),
        "actionable_leads": approved_count,
        "review_required": review_count,
        "jaxgis_enrichment_resolved": enriched_count,
        "jaxgis_enrichment_unresolved": unenriched_count,
        # Aliases the El Paso renderer top-level fields read (if any). Kept
        # for forward-compat; renderer doesn't read these but operator may.
        "epcad_enrichment_resolved": enriched_count,
        "epcad_enrichment_unresolved": unenriched_count,
        "sources_active": [
            "clerk_official_records (Duval Clerk Official Records — Acclaim)",
            "jaxdailyrecord_foreclosures (Jacksonville Daily Record — Ch. 45 sale notices)",
            "realforeclose_duval (duval.realforeclose.com — Ch. 45 foreclosure auctions)",
            "realtaxdeed_duval (duval.realtaxdeed.com — Ch. 197 tax-deed auctions)",
            "pa_tax_roll_estates (Duval PA tax roll — estate-titled owner origination)",
            "pa_tax_roll (Duval PA tax roll — canonical parcel enrichment)",
            "duval_tax_collector (county-taxes.net — tax_default origination)",
            "duval_tax_collector_foreclosure (county-taxes.net — tax-deed application in progress)",
            "duval_tax_collector_sale (county-taxes.net — tax-deed certified / escheated)",
            "gis_parcels (JaxGIS Parcels MapServer — enrichment fallback)",
        ],
        "records": records,
    }

    # Write data.json — COMPACT (no whitespace). At Duval scale (~60K leads)
    # the indented form crosses GitHub's 100 MB per-file limit; the compact
    # JSON is ~25% smaller and the file is machine-loaded, not human-read.
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False,
                   separators=(",", ":")) + "\n",
        encoding="utf-8"
    )
    # Write data.js for the renderer's `<script src=data.js>` first-path load.
    OUT_JS.write_text(
        "window.LEADS = " +
        json.dumps(payload, ensure_ascii=False,
                   separators=(",", ":")) + ";\n",
        encoding="utf-8"
    )
    print(f"\n  wrote {OUT_JSON.relative_to(REPO)} ({OUT_JSON.stat().st_size:,} bytes)")
    print(f"  wrote {OUT_JS.relative_to(REPO)} ({OUT_JS.stat().st_size:,} bytes)")
    print(f"\n  records              : {len(records)}")
    print(f"  approved (actionable): {approved_count}")
    print(f"  review_required      : {review_count}")
    print(f"  ENRICHED             : {enriched_count}")
    print(f"  UNENRICHED           : {unenriched_count}")
    print(f"  NEW (filed today)    : {new_count}")
    print(f"  filed last 30 days   : {last_30d_count}")
    print(f"  owner enriched via PA: {owner_enriched_via_pa}")
    print(f"  owner still unresolved: {owner_still_unresolved}")
    print(f"  owner_source dist    : {dict(sorted(owner_source_dist.items()))}")
    print(f"  address-resolved     : {addr_resolved} (no-street: {addr_unresolved})")
    print(f"  tax_default leads    : {tax_default_count}")
    print(f"  tax_foreclosure leads: {tax_fcl_count}")
    print(f"  tax_sale leads       : {tax_sale_count}")
    print(f"  total balance owed   : ${tax_balance_total:,.0f}")
    print(f"  years-delinquent dist: {dict(sorted(years_dist.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
