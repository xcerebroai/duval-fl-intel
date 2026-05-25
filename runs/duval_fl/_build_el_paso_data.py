"""Adapter — Duval v5.4.0 staged-pipeline output → El Paso renderer record shape.

Reads:
  runs/duval_fl/build/staged/scored_leads.json   (full scored_lead records)
  runs/duval_fl/build/staged/matched_leads.json  (signals[] per lead)
  data/raw/clerk_official_records.jsonl          (raw doc_type per evidence_id)
  data/raw/gis_parcels.jsonl                     (legal_description, situs_zip)

Writes:
  dashboard/data.json                            (El Paso renderer shape)
  dashboard/data.js                              (window.LEADS = ... for the
                                                  <script src=data.js> path)

Field name `epcad_enrichment_status` is kept verbatim so the El Paso renderer's
enrichment-badge / detail-panel branches work unchanged; the display text was
already rebranded to "JaxGIS enriched" in dashboard/app.js. No scaffold/ or
knowledge_base/ edits — county-side only.
"""
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

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
    "lis_pendens": "lis_pendens",   # keep distinct; not a sale itself
    "tax_deed": "tax_deed",         # tax-deed auction (Ch. 197 Fla. Stat.)
}

SIGNAL_LABELS = {
    "lis_pendens": "Lis Pendens", "lien": "Lien",
    "claim_of_lien": "Claim of Lien", "construction_lien": "Construction Lien",
    "federal_tax_lien": "Federal Tax Lien", "state_tax_lien": "State Tax Lien",
    "judgment_lien": "Judgment Lien", "abstract_of_judgment": "Abstract of Judgment",
    "tax_deed": "Tax Deed", "tax_foreclosure_notice": "Tax Foreclosure Notice",
    "tax_sale_certificate": "Tax Sale Certificate",
    "notice_of_sale": "Notice of Sale", "notice_of_default": "Notice of Default",
    "probate": "Probate", "affidavit_of_heirship": "Affidavit of Heirship",
    "executors_deed": "Executor's Deed",
    "administrators_deed": "Administrator's Deed",
    "personal_representative_deed": "Personal Representative's Deed",
    "code_lien": "Code Lien", "mechanics_lien": "Mechanic's Lien",
    "municipal_lien": "Municipal Lien", "hoa_lien": "HOA Lien",
    "hospital_lien": "Hospital Lien", "water_lien": "Water Lien",
    "satisfaction_of_mortgage": "Satisfaction of Mortgage",
    "mortgage": "Mortgage", "mortgage_modification": "Mortgage Modification",
    "assignment_of_mortgage": "Assignment of Mortgage",
    "ucc_financing_statement": "UCC Financing Statement",
    "deed_of_trust": "Deed of Trust", "quitclaim_deed": "Quitclaim Deed",
    "warranty_deed": "Warranty Deed",
    "special_warranty_deed": "Special Warranty Deed",
    "sheriff_deed": "Sheriff's Deed",
    "trustees_deed_upon_sale": "Trustee's Deed Upon Sale",
    "easement": "Easement", "plat": "Plat",
    "condominium_declaration": "Condominium Declaration",
    "eviction_filing": "Eviction Filing",
    "divorce_filing": "Divorce Filing", "bankruptcy_petition": "Bankruptcy Petition",
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

    records: list[dict] = []
    enriched_count = unenriched_count = review_count = approved_count = 0

    for sl in scored:
        lead_id = sl.get("lead_id")
        ml = matched_by_id.get(lead_id) or {}
        owner_name = sl.get("owner_name") or ""
        owner_type = sl.get("owner_type") or "UNKNOWN"
        parcel_id = sl.get("primary_parcel_id") or ""
        parcel_display = sl.get("parcel_display") or {}
        attributes = sl.get("attributes") or []
        gis = gis_by_pid.get(parcel_id, {}) if parcel_id else {}

        is_review = (sl.get("lead_status") == "REVIEW_REQUIRED"
                     or ml.get("parcel_resolution_status") == "REVIEW_REQUIRED"
                     or any("review" in (f or "").lower()
                            for f in sl.get("review_flags") or []))
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
            label = SIGNAL_LABELS.get(canon) or s.get("signal_type") or canon
            # Alias certain canonicals to the renderer's expected signal_type
            # name (so the "Foreclosure sale window" filter + the soonest-sale
            # sort work on canonicals that are functionally "foreclosure").
            rendered_type = DASHBOARD_SIGNAL_TYPE_ALIAS.get(canon, canon)
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
        candidate_dates: list[date] = []
        for s in signals_out:
            for k in ("recorded_date", "earliest_recorded_date"):
                d_ = _parse_iso_date(s.get(k) or "")
                if d_:
                    candidate_dates.append(d_)
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

        rec = {
            "lead_id": lead_id,
            "parcel_resolution_status": parcel_res,
            "epcad_enrichment_status": enrichment,
            "filer_entity": ml.get("filer_entity") or "",
            "parcel_id": parcel_id,
            "owner_name": owner_name,
            "owner_type": owner_type,
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
        records.append(rec)

    new_count = sum(1 for r in records if r.get("is_new"))
    last_30d_count = sum(1 for r in records if r.get("recorded_within_30_days"))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        "refresh_date": refresh_date.isoformat(),
        "new_leads": new_count,
        "last_30d_leads": last_30d_count,
        "county": "Duval County",
        "state": "FL",
        "build_label": "PARTIAL_BUILD",
        "build_label_reason": (
            "v5.4.0 staged pipeline. Primary event sources: or.duvalclerk.com "
            "(Acclaim clerk recorder) + jaxdailyrecord.com (Ch. 45 sale notices) "
            "+ duval.realforeclose.com (Ch. 45 foreclosure auction calendar) "
            "+ duval.realtaxdeed.com (Ch. 197 tax-deed auction calendar). "
            "JaxGIS Parcels is the enrichment source. Some doc types stay "
            "unmapped to canonical lead types — see framework punch-list "
            "FW-PL-001/002/003."
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
            "gis_parcels (JaxGIS Parcels MapServer — enrichment)",
        ],
        "records": records,
    }

    # Write data.json
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    # Write data.js for the renderer's `<script src=data.js>` first-path load.
    OUT_JS.write_text(
        "window.LEADS = " +
        json.dumps(payload, ensure_ascii=False) + ";\n",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
