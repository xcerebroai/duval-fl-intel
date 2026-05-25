"""Duval County Tax Collector delinquency adapter — tax_default origination.

Source : Duval County Tax Collector delinquent real-estate export
Portal : https://county-taxes.net/fl-duval/fl-duval/reports/real-estate
         (Grant Street Group platform; CSV report download from the
         Tax Collector's report page.)
Roles  :
  duval_tax_collector             PRIMARY EVENT — tax_default lead (baseline
                                  unpaid year, parcel + balance + owner)
  duval_tax_collector_foreclosure PRIMARY EVENT — tax_foreclosure (active
                                  tax-deed application in progress)
  duval_tax_collector_sale        PRIMARY EVENT — tax_sale (certified / about
                                  to auction / escheated to county)

Stage rule (from the Smith county precedent, replayed here):
  An OFFICIAL Tax Collector record proving delinquency
  (account/parcel + delinquent year + amount due + source proof + owner)
  ORIGINATES a tax_default lead. The DCPAO parcel master / value /
  assessment data stays ENRICHMENT — it is never a default proof. §17
  reads recorded-event parties only; this adapter's "event-doc" is the
  Tax Collector row, and the named owner on the row is the §17 party.

Five-criteria qualification gate (Smith pattern):
  1. account/parcel id     —— Account Number  (always present)
  2. delinquent year       —— Tax Yr          (always present)
  3. amount due            —— Balance Amount  (must be > 0 for tax_default)
  4. source proof          —— this row + county-taxes.net source_url
  5. owner identification  —— Owner Name      (always present)

Classification cascade (most specific first):
  Parcel Deed Status = "Certified" | "Escheated"   → tax_sale
  Parcel Deed Status = "Applied"   | "Sold"        → tax_foreclosure
  Account Status     = "Unpaid"    AND Balance > 0 → tax_default
  Otherwise (Paid In Full / zero balance)          → SKIP — no distress signal
                                                       (Paid In Full rows would
                                                       contaminate the board)

Florida statutory context:
  Ch. 197 — tax certificate auctioned annually for prior-year unpaid taxes.
  After 2+ years, certificate holder may APPLY for a tax deed; that
  application moves the parcel into the tax-deed sale pipeline (Applied →
  Certified → Sale → Sold). "Escheated" = no bid → escheats to the county.

  Parcel Deed Status values therefore imply years-delinquent floor:
    "-- None --"        →  0–1 yr (this cycle only)
    "Paid Off"          →  prior-year deed-app paid off
    "Sold"              →  ≥ 1 yr (certificate sold)
    "Applied"           →  ≥ 2 yr (deed application filed)
    "Certified"         →  ≥ 2 yr (deed certificate issued)
    "Escheated"         →  ≥ 4 yr (escheated to county)

Input  : CSV (the county-taxes.net real-estate report export).
Output : §4.32 wrapped raw_records to one of three JSONL files keyed by
         lead classification, so the §17 / §18 pipeline can bucket by
         canonical_doc_type cleanly.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(sys.maxsize)

SOURCE_URL = ("https://county-taxes.net/fl-duval/fl-duval/reports/real-estate")

# Years-delinquent floor implied by Parcel Deed Status.
PDS_YEARS_FLOOR = {
    "-- None --": 1,
    "Paid Off":   1,
    "Sold":       1,
    "Applied":    2,
    "Certified":  2,
    "Canceled":   1,
    "Expired":    1,
    "Escheated":  4,
    "LAS":        1,
    "Canceled At Bid Rate": 1,
}

# Tax-deed pipeline mapping → lead classification.
TAX_SALE_PDS = {"Certified", "Escheated"}
TAX_FORECLOSURE_PDS = {"Applied", "Sold"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _num(s) -> Optional[float]:
    s = (s or "").strip().replace(",", "")
    if not s or s in ("-- None --",):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm_parcel(s: str) -> str:
    """Tax-collector account "000006-0100" → 10-digit RE_NOSPACE "0000060100"."""
    return re.sub(r"[^0-9]", "", (s or "").strip())


def _clean(s) -> str:
    s = (s or "").strip()
    if s.upper() in ("", "-- NONE --", "NONE", "NULL"):
        return ""
    return s


def _compose_situs(row: dict) -> dict:
    street = " ".join(filter(None, [
        _clean(row.get("Property Address Line 1")),
        _clean(row.get("Property Address Line 2")),
        _clean(row.get("Property Address Line 3")),
    ]))
    return {
        "street": street,
        "city":   _clean(row.get("Property City")),
        "zip":    _clean(row.get("Property ZIP Code")).rstrip("-"),
        "state":  "FL",
    }


def _compose_mailing(row: dict) -> str:
    lines = [
        _clean(row.get("Owner Address Line 1")),
        _clean(row.get("Owner Address Line 2")),
        _clean(row.get("Owner Address Line 3")),
    ]
    city = _clean(row.get("Owner Address City"))
    state = _clean(row.get("Owner Address State"))
    zipc = _clean(row.get("Owner Address ZIP"))
    tail = ", ".join(filter(None, [city, state])) + ((" " + zipc) if zipc else "")
    return " ".join(filter(None, lines + [tail])).strip()


def classify(row: dict) -> str:
    """Return one of:
       "tax_sale"       — Parcel Deed Status indicates pre/post deed sale
       "tax_foreclosure" — Parcel Deed Status indicates active deed application
       "tax_default"    — baseline Unpaid + balance > 0
       ""               — Paid In Full / no qualifying distress (SKIP)
    """
    status = _clean(row.get("Account Status"))
    pds = _clean(row.get("Parcel Deed Status"))
    bal = _num(row.get("Balance Amount")) or 0.0
    if status != "Unpaid" or bal <= 0:
        return ""        # Paid In Full / zero balance — not a default
    if pds in TAX_SALE_PDS:
        return "tax_sale"
    if pds in TAX_FORECLOSURE_PDS:
        return "tax_foreclosure"
    return "tax_default"


def years_delinquent_floor(row: dict) -> int:
    """Lower bound on years delinquent implied by the Parcel Deed Status."""
    pds = _clean(row.get("Parcel Deed Status")) or "-- None --"
    return PDS_YEARS_FLOOR.get(pds, 1)


def wrap(row: dict, *, lead_class: str, tax_year: str, refresh_iso: str,
         row_index: int) -> dict:
    """Wrap one CSV row into a §4.32 raw_record. PA-aligned parcel_id.

    `row_index` is appended to the raw_record_id so secondary billing lines
    for the same parcel-year (e.g. "HL - HX LIEN" — a homestead-lien
    addendum line that's tracked separately by the Tax Collector) don't
    collide on the evidence-ledger primary key. The CSV can carry multiple
    rows per (account, tax_year).
    """
    acct = _clean(row.get("Account Number"))
    parcel_id = _norm_parcel(acct)
    owner = _clean(row.get("Owner Name"))
    situs = _compose_situs(row)
    mailing = _compose_mailing(row)
    bal = _num(row.get("Balance Amount")) or 0.0
    total_tax = _num(row.get("Total Tax")) or 0.0
    years = years_delinquent_floor(row)
    pds = _clean(row.get("Parcel Deed Status"))
    source_id_by_class = {
        "tax_default":     "duval_tax_collector",
        "tax_foreclosure": "duval_tax_collector_foreclosure",
        "tax_sale":        "duval_tax_collector_sale",
    }
    doc_type_by_class = {
        "tax_default":     "TAX DEFAULT",
        "tax_foreclosure": "TAX FORECLOSURE NOTICE",
        "tax_sale":        "TAX DEED SALE",
    }
    source_id = source_id_by_class[lead_class]
    doc_type = doc_type_by_class[lead_class]

    return {
        "raw_record_id":      f"{source_id}:{acct}:{tax_year}:{row_index}",
        "source_id":          source_id,
        "source_url":         SOURCE_URL,
        "source_fetched_at":  _now_iso(),
        "parser_confidence":  95,
        "raw_payload": {
            "account_number":       acct,
            "parcel_id":            parcel_id,
            "alternate_key":        _clean(row.get("Alternate Key")),
            "tax_year":             tax_year,
            "delinquent_year":      tax_year,
            "lead_classification":  lead_class,
            "years_delinquent_floor": years,
            "owner_name":           owner,
            "owner_mailing":        mailing or None,
            "property_address":     situs["street"] or None,
            "property_city":        situs["city"] or None,
            "property_state":       situs["state"],
            "property_zip":         situs["zip"] or None,
            "legal_description":    _clean(row.get("Legal Desc")) or None,
            "balance_amount":       bal,
            "total_tax":            total_tax,
            "ad_valorem_tax":       _num(row.get("Adv. Tax")),
            "non_ad_valorem_tax":   _num(row.get("NonAdv. Tax")),
            "assessed_value":       _num(row.get("Assessed Value")),
            "account_status":       _clean(row.get("Account Status")),
            "parcel_deed_status":   pds or None,
            "deed_application_no":  _clean(row.get("Deed Application #")) or None,
            "cert_number":          _clean(row.get("Cert #")) or None,
            "bidder_number":        _clean(row.get("Bidder #")) or None,
            "litigation":           _clean(row.get("Litigation")) == "Yes",
            "bankrupt":             _clean(row.get("Bankrupt")) == "Yes",
            "millage_code":         _clean(row.get("Millage Code")) or None,
            "use_code":             _clean(row.get("Use Code")) or None,
            "exemption":            _clean(row.get("Exemption")) or None,
            "doc_type":             doc_type,
            "event_date":           None,         # status, not event
            "recorded_date":        None,
            "snapshot_date":        refresh_iso,
            "is_snapshot_event":    True,         # tax-roll snapshot (not a
                                                  # dated court filing)
            "county":               "Duval",
            "state":                "FL",
        },
    }


def run(src: Path, *,
        out_default: Path,
        out_foreclosure: Path,
        out_sale: Path,
        min_balance: float = 0.0) -> dict:
    """Stream the CSV once, emit three wrapped-JSONL files by classification.

    Five-criteria gate enforced: only rows with non-empty Account Number +
    Owner Name + Tax Yr + Balance > 0 + Account Status="Unpaid" are written.
    Rows below `min_balance` are dropped (default 0 — none dropped here; the
    dashboard default-hides low-priority but the data ledger keeps them).
    """
    out_default.parent.mkdir(parents=True, exist_ok=True)
    out_foreclosure.parent.mkdir(parents=True, exist_ok=True)
    out_sale.parent.mkdir(parents=True, exist_ok=True)
    tmps = {
        "default":     out_default.with_suffix(".jsonl.tmp"),
        "foreclosure": out_foreclosure.with_suffix(".jsonl.tmp"),
        "sale":        out_sale.with_suffix(".jsonl.tmp"),
    }
    classes_to_path = {
        "tax_default":     ("default",     out_default),
        "tax_foreclosure": ("foreclosure", out_foreclosure),
        "tax_sale":        ("sale",        out_sale),
    }
    stats = {
        "rows_read":         0,
        "rows_paid_in_full": 0,
        "tax_default":       0,
        "tax_foreclosure":   0,
        "tax_sale":          0,
        "dropped_low_bal":   0,
        "dropped_missing":   0,
        "years_floor_dist":  {},
        "balance_total_owed_$": 0.0,
        "estate_pattern_unpaid": 0,
    }
    refresh_iso = datetime.now(timezone.utc).date().isoformat()
    # local estate-pattern detector (audit-only metric; estate origination is
    # already covered by the PA tax-roll adapter).
    estate_re = re.compile(
        r"\b(?:ESTATE|EST)\s+OF\b|\bLIFE\s+(?:ESTATE|EST)\b|"
        r"\b(?:ESTATE|EST)\s*$", re.I)

    handles = {k: open(v, "w", encoding="utf-8") for k, v in tmps.items()}
    try:
        with open(src, "r", encoding="utf-8") as fh:
            rdr = csv.DictReader(fh)
            for row_index, row in enumerate(rdr):
                stats["rows_read"] += 1
                acct = _clean(row.get("Account Number"))
                owner = _clean(row.get("Owner Name"))
                tax_year = _clean(row.get("Tax Yr"))
                bal = _num(row.get("Balance Amount")) or 0.0
                if not (acct and owner and tax_year):
                    stats["dropped_missing"] += 1
                    continue
                if _clean(row.get("Account Status")) == "Paid In Full":
                    stats["rows_paid_in_full"] += 1
                    continue
                if bal < min_balance:
                    stats["dropped_low_bal"] += 1
                    continue
                lead_class = classify(row)
                if not lead_class:
                    continue
                stats[lead_class] += 1
                stats["balance_total_owed_$"] += bal
                if estate_re.search(owner):
                    stats["estate_pattern_unpaid"] += 1
                years = years_delinquent_floor(row)
                stats["years_floor_dist"][str(years)] = \
                    stats["years_floor_dist"].get(str(years), 0) + 1
                rec = wrap(row, lead_class=lead_class, tax_year=tax_year,
                           refresh_iso=refresh_iso, row_index=row_index)
                key, _ = classes_to_path[lead_class]
                handles[key].write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        for h in handles.values():
            h.close()
    tmps["default"].replace(out_default)
    tmps["foreclosure"].replace(out_foreclosure)
    tmps["sale"].replace(out_sale)

    stats["balance_total_owed_$"] = round(stats["balance_total_owed_$"], 2)
    stats["status"] = "OK"
    stats["source_file"] = str(src)
    stats["out_tax_default"] = str(out_default.relative_to(REPO_ROOT))
    stats["out_tax_foreclosure"] = str(out_foreclosure.relative_to(REPO_ROOT))
    stats["out_tax_sale"] = str(out_sale.relative_to(REPO_ROOT))
    return stats


def main() -> int:
    p = argparse.ArgumentParser(
        description="Duval County Tax Collector delinquency adapter "
                    "(county-taxes.net real-estate report CSV).")
    p.add_argument("--src", default=None,
                   help="Path to the county-taxes.net CSV export. Default: "
                        "data/raw/duval_tax_collector_src.csv")
    p.add_argument("--out-default", default=None)
    p.add_argument("--out-foreclosure", default=None)
    p.add_argument("--out-sale", default=None)
    p.add_argument("--min-balance", type=float, default=0.0,
                   help="Drop rows below this balance (default: 0 — keep all).")
    args = p.parse_args()

    src = Path(args.src) if args.src else (
        REPO_ROOT / "data/raw/duval_tax_collector_src.csv")
    if not src.exists():
        print(f"ERROR: source file not found: {src}", file=sys.stderr)
        return 2
    out_default = Path(args.out_default) if args.out_default else (
        REPO_ROOT / "data/raw/duval_tax_collector.jsonl")
    out_fcl = Path(args.out_foreclosure) if args.out_foreclosure else (
        REPO_ROOT / "data/raw/duval_tax_collector_foreclosure.jsonl")
    out_sale = Path(args.out_sale) if args.out_sale else (
        REPO_ROOT / "data/raw/duval_tax_collector_sale.jsonl")

    stats = run(src,
                out_default=out_default,
                out_foreclosure=out_fcl,
                out_sale=out_sale,
                min_balance=args.min_balance)
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
