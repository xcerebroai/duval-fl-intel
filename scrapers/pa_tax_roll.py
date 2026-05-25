"""Duval Property Appraiser tax-roll adapter — parcel master ENRICHMENT
+ estate-titled-owner ORIGINATION.

Source id : pa_tax_roll          (parcel master enrichment)
            pa_tax_roll_estates  (estate-titled owner names = primary leads)
Portal    : https://www.jacksonville.gov/departments/property-appraiser/data-offerings
File      : DCPAO Real Estate pipe-delimited TXT (monthly uncertified release)

Stage classification — per the framework rule:

  ENRICHMENT (pa_tax_roll)
    Parcel master, owner_name, mailing address, situs address, just/market
    value, assessed value, taxable value, exemptions (HX homestead, HB
    banding, etc.), year-built (from 00005 building rows), legal description.
    The PA tax roll attaches downstream by parcel_id; it SUPERSEDES the
    JaxGIS gis_parcels enrichment for fields the COJ Parcels MapServer does
    not expose (year_built, exemption codes, owner mailing care-of line).

  PRIMARY EVENT SOURCE (pa_tax_roll_estates)
    Owner-name rows (record type 00003) where the name matches a
    word-boundary estate / life-estate pattern — "ESTATE OF", "EST OF",
    "ESTATE" at end-of-name, "EST" at end-of-name, "LIFE EST". These
    ORIGINATE standalone probate / estate leads per the framework rule —
    an estate-titled owner is itself a strong motivated-heir signal even
    absent a court filing.

  NOT-IN-FILE — DELINQUENCY
    The PA tax roll is a parcel master; it does NOT carry delinquent-tax
    status. The Duval tax-collector ledger (jaxtaxcollector.com via Grant
    Street Group) is the source of record for delinquency and tax certificate
    history. This adapter surfaces the gap honestly; a tax-collector adapter
    is a separate build (see config sources: tax_certificate_sale,
    tax_collector).

Record type schema (DCPAO pipe-delimited file):
  00001 : master row — pos 8-12 mailing, pos 22 assessed, pos 25 just value
  00002 : legal description (multi-row, concatenate by sequence)
  00003 : owner name (multi-row — multiple owners per parcel)
  00004 : situs address (street, city, zip)
  00005 : building characteristics (year-built in pos 9-10)
  00015 : exemption — HX = Homestead, HB = Homestead Banding, etc.
  00017 : sales history (deed type, sale date, sale price)

Output: §4.32 wrapped raw_record per record-class.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]

# The PA file uses an 11-char parcel id with a "R" suffix for real estate
# ("T" for tangible — Tangible file is separate). Strip the R to align with
# JaxGIS RE_NOSPACE format.
def _norm_parcel(s: str) -> str:
    s = (s or "").strip()
    return s[:-1] if s.endswith(("R", "r")) else s


# Estate-titled owner pattern. Word-boundary detection — matches:
#   "SMITH JOHN ESTATE OF"
#   "JONES MARY EST OF"
#   "BROWN BOB ESTATE"
#   "DOE JANE EST"
#   "DOE JANE (DECD)"
# Does NOT match:
#   "ESTABLISHED REALTY LLC" (no word boundary)
#   "WEST OF MILTON" (suffix containing EST but as letters in another word)
#   "OAK ESTATES SUBDIVISION" (ESTATES plural — fails \bESTATE\b)
# The regex anchors to whole-word EST / ESTATE preceded or followed by
# whitespace or end-of-string.
ESTATE_PATTERN = re.compile(
    r"(?:\b(?:ESTATE|EST)\s+OF\b)"            # "ESTATE OF"/"EST OF"
    r"|(?:\b(?:ESTATE|EST)\s*$)"              # trailing "ESTATE"/"EST"
    r"|(?:\bDEC(?:E)?D\b)"                    # "(DECD)" / "DECEASED" markers
    r"|(?:\(DECD\))",
    re.I,
)

# LIFE ESTATE / LIFE EST — a living life-tenant under a deliberate estate-
# planning arrangement (the owner is ALIVE; the remainderman is named on
# the same deed). NOT a probate signal. Detected separately and EXCLUDED
# from estate-titled origination.
LIFE_ESTATE_PATTERN = re.compile(
    r"\bLIFE\s+(?:ESTATE|EST)\b",
    re.I,
)

# Entity / corporate / trust / institutional keywords. When any of these
# match, the owner is NOT an individual decedent — the parcel is held by
# an entity that happens to have "ESTATE" in its name (e.g. "REAL ESTATE
# OF JACKSONVILLE LLC", "X TRUST & ESTATE"). Exclude from estate origination.
ENTITY_KEYWORDS_PATTERN = re.compile(
    r"\b(?:LLC|L\.L\.C\.?|INC\.?|INCORPORATED|CORP\.?|CORPORATION|"
    r"COMPANY|LP|LLP|LTD\.?|LIMITED|REALTY|PROPERTIES|HOLDINGS|"
    r"INVESTMENTS|HOMES|FUND|ASSOCIATION|PARTNERS|GROUP|BANK|CLUB|"
    r"FOUNDATION|ENTERPRISES|VENTURES|REAL\s+ESTATE|MINISTRIES)\b",
    re.I,
)

# Trust-tail keywords. "X TRUST" / "X TRUST OF" — a living-trust holding
# the parcel — also excluded from estate origination (the owner is the
# trustee, not a decedent). "TRUST ESTATE" is treated as the trust-side,
# not the probate-side.
TRUST_KEYWORDS_PATTERN = re.compile(
    r"\b(?:TRUST|TRUSTEE|REVOCABLE|IRREVOCABLE)\b",
    re.I,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _num(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int_or_none(s):
    f = _num(s)
    return int(f) if f is not None else None


def _safe(seq, i, default=""):
    """Get a 1-indexed pipe field (the file's record-type code is field 1)."""
    return seq[i] if i < len(seq) else default


def iter_lines(src: Path | str) -> Iterator[str]:
    """Stream the PA file. Accepts a .zip (containing one .txt) or a raw .txt."""
    p = Path(src)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            inner = [n for n in zf.namelist()
                     if n.lower().endswith(".txt")]
            if not inner:
                raise ValueError(f"no .txt inside {p}")
            with zf.open(inner[0]) as fh:
                for raw in io.TextIOWrapper(fh, encoding="latin-1",
                                             newline=""):
                    yield raw.rstrip("\r\n")
    else:
        with open(p, "r", encoding="latin-1") as fh:
            for raw in fh:
                yield raw.rstrip("\r\n")


def _master_to_enrichment(parts: list) -> dict:
    """Parse a 00001 master row into the per-parcel enrichment payload.

    Field positions (1-indexed within the original row, 0-indexed in the
    list returned by split('|')):
        [0]  record_type     "00001"
        [1]  parcel_id_raw   "0000010005R"
        [2]  section
        [3]  township
        [4]  range
        [5]  property_class_code (4-digit DOR-style)
        [6]  reserved flag (often "N")
        [7]  mailing care-of  ("C/O PROPERTY TAX COORDINATOR")
        [8]  mailing street   ("1 RAYONIER WAY")
        [9]  mailing city
        [10] mailing state
        [11] mailing zip
        [12] land use class (4-digit)
        [13] subclass
        [14] property_class description
        [15] (blank)
        [16] (blank)
        [17] just_value (market)
        [18] (number)
        [19] (number)
        [20] (number)
        [21] assessed (school)
        [22] assessed
        [23] (number)
        [24] just_value_total
        [25] (number)
        [26] (number)
        [27] (number)
        [28] class_flag
        [29] master_pid
        [30] acreage
    """
    return {
        "parcel_id":              _norm_parcel(_safe(parts, 1)),
        "section":                _safe(parts, 2),
        "township":               _safe(parts, 3),
        "range":                  _safe(parts, 4),
        "property_class_code":    _safe(parts, 5),
        "mail_care_of":           _safe(parts, 7),
        "owner_mailing_addr1":    _safe(parts, 8),
        "owner_mailing_city":     _safe(parts, 9),
        "owner_mailing_state":    _safe(parts, 10),
        "owner_mailing_zip":      _safe(parts, 11),
        "land_use_code":          _safe(parts, 12),
        "property_class":         _safe(parts, 14),
        "just_value":             _num(_safe(parts, 17)),
        "assessed_value_school":  _num(_safe(parts, 21)),
        "assessed_value":         _num(_safe(parts, 22)),
        "just_value_total":       _num(_safe(parts, 24)),
        "taxable_value_school":   _num(_safe(parts, 25)),
        "taxable_value":          _num(_safe(parts, 27)),
        "acreage":                _num(_safe(parts, 30)),
    }


def _building_year_built(parts: list) -> int | None:
    """Parse a 00005 building row → year built (position 9, sometimes 10).

        00005|0000060030R|1|0101|SFR 1 STORY|01|4|03|1980|1980|1.00|352917|2940
                                                ^^^ effective_year ^^^^ actual_year
    """
    yr = _int_or_none(_safe(parts, 8)) or _int_or_none(_safe(parts, 9))
    return yr if (yr and 1700 <= yr <= 2100) else None


def _exemption(parts: list) -> dict:
    """Parse a 00015 exemption row.

        00015|0000060030R|1|NADELEN ELIZABETH ANN|HX|Homestead|1.00|25000|-1
                            ^^^^ owner ^^^^^^^^^^|^^|^^label^^|^^^^|amt|expyr
    """
    return {
        "applicant":     _safe(parts, 3),
        "code":          _safe(parts, 4),
        "label":         _safe(parts, 5),
        "amount":        _num(_safe(parts, 7)),
        "expiry_year":   _safe(parts, 8),
    }


def _sale(parts: list) -> dict:
    """Parse a 00017 sales row.

        00017|0000090000R|2|BRAUN JOSEPH F JR|21144|01612|37|V|WD|Warranty Deed|
                              SA|Same As|07/26/2024|07/31/2024|975000
    """
    return {
        "grantee_name":      _safe(parts, 3),
        "or_book":           _safe(parts, 4),
        "or_page":           _safe(parts, 5),
        "instrument_code":   _safe(parts, 8),
        "instrument_label":  _safe(parts, 9),
        "qualification":     _safe(parts, 10),
        "qualification_lbl": _safe(parts, 11),
        "sale_date":         _safe(parts, 12),
        "recorded_date":     _safe(parts, 13),
        "sale_price":        _num(_safe(parts, 14)),
    }


def classify_estate_name(owner: str) -> str:
    """Three-way estate classification per standing rule #4.

    Returns one of:
      "individual_estate"  — "ESTATE OF [name]", "EST OF", "[name] ESTATE",
                              "(DECD)" on an individual person → probate lead
      "life_estate"        — "LIFE ESTATE" / "LIFE EST" → living life-tenant,
                              NOT a probate lead, tagged separately, NOT
                              emitted as an origination event
      "entity_estate"      — company / trust / institutional owner that
                              happens to have ESTATE in the name → NOT a
                              probate lead, dropped from origination
      ""                   — no estate match
    """
    if not owner or len(owner.strip()) < 4:
        return ""
    # Life estate first — it's the most common false positive in FL.
    if LIFE_ESTATE_PATTERN.search(owner):
        return "life_estate"
    if not ESTATE_PATTERN.search(owner):
        return ""
    if ENTITY_KEYWORDS_PATTERN.search(owner):
        return "entity_estate"
    if TRUST_KEYWORDS_PATTERN.search(owner):
        return "entity_estate"
    return "individual_estate"


def is_estate_titled(owner: str) -> bool:
    """Back-compat wrapper — True only for individual-person estate matches.
    Companies, trusts, and life estates DO NOT originate probate leads."""
    return classify_estate_name(owner) == "individual_estate"


def _flush_parcel(parcel_id: str, master: dict | None,
                  owners: list[str], situs: dict | None,
                  year_built: int | None, legal: str,
                  exemptions: list[dict], sales: list[dict]) -> dict | None:
    """Build the per-parcel enrichment record once all the parcel's rows
    have streamed past."""
    if master is None:
        return None
    # primary owner = the first 00003 row by sequence
    primary_owner = owners[0] if owners else ""
    coowners = owners[1:] if len(owners) > 1 else []
    payload = dict(master)
    payload.update({
        "owner_name":              primary_owner,
        "additional_owner_names":  coowners,
        "owner_count":             len(owners),
        "situs_address":           (situs or {}).get("street") or None,
        "situs_city":              (situs or {}).get("city")   or None,
        "situs_state":             "FL",
        "situs_zip":               (situs or {}).get("zip")    or None,
        "year_built":              year_built,
        "legal_description":       legal or None,
        "exemptions":              exemptions,
        "homestead":               any(e.get("code") == "HX" for e in exemptions),
        "last_sale_date":          (sales[0]["sale_date"] if sales else None),
        "last_sale_price":         (sales[0]["sale_price"] if sales else None),
        "sales_history":           sales[:10],   # cap to 10
        "county":                  "Duval",
        "state":                   "FL",
    })
    return {
        "raw_record_id":      f"pa_tax_roll:{parcel_id}",
        "source_id":          "pa_tax_roll",
        "source_url":         "https://www.jacksonville.gov/departments/"
                              "property-appraiser/data-offerings",
        "source_fetched_at":  _now_iso(),
        "parser_confidence":  95 if payload.get("owner_name") else 70,
        "raw_payload":        payload,
    }


def _estate_event(parcel_id: str, owner: str, master: dict | None,
                  situs: dict | None, legal: str, sequence: int,
                  refresh_iso: str) -> dict:
    """Build a wrapped PRIMARY EVENT record for one estate-titled owner row."""
    mailing = ""
    if master:
        mailing = " ".join(filter(None, [
            master.get("owner_mailing_addr1"),
            master.get("owner_mailing_city"),
            master.get("owner_mailing_state"),
            master.get("owner_mailing_zip"),
        ]))
    return {
        "raw_record_id":      f"pa_tax_roll_estates:{parcel_id}:{sequence}",
        "source_id":          "pa_tax_roll_estates",
        "source_url":         "https://www.jacksonville.gov/departments/"
                              "property-appraiser/data-offerings",
        "source_fetched_at":  _now_iso(),
        "parser_confidence":  92,
        "raw_payload": {
            "owner_name":         owner,
            "owner_role":         "estate_named_owner",
            "parcel_id":          parcel_id,
            "situs_address":      (situs or {}).get("street") or None,
            "situs_city":         (situs or {}).get("city") or None,
            "situs_state":        "FL",
            "situs_zip":          (situs or {}).get("zip") or None,
            "owner_mailing":      mailing or None,
            "assessed_value":     (master or {}).get("assessed_value"),
            "just_value":         (master or {}).get("just_value"),
            "legal_description":  legal or None,
            "doc_type":           "ESTATE TITLED OWNER",
            # PA estate is a continuous-status signal (the parcel master shows
            # an estate-titled owner today; we don't know WHEN the estate
            # designation began). We expose the snapshot date so the scoring
            # seam can age it, but mark `is_snapshot_event` so the dashboard
            # does NOT count it toward NEW / last-30-days recency filters.
            "event_date":         refresh_iso,
            "recorded_date":      refresh_iso,
            "snapshot_date":      refresh_iso,
            "is_snapshot_event":  True,
            "county":             "Duval",
            "state":              "FL",
        },
    }


def run(src: Path, *, out_enrichment: Path, out_estates: Path,
        max_parcels: int | None = None) -> dict:
    """Stream the PA file once, emit enrichment + estate-origination JSONL.

    Returns a stats dict.
    """
    out_enrichment.parent.mkdir(parents=True, exist_ok=True)
    out_estates.parent.mkdir(parents=True, exist_ok=True)
    tmp_enr = out_enrichment.with_suffix(".jsonl.tmp")
    tmp_est = out_estates.with_suffix(".jsonl.tmp")

    parcels_written = 0
    estates_written = 0
    estate_dedup_skipped = 0
    estate_life_excluded = 0
    estate_entity_excluded = 0
    estate_parcels: set[str] = set()
    estate_dedup_keys: set[tuple[str, str]] = set()
    homestead_parcels = 0
    refresh_iso = datetime.now(timezone.utc).date().isoformat()

    current_pid: str | None = None
    master: dict | None = None
    owners: list[str] = []
    situs: dict | None = None
    year_built: int | None = None
    legal_parts: dict[int, str] = {}
    exemptions: list[dict] = []
    sales: list[dict] = []

    def flush():
        nonlocal parcels_written, homestead_parcels
        if current_pid is None:
            return
        legal = " ".join(legal_parts[k] for k in sorted(legal_parts.keys()))
        rec = _flush_parcel(current_pid, master, owners, situs, year_built,
                            legal, exemptions, sales)
        if rec:
            fh_enr.write(json.dumps(rec, ensure_ascii=False) + "\n")
            parcels_written += 1
            if rec["raw_payload"].get("homestead"):
                homestead_parcels += 1

    with open(tmp_enr, "w", encoding="utf-8") as fh_enr, \
         open(tmp_est, "w", encoding="utf-8") as fh_est:
        for line in iter_lines(src):
            if not line:
                continue
            parts = line.split("|")
            rt = parts[0] if parts else ""
            raw_pid = _safe(parts, 1)
            pid = _norm_parcel(raw_pid)
            if not pid:
                continue
            if pid != current_pid:
                # boundary — flush previous
                flush()
                if max_parcels is not None and parcels_written >= max_parcels:
                    break
                # reset
                current_pid = pid
                master = None
                owners = []
                situs = None
                year_built = None
                legal_parts = {}
                exemptions = []
                sales = []
            if rt == "00001":
                master = _master_to_enrichment(parts)
            elif rt == "00002":
                seq = _int_or_none(_safe(parts, 2)) or len(legal_parts) + 1
                legal_parts[seq] = _safe(parts, 3)
            elif rt == "00003":
                owner = _safe(parts, 3).strip()
                if owner:
                    owners.append(owner)
                    klass = classify_estate_name(owner)
                    if klass == "life_estate":
                        estate_life_excluded += 1
                    elif klass == "entity_estate":
                        estate_entity_excluded += 1
                    elif klass == "individual_estate":
                        # Dedupe per (parcel_id, normalized name) — the CSV
                        # occasionally carries the same individual estate on
                        # multiple sequence rows for one parcel.
                        norm_name = re.sub(r"\s+", " ", owner.upper()).strip()
                        key = (pid, norm_name)
                        if key in estate_dedup_keys:
                            estate_dedup_skipped += 1
                        else:
                            estate_dedup_keys.add(key)
                            ev = _estate_event(
                                pid, owner, master, situs,
                                " ".join(legal_parts.get(k, "")
                                         for k in sorted(legal_parts)),
                                len(owners), refresh_iso)
                            fh_est.write(json.dumps(ev, ensure_ascii=False) + "\n")
                            estates_written += 1
                            estate_parcels.add(pid)
            elif rt == "00004":
                # 00004 fields (0-indexed in the parts list):
                #   0:rt, 1:pid, 2:house_number, 3:direction (N/S/E/W),
                #   4:street_name, 5:street_type (LN/AVE/HWY/etc.),
                #   6:unit, 7:city, 8:zip+ext, 9:reserved
                # Earlier versions of this adapter mis-aligned the
                # positions and dropped the house number — that broke the
                # downstream PA-tax-roll address join for ~all enriched
                # leads (cards showed "STREET TYPE, JACKSONVILLE, FL"
                # with no house number). The fix lifts house_number +
                # direction into the composed street address.
                hnum = _safe(parts, 2).strip()
                direction = _safe(parts, 3).strip()
                street_name = _safe(parts, 4).strip()
                street_type = _safe(parts, 5).strip()
                unit = _safe(parts, 6).strip()
                street = " ".join(filter(None, [
                    hnum, direction, street_name, street_type, unit]))
                situs = {
                    "street": street,
                    "city":   _safe(parts, 7).strip(),
                    "zip":    _safe(parts, 8).strip().split("-")[0],
                }
            elif rt == "00005":
                yr = _building_year_built(parts)
                if yr and (year_built is None or yr < year_built):
                    year_built = yr
            elif rt == "00015":
                exemptions.append(_exemption(parts))
            elif rt == "00017":
                sales.append(_sale(parts))
            # other record types (00006..00014, 00016) — skipped
        # final flush
        flush()

    tmp_enr.replace(out_enrichment)
    tmp_est.replace(out_estates)

    return {
        "status":                  "OK",
        "source_file":             str(src),
        "parcels_written":         parcels_written,
        "estates_written":         estates_written,
        "estate_parcels_distinct": len(estate_parcels),
        "estate_life_excluded":    estate_life_excluded,
        "estate_entity_excluded":  estate_entity_excluded,
        "estate_dedup_skipped":    estate_dedup_skipped,
        "homestead_parcels":       homestead_parcels,
        "enrichment_path":         str(out_enrichment.relative_to(REPO_ROOT)),
        "estates_path":            str(out_estates.relative_to(REPO_ROOT)),
    }


def download(url: str, dest: Path) -> Path:
    """Download a PA data-offering file to dest. Returns dest path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}", file=sys.stderr)
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "xcerebro-duval-pa/0.1 (+private repo)",
            "Accept": "*/*",
        })
    with urllib.request.urlopen(req, timeout=300) as resp, \
         open(dest, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    return dest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Duval PA tax-roll adapter — parcel enrichment + "
                    "estate-titled-owner origination.")
    p.add_argument("--src", default=None,
                   help="Local path to the PA pipe-delimited file "
                        "(.zip or .txt). If omitted with --url, --url is "
                        "downloaded.")
    p.add_argument("--url", default=None,
                   help="URL to the PA pipe-delimited zip; downloaded into "
                        "data/raw/pa_tax_roll_src.zip if --src is not set.")
    p.add_argument("--out-enrichment", default=None,
                   help="Output JSONL for parcel enrichment (default "
                        "data/raw/pa_tax_roll.jsonl).")
    p.add_argument("--out-estates", default=None,
                   help="Output JSONL for estate-titled events (default "
                        "data/raw/pa_tax_roll_estates.jsonl).")
    p.add_argument("--max-parcels", type=int, default=None,
                   help="Cap total parcels written (for bounded testing).")
    args = p.parse_args()

    if not args.src and not args.url:
        print("must pass --src or --url", file=sys.stderr)
        return 2

    src = Path(args.src) if args.src else (
        REPO_ROOT / "data/raw/pa_tax_roll_src.zip")
    if args.url and not src.exists():
        download(args.url, src)

    out_enr = Path(args.out_enrichment) if args.out_enrichment else (
        REPO_ROOT / "data/raw/pa_tax_roll.jsonl")
    out_est = Path(args.out_estates) if args.out_estates else (
        REPO_ROOT / "data/raw/pa_tax_roll_estates.jsonl")

    stats = run(src, out_enrichment=out_enr, out_estates=out_est,
                max_parcels=args.max_parcels)
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
