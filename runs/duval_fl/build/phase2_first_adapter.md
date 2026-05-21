# Phase 2 — First Adapter — Duval County, Florida (duval_fl)

Build Mode, Phase 2. Completed 2026-05-21. Framework v5.3.1.
Build classification: PARTIAL_BUILD.

---

## Scope — ENRICHMENT FOUNDATION ONLY (no lead origination)

Phase 2 built an **enrichment foundation only**. `gis_parcels` is a parcel /
GIS source — per the §13 Lead Origination Contract (HARD RULE 13.4.1) it is an
`ENRICHMENT_SOURCE` and **cannot originate a lead row**. This adapter produces
**zero lead rows**. It emits parcel STATE (owner, situs, value, sale date) that
DECORATES leads created elsewhere; it never creates them.

**Duval County currently has zero leads.** No primary event source has been
built yet. The dashboard is NOT valid, NOT complete, and must NOT be deployed
on the strength of this enrichment output — a dashboard with no primary-event
lead rows is a No False Dashboard violation (MASTER_PROMPT §4.11). Lead
origination is the Phase 3 task (`clerk_official_records`).

---

## Adapter built

`scrapers/gis_parcels.py` — Duval County (City of Jacksonville / JaxGIS)
parcel enrichment adapter.

- **Source:** `gis_parcels` (ENRICHMENT_SOURCE) — the easiest source in the
  Source-of-Record Matrix: an open, documented ArcGIS REST API.
- **Portal:** `https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer`
  layer 0 ("Parcels" — 405,716 polygon features, 74 fields).
- **Tooling:** standard-library `urllib` via the framework's county-agnostic
  `scaffold/scrapers/_arcgis_featureserver.py` helper. No browser, no SPA, no
  hidden API — no Phase 2 tooling blocker encountered.

## Why this source first

Per MASTER_PROMPT §6, Phase 2 builds one scraper — the easiest, an enrichment
source — to validate the matching layer before lead sources are wired. The
recon Source-of-Record Matrix flagged `gis_parcels` as `OPEN_PUBLIC` with a
documented ArcGIS API (`api_discovery_report.md`); it is the lowest-risk first
adapter. It is an `ENRICHMENT_SOURCE` — it never originates a lead (§13.4.1).

## Contract conformance (§4.32 scraper-to-translator)

The adapter NORMALIZES the 74 COJ field names into framework-canonical
lowercase field names and writes one wrapped record per line:

    raw_record_id · source_id · source_url · source_fetched_at ·
    parser_confidence · raw_payload{ canonical fields }

COJ → canonical mapping (key fields): `RE_NOSPACE`→parcel_id,
`LNAMEOWNER`(+`LNAME2`)→owner_name, `LONGNAME`(+`UNIT_NO`)→situs_address,
`ADDRCITY`/`ZIPCODE`→situs_city/zip, `MAILADDR1-3`→owner_mailing_addr1,
`CAMA_VAL`→assessed_value, `TOT_LND_VA`→land_value, `TOT_IMPR_V`→
improvement_value, `SALESLYY/MM/DD`→last_sale_date, `DESCPU`/`PUSE`→
property_class/land_use_code, `ACRES`→acreage, `LEGAL1-5`→legal_description.
The layer carries no year-built or sale-price field — those canonical fields
are emitted `null` (resolved later from the Property Appraiser parcel_master).

## Live verification (sample reviewed against the live source)

    python3 scrapers/gis_parcels.py --limit 25
    -> status OK, 25 records written, 0 routed to review, all parser_confidence 95

Sample records spot-checked against the live ArcGIS source: owner names,
situs addresses, mailing addresses, assessed/land/improvement values, last
sale dates (composed from SALESLYY/MM/DD), property class, and acreage all
normalize correctly. Condo unit numbers are appended to situs_address.
Output: `data/raw/gis_parcels.jsonl` (gitignored — transient raw scrape).

## Fixture gate (§05 — eight standard scenarios)

`tests/fixtures/gis_parcels/` — 8 fixtures captured from real source data
(empty, single, multiple, pagination, record_detail, document_download,
blocked_session, malformed_record). `tests/test_scrapers.py` is the harness;
the adapter exposes a `parse_fixture()` entry point.

    python3 tests/test_scrapers.py
    -> PASS: 12   FAIL: 0   — scraper fixture gate satisfied (exit 0)

All eight scenarios verified: empty→[], single→1 wrapped record, multiple→3,
pagination→walks pages, record_detail→enriched, document_download→N/A skip
flag (ArcGIS metadata API has no document layer), blocked_session→
SourceBlockedError (exit-4 class), malformed_record→routed to review with
parser_confidence < 80.

## Note — stale county-side scraper leftovers

`scrapers/parcel_master.py` and `scrapers/foreclosure_notices_map.py` in this
repo are **Bexar County leftovers** from the harness extraction (hardcoded
`maps.bexar.org`, BCAD fields, `runs/bexar_tx/` references). `scrapers/` is
county-scoped (exempt from the §4.31 universality scan), so this is not a
contract violation — but they are the wrong county. They should be deleted or
replaced before they are wired into the Duval pipeline. The Duval config's
`parcel_master` source points at `scrapers/parcel_master.py`; that adapter is
a Phase 2/4 follow-up, not yet built for Duval. Surfaced for operator
awareness — not fixed in this Phase 2 step (out of scope: Phase 2 builds one
adapter).

## Status

Phase 2 complete — as an ENRICHMENT FOUNDATION only. First adapter built,
live-verified, fixture-gated. It originates **zero leads** by design.
`REVIEW_GATE_3` (end of Phase 2 / first scraper output) gates Phase 3.
Phase 3 builds the first PRIMARY EVENT SOURCE — `clerk_official_records`
(or.duvalclerk.com), recorded distress instruments — which is where Duval's
first real lead rows originate. Until Phase 3 lands a primary event source,
Duval has no leads and no valid dashboard.
