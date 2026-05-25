"""Duval County pipeline runner — v5.4.0 staged + Phase 4 matcher (pre-pipeline).

Architecture (post-2026-05-25 diagnostic fix):

  1. Read clerk events → raw_events (parties from clerk doc only).
  2. PHASE 4 MATCHER (pre-pipeline): live ArcGIS LNAMEOWNER batch query on
     candidate debtor names from raw_event.parties. Single-name-match parcels
     are pre-resolved onto raw_event.property_refs.parcel_id. Stage boundary
     preserved — §17 still reads ONLY raw_event.parties (the clerk doc
     party list); the matcher writes parcel_id into property_refs adjacent
     to §17, not inside it.
  3. Run staged pipeline (§17 → §18 → §19 → §20 → seam) WITH a real
     enrichment_provider(parcel_id) -> dict. The seam reads the provider
     during scoring; this is where attributes (absentee, high_equity,
     long_term_owned, out_of_state_owner, ...) and enrichment-derived score
     factors are derived.
  4. NO post-hoc parcel_display mutation — the seam owns attribute derivation
     and scoring; mutating after the seam was the prior bug (flat scores,
     empty attributes).
  5. Build dashboard payload + write data/leads.json + dashboard/data.json.

Stage attribution preserved:
  event_source       = clerk_official_records
  enrichment_source  = gis_parcels
  enrichment_attach_mode = pre_pipeline_parcel_id_via_owner_name_exact
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scaffold.pipeline import run_pipeline_staged              # noqa: E402
from scaffold.pipeline import scoring_seam                     # noqa: E402
from scaffold.pipeline.normalize import normalize_doc_type     # noqa: E402
from scaffold.pipeline.doc_type_bridge import REGISTRY_LOWER_KEYS  # noqa: E402
from scaffold.scrapers._arcgis_featureserver import ArcGISFeatureServer  # noqa: E402
from scrapers.gis_parcels import (                             # noqa: E402
    SERVICE_URL as GIS_SERVICE_URL, LAYER_ID as GIS_LAYER_ID,
    FIELD_LIST as GIS_FIELD_LIST, normalize_feature as gis_normalize_feature,
)


PUNCH: list[dict] = []


def punch(category: str, detail: str, sample: str | None = None) -> None:
    PUNCH.append({"category": category, "detail": detail, "sample": sample})


COUNTY_CONFIG = json.loads((REPO / "config/counties/duval_fl.json").read_text())
COUNTY_NAME = COUNTY_CONFIG["county_name"]
STATE = COUNTY_CONFIG["state"]
CLERK_RAW = REPO / "data/raw/clerk_official_records.jsonl"
JAXDAILY_RAW = REPO / "data/raw/jaxdailyrecord_foreclosures.jsonl"
REALFORECLOSE_RAW = REPO / "data/raw/realforeclose_duval.jsonl"
REALTAXDEED_RAW = REPO / "data/raw/realtaxdeed_duval.jsonl"
PA_ENRICHMENT_RAW = REPO / "data/raw/pa_tax_roll.jsonl"
PA_ESTATES_RAW = REPO / "data/raw/pa_tax_roll_estates.jsonl"
TC_DEFAULT_RAW = REPO / "data/raw/duval_tax_collector.jsonl"
TC_FORECLOSURE_RAW = REPO / "data/raw/duval_tax_collector_foreclosure.jsonl"
TC_SALE_RAW = REPO / "data/raw/duval_tax_collector_sale.jsonl"
GIS_RAW = REPO / "data/raw/gis_parcels.jsonl"
WORKDIR = REPO / "runs/duval_fl/build/staged"
DASHBOARD_DATA = REPO / "data/leads.json"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path, "r", encoding="utf-8") if l.strip()]


# ---------------------------------------------------------------- party mapping
# §17 name_type defaults: Direct→GR, Indirect→TP. Court-filing overrides put
# Direct→PL, Indirect→DF where the doc type is plaintiff-vs-defendant.
DEFAULT_DIRECT_NAME_TYPE = "GR"
DEFAULT_INDIRECT_NAME_TYPE = "TP"
DOC_TYPE_PARTY_OVERRIDES = {
    "lis_pendens":                  ("PL", "DF"),
    "final_judgment_of_foreclosure": ("PL", "DF"),
}

SIGNAL_TYPE_LABELS = {
    "lis_pendens": "Lis Pendens", "lien": "Lien",
    "claim_of_lien": "Claim of Lien", "construction_lien": "Construction Lien",
    "federal_tax_lien": "Federal Tax Lien", "state_tax_lien": "State Tax Lien",
    "judgment": "Judgment", "abstract_of_judgment": "Abstract of Judgment",
    "tax_deed": "Tax Deed", "tax_foreclosure_notice": "Tax Foreclosure Notice",
    "tax_sale_certificate": "Tax Sale Certificate",
    "notice_of_sale": "Notice of Sale", "probate": "Probate",
    "affidavit_of_heirship": "Affidavit of Heirship",
    "executors_deed": "Executor's Deed",
    "administrators_deed": "Administrator's Deed",
    "code_lien": "Code Lien", "mechanics_lien": "Mechanic's Lien",
    "satisfaction_of_mortgage": "Satisfaction of Mortgage",
    "mortgage": "Mortgage", "deed": "Deed",
    "easement": "Easement", "plat": "Plat",
}


def map_clerk_row_to_raw_event(rec: dict) -> dict | None:
    pay = rec.get("raw_payload", {}) or {}
    instrument = (pay.get("instrument_number") or "").strip()
    record_date = (pay.get("record_date") or "").strip()
    if not instrument and not record_date:
        punch("DEGENERATE_ROW",
              "clerk row missing instrument_number AND record_date — dropped",
              rec.get("raw_record_id"))
        return None

    raw_doc_type = (pay.get("doc_type") or "").strip()
    syn = (COUNTY_CONFIG.get("sources", {})
           .get("clerk_official_records", {})
           .get("doc_type_synonyms", {}) or {})
    norm = normalize_doc_type(raw_doc_type, county_synonyms=syn) if raw_doc_type else {
        "normalized_doc_type": None, "reason": "blank"}
    upper_canon = norm.get("normalized_doc_type")
    if upper_canon is None:
        punch("UNKNOWN_DOC_TYPE",
              f"normalize.normalize_doc_type returned None for raw label "
              f"{raw_doc_type!r} (reason={norm.get('reason')})", instrument)
        lower_canon = (raw_doc_type.lower().replace(" ", "_").replace("/", "_")
                       if raw_doc_type else "unknown")
    else:
        lower_canon = upper_canon.lower()
        if lower_canon not in REGISTRY_LOWER_KEYS:
            punch("CANON_NOT_IN_REGISTRY",
                  f"{upper_canon!r} not in REGISTRY_LOWER_KEYS", instrument)

    direct = (pay.get("direct_name") or "").strip()
    indirect = (pay.get("indirect_name") or "").strip()
    direct_t, indirect_t = DOC_TYPE_PARTY_OVERRIDES.get(
        lower_canon, (DEFAULT_DIRECT_NAME_TYPE, DEFAULT_INDIRECT_NAME_TYPE))
    parties = []
    if direct:
        parties.append({"name": direct, "name_type": direct_t,
                        "raw_role": "Direct"})
    if indirect:
        parties.append({"name": indirect, "name_type": indirect_t,
                        "raw_role": "Indirect"})

    legal = (pay.get("legal_description") or "").strip()
    case_no = (pay.get("case_number") or "").strip()
    return {
        "raw_event_id": rec.get("raw_record_id") or f"clerk:{instrument}",
        "source_id": rec.get("source_id") or "clerk_official_records",
        "source_role": "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": lower_canon,
        "raw_doc_type": raw_doc_type,
        "instrument_number": instrument,
        "recorded_date": record_date,
        "event_date": None,
        "source_url": rec.get("source_url") or "",
        "parties": parties,                 # §17 reads ONLY this
        "document_body_text": None,
        "property_refs": {
            "parcel_id": None,              # filled by matcher (next pass)
            "situs_address": None,
            "legal_description": legal or None,
            "case_number": case_no or None,
        },
        "amounts": [],
        "evidence_ids": [rec.get("raw_record_id") or f"clerk:{instrument}"],
        "parser_name": "clerk_official_records",
        "parser_version": "0.1.0",
        "parser_confidence": rec.get("parser_confidence", 95),
        "captured_at": rec.get("source_fetched_at") or
                       datetime.now(timezone.utc).isoformat(
                           timespec="seconds").replace("+00:00", "Z"),
    }


def map_jaxdailyrecord_row_to_raw_event(rec: dict) -> dict | None:
    """Jacksonville Daily Record Notice of Sale - Foreclosure → §17 raw_event.

    Each notice is a primary distress event: the foreclosure SALE itself is
    being noticed publicly. Florida judicial-foreclosure sales are advertised
    in a county-of-circulation newspaper (Fla. Stat. § 45.031). This source
    carries the SALE DATE — the field the clerk Official Records index does
    not provide. Parties: plaintiff (PL = lender / association); defendants
    (DF = property owner(s)). §17 picks DF as the debtor.
    """
    pay = rec.get("raw_payload", {}) or {}
    publication_id = (pay.get("publication_id") or "").strip()
    case_no = (pay.get("case_no") or "").strip()
    sale_date = (pay.get("sale_date") or "").strip()
    if not publication_id and not case_no:
        punch("DEGENERATE_ROW",
              "jaxdailyrecord row missing publication_id AND case_no — dropped",
              rec.get("raw_record_id"))
        return None

    # Parties — plaintiff (PL), defendants split on ';' (DF each).
    parties = []
    plaintiff = (pay.get("plaintiff") or "").strip()
    if plaintiff:
        parties.append({"name": plaintiff, "name_type": "PL",
                        "raw_role": "Plaintiff"})
    defs = (pay.get("defendants") or "").strip()
    if defs:
        for d in re.split(r"\s*;\s*|\s*,\s*(?=[A-Z])", defs):
            d = d.strip(" ,")
            if d and len(d) > 1:
                parties.append({"name": d, "name_type": "DF",
                                "raw_role": "Defendant"})

    return {
        "raw_event_id": rec.get("raw_record_id")
                       or f"jaxdailyrecord_foreclosures:{publication_id}",
        "source_id": "jaxdailyrecord_foreclosures",
        "source_role": "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": "notice_of_sale",
        "raw_doc_type": "NOTICE OF SALE",
        "instrument_number": case_no or publication_id,
        "recorded_date": sale_date or "",     # publication is the event;
                                              # using sale_date for now since
                                              # publication date is implicit.
        "event_date": sale_date or None,
        "source_url": rec.get("source_url") or "",
        "parties": parties,
        "document_body_text": pay.get("notice_text"),
        "property_refs": {
            "parcel_id": None,
            "situs_address": pay.get("property_address") or None,
            "legal_description": pay.get("legal_description") or None,
            "case_number": case_no or None,
        },
        "amounts": [],
        "evidence_ids": [rec.get("raw_record_id")
                        or f"jaxdailyrecord_foreclosures:{publication_id}"],
        "parser_name": "jaxdailyrecord_foreclosures",
        "parser_version": "0.1.0",
        "parser_confidence": rec.get("parser_confidence", 95),
        "captured_at": rec.get("source_fetched_at") or
                       datetime.now(timezone.utc).isoformat(
                           timespec="seconds").replace("+00:00", "Z"),
    }


# RealAuction (Ch. 45 foreclosure + Ch. 197 tax deed) — PRIMARY EVENT SOURCES.
# RealForeclose summary records carry case_number, parcel_id, situs_address,
# auction_status, auction_date — but NO plaintiff/defendant party names. RealTaxDeed
# carries case_number, certificate_number, parcel_id, situs_address — no parties.
# §17 stage boundary: parties are read ONLY from event-doc data. The auction
# calendar summary does not name the property owner — parties[] is empty. §17 will
# route to REVIEW_REQUIRED "owner_not_on_document" (the documented behavior for
# both notice_of_sale via the foreclosure_notice broad rule, and tax_deed via the
# Session-7 tax deed rule). The lead is NEVER dropped. Property attachment is
# proven via parcel_id (lifted from the event itself — NOT enrichment).
REALAUCTION_SOURCE_DOC_TYPE = {
    "realforeclose_duval": ("notice_of_sale", "FORECLOSURE SALE"),
    "realtaxdeed_duval":   ("tax_deed",      "TAX DEED SALE"),
}


def _clean_situs_address(raw: str) -> str | None:
    """RealAuction property_address comes as 'Property Address:\\t<addr>'.
    Strip the label and tabs; return None on blank."""
    if not raw:
        return None
    s = re.sub(r"^Property Address:\s*", "", raw.strip(), flags=re.I)
    s = s.replace("\t", " ").strip()
    return s or None


def map_realauction_row_to_raw_event(rec: dict) -> dict | None:
    """RealAuction (realforeclose_duval / realtaxdeed_duval) → §17 raw_event.

    Each auction record is a primary distress event (the sale is publicly
    noticed via the Clerk's designated auction venue). The event-doc itself
    does not name the property owner — parties[] is empty and §17 will route
    to REVIEW_REQUIRED "owner_not_on_document". The parcel_id IS present on
    the event-doc (it is the auction lot identifier, not enrichment).

    Stage boundary preserved:
      event_source       = realforeclose_duval | realtaxdeed_duval
      §17 parties        = [] (the event-doc names no owner)
      property_refs.parcel_id  = from raw_payload.parcel_id (event-doc field)
      enrichment_source  = gis_parcels (downstream §13.14)
    """
    pay = rec.get("raw_payload", {}) or {}
    source_id = rec.get("source_id") or pay.get("source_id") or ""
    canonical, raw_label = REALAUCTION_SOURCE_DOC_TYPE.get(
        source_id, (None, ""))
    if canonical is None:
        punch("REALAUCTION_UNKNOWN_SOURCE",
              f"unrecognized RealAuction source_id {source_id!r}",
              rec.get("raw_record_id"))
        return None

    case_no = (pay.get("case_number") or "").strip()
    cert_no = (pay.get("certificate_number") or "").strip()
    if not case_no and not cert_no:
        punch("DEGENERATE_ROW",
              "realauction row missing case_number AND certificate_number — dropped",
              rec.get("raw_record_id"))
        return None

    parcel_raw = (pay.get("parcel_id") or "").strip()
    # RealAuction parcel_id format "127483-0000" ↔ JaxGIS RE_NOSPACE "1274830000".
    parcel_canonical = re.sub(r"[^0-9]", "", parcel_raw) if parcel_raw else None

    sale_date = (pay.get("sale_date") or pay.get("auction_date") or "").strip()

    return {
        "raw_event_id": rec.get("raw_record_id") or f"{source_id}:{case_no or cert_no}",
        "source_id": source_id,
        "source_role": "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": canonical,
        "raw_doc_type": raw_label,
        "instrument_number": case_no or cert_no,
        "recorded_date": sale_date or "",
        "event_date": sale_date or None,
        "source_url": rec.get("source_url") or "",
        "parties": [],                          # event-doc names no owner
        "document_body_text": pay.get("raw_text"),
        "property_refs": {
            "parcel_id": parcel_canonical or None,
            "situs_address": _clean_situs_address(pay.get("property_address")),
            "legal_description": None,
            "case_number": case_no or None,
        },
        "amounts": [],
        "evidence_ids": [rec.get("raw_record_id") or f"{source_id}:{case_no or cert_no}"],
        "parser_name": source_id,
        "parser_version": "0.1.0",
        "parser_confidence": rec.get("parser_confidence", 95),
        "captured_at": rec.get("source_fetched_at") or
                       datetime.now(timezone.utc).isoformat(
                           timespec="seconds").replace("+00:00", "Z"),
    }


TC_CLASS_TO_CANONICAL = {
    # The Florida Ch. 197 tax-deed progression:
    #   Unpaid → certificate auctioned next cycle → if 2yr still unpaid, deed
    #   APPLIED → CERTIFIED → SOLD or ESCHEATED. The canonical doc types are:
    "tax_default":     ("tax_sale_certificate",   "TAX DEFAULT"),
    "tax_foreclosure": ("tax_foreclosure_notice", "TAX FORECLOSURE NOTICE"),
    "tax_sale":        ("tax_deed",               "TAX DEED SALE"),
}


def map_tax_collector_row_to_raw_event(rec: dict) -> dict | None:
    """Duval Tax Collector delinquent row → §17 raw_event.

    The Tax Collector row IS the event-doc: it carries the four hard proofs
    (parcel + delinquent year + amount + owner) and is the official record.
    §17 reads the named owner as TP — the universal STRUCTURED rule for
    tax_sale_certificate / tax_foreclosure_notice / tax_deed all expect TP
    and have no filer-name-type that would suppress the owner. The §17 stage
    boundary holds: parties come from the event-doc itself, NOT from
    enrichment.

    Stage attribution preserved:
      event_source      = duval_tax_collector*       (per classification)
      §17 parties       = [{name: owner, name_type: TP, role: Direct}]
      property_refs.parcel_id = from raw_payload.parcel_id (event-doc field)
      enrichment_source = pa_tax_roll + gis_parcels  (downstream)
    """
    pay = rec.get("raw_payload", {}) or {}
    owner = (pay.get("owner_name") or "").strip()
    parcel_id = (pay.get("parcel_id") or "").strip()
    lead_class = (pay.get("lead_classification") or "").strip()
    balance = pay.get("balance_amount") or 0
    if not owner or not parcel_id or not lead_class:
        punch("DEGENERATE_ROW",
              "TC row missing owner/parcel/classification — dropped",
              rec.get("raw_record_id"))
        return None
    if lead_class not in TC_CLASS_TO_CANONICAL:
        punch("TC_UNKNOWN_CLASS",
              f"unknown lead_classification {lead_class!r}",
              rec.get("raw_record_id"))
        return None
    canonical, raw_label = TC_CLASS_TO_CANONICAL[lead_class]

    parties = [{
        "name":      owner,
        "name_type": "TP",
        "raw_role":  "Direct",
    }]
    event_date = (pay.get("event_date") or "").strip()
    return {
        "raw_event_id":      rec.get("raw_record_id"),
        "source_id":         rec.get("source_id"),
        "source_role":       "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": canonical,
        "raw_doc_type":      raw_label,
        "instrument_number": pay.get("deed_application_no") or "",
        "recorded_date":     event_date or "",
        "event_date":        event_date or None,
        "source_url":        rec.get("source_url") or "",
        "parties":           parties,
        "document_body_text": None,
        "property_refs": {
            "parcel_id":         parcel_id,
            "situs_address":     pay.get("property_address"),
            "legal_description": pay.get("legal_description"),
            "case_number":       None,
        },
        "amounts": [
            {"kind": "balance_amount", "amount": balance,
             "currency": "USD"},
        ],
        "evidence_ids":      [rec.get("raw_record_id")],
        "parser_name":       rec.get("source_id"),
        "parser_version":    "0.1.0",
        "parser_confidence": rec.get("parser_confidence", 95),
        "captured_at":       rec.get("source_fetched_at") or
                             datetime.now(timezone.utc).isoformat(
                                 timespec="seconds").replace("+00:00", "Z"),
    }


def map_pa_estate_row_to_raw_event(rec: dict) -> dict | None:
    """Duval Property Appraiser tax-roll estate-titled-owner row → §17 raw_event.

    Framework rule: an estate-titled owner name in the parcel master IS itself
    a primary distress event — a motivated-heir / probate signal even absent
    a court filing. The doc-type maps to "estate_titled_owner" (see Smith
    county rule). §17 will route through the broad ESTATE / probate-style
    rule using the owner name as TP.

    Stage boundary preserved:
      event_source       = pa_tax_roll_estates
      §17 parties        = [{name: estate_owner, name_type: TP, role: Direct}]
                           — derived from the event-doc itself (the PA tax
                           roll IS the event-doc here)
      property_refs.parcel_id = from raw_payload.parcel_id
      enrichment_source  = pa_tax_roll + gis_parcels (downstream §13.14)
    """
    pay = rec.get("raw_payload", {}) or {}
    owner = (pay.get("owner_name") or "").strip()
    parcel_id = (pay.get("parcel_id") or "").strip()
    if not owner or not parcel_id:
        punch("DEGENERATE_ROW",
              "pa estate row missing owner_name AND parcel_id — dropped",
              rec.get("raw_record_id"))
        return None
    # §17 canonical_doc_type "administrators_deed" — STRUCTURED rule with
    # expected_debtor_name_type = "GR" and no filer; the estate is the lead
    # subject. The PA tax-roll's estate-named owner row is functionally the
    # same lead signal an administrators_deed conveys (the estate holds the
    # property; the heir is the motivated party). owner_type classifies as
    # ESTATE via the universal name-pattern rule once §17 resolves the GR.
    parties = [{
        "name":      owner,
        "name_type": "GR",
        "raw_role":  "Direct",
    }]
    event_date = (pay.get("event_date") or pay.get("recorded_date") or "").strip()
    return {
        "raw_event_id":      rec.get("raw_record_id"),
        "source_id":         "pa_tax_roll_estates",
        "source_role":       "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": "administrators_deed",
        "raw_doc_type":      "ESTATE TITLED OWNER",
        "instrument_number": "",
        "recorded_date":     event_date,
        "event_date":        event_date or None,
        "source_url":        rec.get("source_url") or "",
        "parties":           parties,
        "document_body_text": None,
        "property_refs": {
            "parcel_id":         parcel_id,
            "situs_address":     pay.get("situs_address"),
            "legal_description": pay.get("legal_description"),
            "case_number":       None,
        },
        "amounts":           [],
        "evidence_ids":      [rec.get("raw_record_id")],
        "parser_name":       "pa_tax_roll_estates",
        "parser_version":    "0.1.0",
        "parser_confidence": rec.get("parser_confidence", 92),
        "captured_at":       rec.get("source_fetched_at") or
                             datetime.now(timezone.utc).isoformat(
                                 timespec="seconds").replace("+00:00", "Z"),
    }


def map_evidence(rec: dict) -> dict:
    return {
        "evidence_id": rec.get("raw_record_id"),
        "record_id": rec.get("raw_record_id"),
        "field": "doc_type",
        "value": (rec.get("raw_payload") or {}).get("doc_type", ""),
        "status": "Confirmed",
        "source_id": rec.get("source_id"),
        "source_reliability_grade": "A",
        "source_url": rec.get("source_url") or "",
        "captured_at": rec.get("source_fetched_at") or "",
    }


# ---------------------------------------------------------------- matcher
def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def name_match_against_gis_parcels(owner_names: set[str]) -> tuple[dict, dict]:
    """Batched ArcGIS LNAMEOWNER lookup. Returns:
      - name_to_parcels: {owner_name (upper) -> list[matched gis_parcels records]}
      - parcel_id_to_raw: {parcel_id -> wrapped §4.32 raw_record}
    """
    if not owner_names:
        return {}, {}
    server = ArcGISFeatureServer(GIS_SERVICE_URL,
                                 user_agent="xcerebro-duval-matcher/0.2")
    name_to_parcels: dict[str, list] = {n: [] for n in owner_names}
    parcel_id_to_raw: dict[str, dict] = {}
    names_sorted = sorted(owner_names)
    BATCH = 50
    for i in range(0, len(names_sorted), BATCH):
        chunk = names_sorted[i:i + BATCH]
        quoted = ",".join("'" + _sql_escape(n) + "'" for n in chunk)
        where = f"LNAMEOWNER IN ({quoted})"
        try:
            for feat in server.iter_features(
                    GIS_LAYER_ID, where=where, out_fields=GIS_FIELD_LIST,
                    return_geometry=False):
                rec = gis_normalize_feature(feat)
                pid = rec["raw_payload"].get("parcel_id")
                owner = (rec["raw_payload"].get("owner_name") or "").upper()
                if pid:
                    parcel_id_to_raw[pid] = rec
                if owner in name_to_parcels:
                    name_to_parcels[owner].append(rec)
        except Exception as e:  # noqa: BLE001
            punch("MATCHER_ARCGIS_BATCH_FAILED",
                  f"ArcGIS LNAMEOWNER IN(...) batch raised {type(e).__name__}: {e}",
                  f"batch_size={len(chunk)}")
    return name_to_parcels, parcel_id_to_raw


def parcel_id_lookup_against_gis_parcels(parcel_ids: set[str]) -> dict:
    """Batched ArcGIS RE_NOSPACE lookup for RealAuction events.

    RealAuction events already carry parcel_id on the event-doc (the auction
    lot identifier). This is the parcel-side of the matcher: pull the parcel
    record so the enrichment_provider has owner/situs/assessed attached. The
    stage boundary remains intact — the parcel attachment to the event was
    established by the event-doc itself, not by enrichment-side name matching.
    """
    if not parcel_ids:
        return {}
    server = ArcGISFeatureServer(GIS_SERVICE_URL,
                                 user_agent="xcerebro-duval-matcher/0.2")
    parcel_id_to_raw: dict[str, dict] = {}
    pids = sorted(parcel_ids)
    BATCH = 50
    for i in range(0, len(pids), BATCH):
        chunk = pids[i:i + BATCH]
        quoted = ",".join("'" + _sql_escape(p) + "'" for p in chunk)
        where = f"RE_NOSPACE IN ({quoted})"
        try:
            for feat in server.iter_features(
                    GIS_LAYER_ID, where=where, out_fields=GIS_FIELD_LIST,
                    return_geometry=False):
                rec = gis_normalize_feature(feat)
                pid = rec["raw_payload"].get("parcel_id")
                if pid:
                    parcel_id_to_raw[pid] = rec
        except Exception as e:  # noqa: BLE001
            punch("MATCHER_ARCGIS_PARCEL_BATCH_FAILED",
                  f"ArcGIS RE_NOSPACE IN(...) batch raised "
                  f"{type(e).__name__}: {e}", f"batch_size={len(chunk)}")
    return parcel_id_to_raw


def resolve_parcel_ids(raw_events: list[dict],
                       name_to_parcels: dict) -> tuple[int, int, int]:
    """Pre-resolve raw_event.property_refs.parcel_id by name-matching the
    debtor side (Indirect first per §17 default; Direct fallback).

    Stage boundary: this writes only to property_refs.parcel_id. §17 reads
    raw_event.parties (the clerk doc party list) — unchanged here.

    Returns (resolved, multi_match_only, no_match).
    """
    resolved = multi_only = no_match = 0
    for ev in raw_events:
        # Order parties: Indirect first (default debtor side), Direct fallback.
        parties = sorted(ev.get("parties", []) or [],
                         key=lambda p: 0 if p.get("raw_role") == "Indirect" else 1)
        chosen_pid = None
        saw_multi = False
        for p in parties:
            n = (p.get("name") or "").strip().upper()
            if not n:
                continue
            cands = name_to_parcels.get(n, [])
            if len(cands) == 1:
                chosen_pid = cands[0]["raw_payload"]["parcel_id"]
                break
            if len(cands) > 1:
                saw_multi = True
        if chosen_pid:
            ev["property_refs"]["parcel_id"] = chosen_pid
            resolved += 1
        elif saw_multi:
            multi_only += 1
        else:
            no_match += 1
    return resolved, multi_only, no_match


def _read_pa_enrichment(path: Path) -> dict[str, dict]:
    """Read the PA tax-roll enrichment file into {parcel_id: raw_payload}."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for rec in _read_jsonl(path):
        p = rec.get("raw_payload") or {}
        pid = (p.get("parcel_id") or "").strip()
        if pid:
            out[pid] = p
    return out


def build_enrichment_provider(parcel_id_to_raw: dict,
                              pa_by_pid: dict[str, dict] | None = None):
    """Build the parcel_id -> seam-shaped parcel dict map and the provider.

    The PA tax-roll fields SUPERSEDE the JaxGIS Parcels MapServer values for
    fields the COJ layer does not expose:
      year_built (COJ Parcels layer has none — PA has it)
      last_sale_date / last_sale_price (COJ has neither — PA carries both)
      exemptions / homestead (COJ doesn't expose — PA does)
    For the overlapping fields (owner_name, owner_mailing, situs_address,
    assessed_value) the PA tax roll is canonical (the source of record);
    we fall back to gis_parcels when the PA file lacks the parcel.

    The seam's _parcel_display_from reads `owner_mailing_address` (not the
    gis_parcels canonical `owner_mailing_addr1`). This shim renames the field
    for seam consumption.
    """
    pa_by_pid = pa_by_pid or {}
    by_pid: dict = {}
    all_pids = set(parcel_id_to_raw.keys()) | set(pa_by_pid.keys())
    for pid in all_pids:
        g = (parcel_id_to_raw.get(pid) or {}).get("raw_payload") or {}
        pa = pa_by_pid.get(pid) or {}
        # PA wins on conflict; gis_parcels fills gaps.
        def pick(*vals):
            for v in vals:
                if v not in (None, "", []):
                    return v
            return None
        by_pid[pid] = {
            "parcel_id": pid,
            "situs_address":         pick(pa.get("situs_address"),
                                          g.get("situs_address")),
            "situs_city":            pick(pa.get("situs_city"),
                                          g.get("situs_city")),
            "situs_state":           pick(pa.get("situs_state"),
                                          g.get("situs_state")),
            "situs_zip":             pick(pa.get("situs_zip"),
                                          g.get("situs_zip")),
            "owner_name":            pick(pa.get("owner_name"),
                                          g.get("owner_name")),
            "owner_mailing_address": pick(pa.get("owner_mailing_addr1"),
                                          g.get("owner_mailing_addr1")),
            "owner_mailing_city":    pick(pa.get("owner_mailing_city"),
                                          g.get("owner_mailing_city")),
            "owner_mailing_state":   pick(pa.get("owner_mailing_state"),
                                          g.get("owner_mailing_state")),
            "owner_mailing_zip":     pick(pa.get("owner_mailing_zip"),
                                          g.get("owner_mailing_zip")),
            "assessed_value":        pick(pa.get("assessed_value"),
                                          g.get("assessed_value")),
            "just_value":            pick(pa.get("just_value_total"),
                                          pa.get("just_value")),
            "taxable_value":         pa.get("taxable_value"),
            "land_value":            g.get("land_value"),
            "improvement_value":     g.get("improvement_value"),
            "last_sale_date":        pick(pa.get("last_sale_date"),
                                          g.get("last_sale_date")),
            "last_sale_price":       pick(pa.get("last_sale_price"),
                                          g.get("last_sale_price")),
            "year_built":            pick(pa.get("year_built"),
                                          g.get("year_built")),
            "legal_description":     pick(pa.get("legal_description"),
                                          g.get("legal_description")),
            "acreage":               pick(pa.get("acreage"),
                                          g.get("acreage")),
            "property_class":        pick(pa.get("property_class"),
                                          g.get("property_class")),
            "exemptions":            pa.get("exemptions") or [],
            "homestead":             "HOMESTEAD" if pa.get("homestead") else None,
            "additional_owner_names": pa.get("additional_owner_names") or [],
            "owner_count":           pa.get("owner_count"),
        }

    def provider(parcel_id):
        if not parcel_id:
            return None
        return by_pid.get(parcel_id)

    return provider


def write_gis_parcels_jsonl(parcel_id_to_raw: dict) -> None:
    GIS_RAW.parent.mkdir(parents=True, exist_ok=True)
    tmp = GIS_RAW.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for pid, rec in sorted(parcel_id_to_raw.items()):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(GIS_RAW)


# ---------------------------------------------------------------- main
def main() -> int:
    print("# Duval County pipeline runner — v5.4.0 staged + pre-pipeline matcher")
    clerk = _read_jsonl(CLERK_RAW)
    print(f"  clerk raw rows : {len(clerk)}  ({CLERK_RAW.relative_to(REPO)})")
    dates = sorted({(r.get("raw_payload") or {}).get("record_date", "")
                    for r in clerk
                    if (r.get("raw_payload") or {}).get("record_date")})
    if dates:
        print(f"  date range     : {dates[0]} … {dates[-1]}  "
              f"({len(dates)} distinct dates)")

    raw_events = []
    skipped = 0
    for rec in clerk:
        ev = map_clerk_row_to_raw_event(rec)
        if ev is None:
            skipped += 1
        else:
            raw_events.append(ev)
    print(f"  raw_events from clerk : {len(raw_events)}  (skipped={skipped})")

    # Merge Jacksonville Daily Record foreclosure notices (primary event source)
    jaxd = _read_jsonl(JAXDAILY_RAW)
    jaxd_added = 0
    for rec in jaxd:
        ev = map_jaxdailyrecord_row_to_raw_event(rec)
        if ev is not None:
            raw_events.append(ev)
            jaxd_added += 1
    print(f"  jaxdailyrecord notices : {len(jaxd)} pulled, {jaxd_added} merged "
          f"(source: {JAXDAILY_RAW.relative_to(REPO)})")

    # Merge RealAuction sales (foreclosure + tax deed) — PRIMARY event sources.
    realforeclose = _read_jsonl(REALFORECLOSE_RAW)
    realtaxdeed = _read_jsonl(REALTAXDEED_RAW)
    realauction_added = 0
    for rec in realforeclose + realtaxdeed:
        ev = map_realauction_row_to_raw_event(rec)
        if ev is not None:
            raw_events.append(ev)
            realauction_added += 1
    print(f"  realforeclose sales    : {len(realforeclose)} pulled "
          f"(source: {REALFORECLOSE_RAW.relative_to(REPO)})")
    print(f"  realtaxdeed sales      : {len(realtaxdeed)} pulled "
          f"(source: {REALTAXDEED_RAW.relative_to(REPO)})")
    print(f"  realauction merged     : {realauction_added}")

    # Merge PA tax-roll estate-titled-owner rows — PRIMARY event source.
    # Framework rule: an estate-named owner in the parcel master IS a lead.
    pa_estates = _read_jsonl(PA_ESTATES_RAW)
    pa_estates_added = 0
    for rec in pa_estates:
        ev = map_pa_estate_row_to_raw_event(rec)
        if ev is not None:
            raw_events.append(ev)
            pa_estates_added += 1
    print(f"  pa_tax_roll estates    : {len(pa_estates)} pulled, "
          f"{pa_estates_added} merged (source: "
          f"{PA_ESTATES_RAW.relative_to(REPO)})")

    # Merge Duval Tax Collector delinquency rows — PRIMARY event source.
    # Smith framework rule: an official Tax Collector record proving
    # delinquency ORIGINATES a tax_default lead. The five-criteria gate
    # was enforced by the adapter (parcel + year + balance + owner +
    # source proof) — only Unpaid rows with balance > 0 were written.
    tc_default = _read_jsonl(TC_DEFAULT_RAW)
    tc_fcl = _read_jsonl(TC_FORECLOSURE_RAW)
    tc_sale = _read_jsonl(TC_SALE_RAW)
    tc_added = 0
    for rec in tc_default + tc_fcl + tc_sale:
        ev = map_tax_collector_row_to_raw_event(rec)
        if ev is not None:
            raw_events.append(ev)
            tc_added += 1
    print(f"  tax_collector default  : {len(tc_default)} rows "
          f"({TC_DEFAULT_RAW.relative_to(REPO)})")
    print(f"  tax_collector fcl      : {len(tc_fcl)} rows "
          f"({TC_FORECLOSURE_RAW.relative_to(REPO)})")
    print(f"  tax_collector sale     : {len(tc_sale)} rows "
          f"({TC_SALE_RAW.relative_to(REPO)})")
    print(f"  tax_collector merged   : {tc_added}")
    print(f"  raw_events TOTAL       : {len(raw_events)}")

    evidence_entries = [map_evidence(rec) for rec in clerk
                        if rec.get("raw_record_id")]
    for rec in jaxd:
        if rec.get("raw_record_id"):
            evidence_entries.append(map_evidence(rec))
    for rec in realforeclose + realtaxdeed:
        if rec.get("raw_record_id"):
            evidence_entries.append(map_evidence(rec))
    for rec in pa_estates:
        if rec.get("raw_record_id"):
            evidence_entries.append(map_evidence(rec))
    for rec in tc_default + tc_fcl + tc_sale:
        if rec.get("raw_record_id"):
            evidence_entries.append(map_evidence(rec))

    # --- PHASE 4 MATCHER (pre-pipeline) ---
    candidate_names = set()
    for ev in raw_events:
        for p in ev.get("parties", []) or []:
            n = (p.get("name") or "").strip().upper()
            if n:
                candidate_names.add(n)
    print(f"\n  Phase 4 matcher input    : {len(candidate_names)} distinct "
          "candidate party names (Direct + Indirect across all events)")
    name_to_parcels, parcel_id_to_raw = name_match_against_gis_parcels(
        candidate_names)
    print(f"  Phase 4 matcher result   : "
          f"{sum(1 for v in name_to_parcels.values() if v)} candidate names "
          f"matched in gis_parcels, "
          f"{len(parcel_id_to_raw)} distinct parcels pulled")

    resolved, multi_only, no_match = resolve_parcel_ids(raw_events, name_to_parcels)
    print(f"  raw_events with parcel_id resolved (name-match): {resolved}  "
          f"(multi-match-only={multi_only}, no-match={no_match})")

    # --- PHASE 4b PARCEL-ID LOOKUP — RealAuction events carry parcel_id on
    # the event-doc. Pull the parcel record so enrichment_provider has the
    # owner/situs/assessed attached. (Stage boundary preserved — the parcel
    # was attached to the event by the event-doc itself.)
    event_parcel_ids = set()
    for ev in raw_events:
        pid = (ev.get("property_refs") or {}).get("parcel_id")
        if pid and pid not in parcel_id_to_raw:
            event_parcel_ids.add(pid)
    print(f"\n  Phase 4b parcel-id input : {len(event_parcel_ids)} parcel ids "
          "from event-doc property_refs (not already pulled by name-match)")
    extra_parcels = parcel_id_lookup_against_gis_parcels(event_parcel_ids)
    parcel_id_to_raw.update(extra_parcels)
    print(f"  Phase 4b parcel-id result: {len(extra_parcels)} new parcels pulled, "
          f"{len(parcel_id_to_raw)} parcels total")

    if parcel_id_to_raw:
        write_gis_parcels_jsonl(parcel_id_to_raw)
        print(f"  gis_parcels.jsonl written: {len(parcel_id_to_raw)} records "
              f"({GIS_RAW.relative_to(REPO)})")

    # PA tax-roll enrichment — supersedes JaxGIS for year_built / sales /
    # exemptions; PA + JaxGIS merged in build_enrichment_provider.
    pa_by_pid = _read_pa_enrichment(PA_ENRICHMENT_RAW)
    print(f"\n  PA tax-roll enrichment   : {len(pa_by_pid)} parcels indexed "
          f"({PA_ENRICHMENT_RAW.relative_to(REPO) if PA_ENRICHMENT_RAW.exists() else '<missing>'})")
    enrichment_provider = build_enrichment_provider(parcel_id_to_raw, pa_by_pid)

    # --- staged pipeline WITH enrichment_provider ---
    WORKDIR.mkdir(parents=True, exist_ok=True)
    try:
        result = run_pipeline_staged.run_staged_pipeline(
            raw_events,
            evidence_entries=evidence_entries,
            signal_type_labels=SIGNAL_TYPE_LABELS,
            workdir=WORKDIR,
            as_of=date(2026, 5, 25),
            enrichment_provider=enrichment_provider,
            approve_needs_review=True,
        )
    except scoring_seam.SemanticGateBlocked as e:
        print(f"\n!! §20 DEPLOY_BLOCKED")
        print(f"   {e}")
        _emit_punch_list()
        return 4

    verdict = result["semantic_verdict"]
    scored = result["scored_leads"]
    print(f"\n  §20 semantic_verdict     : {verdict}")
    print(f"  matched_leads count      : {len(result['matched_leads'])}")
    print(f"  scored_leads count       : {len(scored)}")
    enriched_count = sum(1 for s in scored if s.get("enrichment_status") == "ENRICHED")
    with_attrs = sum(1 for s in scored if s.get("attributes"))
    print(f"  ENRICHED scored_leads    : {enriched_count}")
    print(f"  scored_leads with attrs  : {with_attrs}")

    review_count = sum(
        1 for s in scored
        if (s.get("lead_status") and "REVIEW" in s["lead_status"])
        or s.get("review_required")
        or any("review" in (f or "").lower() for f in s.get("review_flags", []))
    )
    print(f"  REVIEW_REQUIRED total    : {review_count}")

    # --- Dashboard payload ---
    payload = run_pipeline_staged.build_dashboard_payload(
        scored,
        semantic_verdict=verdict,
        county=COUNTY_NAME,
        state=STATE,
        mode="production",
        build_label="PARTIAL_BUILD",
    )
    payload["event_source"] = (
        "clerk_official_records + jaxdailyrecord_foreclosures + "
        "realforeclose_duval + realtaxdeed_duval + pa_tax_roll_estates + "
        "duval_tax_collector + duval_tax_collector_foreclosure + "
        "duval_tax_collector_sale"
    )
    payload["enrichment_source"] = "pa_tax_roll + gis_parcels"
    payload["enrichment_attach_mode"] = (
        "pre_pipeline_parcel_id_via_owner_name_exact "
        "+ event_doc_parcel_id_from_realauction "
        "+ event_doc_parcel_id_from_pa_estates "
        "+ pa_tax_roll_supersede_gis"
    )

    # Compact JSON — see _build_el_paso_data.py for the why (GitHub 100 MB cap).
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DATA.write_text(
        json.dumps(payload, ensure_ascii=False,
                   separators=(",", ":")) + "\n",
        encoding="utf-8")
    (REPO / "dashboard/data.json").write_text(
        json.dumps(payload, ensure_ascii=False,
                   separators=(",", ":")) + "\n",
        encoding="utf-8")

    print(f"\n  dashboard payload     : data/leads.json + dashboard/data.json")
    print(f"  lead_total            : {payload['lead_total']}")
    print(f"  enrichment_breakdown  : {payload['enrichment_breakdown']}")
    print(f"  pattern_counts        : {payload['pattern_counts']}")
    print(f"  attribute_counts      : {payload['attribute_counts']}")
    print(f"  score_tier_distribution : {payload['score_tier_distribution']}")
    print(f"  deal_path_distribution  : {payload['deal_path_distribution']}")
    print(f"  stack_depth_distribution: {payload['stack_depth_distribution']}")

    _emit_punch_list()
    return 0


def _emit_punch_list() -> None:
    counts: dict[str, int] = {}
    for p in PUNCH:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    print("\n# PUNCH LIST (summary by category):")
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>5}  {cat}")
    punch_path = REPO / "runs/duval_fl/build/staged/punch_list.json"
    punch_path.parent.mkdir(parents=True, exist_ok=True)
    punch_path.write_text(
        json.dumps({"category_counts": counts, "entries": PUNCH},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"  (full punch list: {punch_path.relative_to(REPO)})")


if __name__ == "__main__":
    raise SystemExit(main())
