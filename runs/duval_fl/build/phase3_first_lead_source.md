# Phase 3 — First Primary Event Source — Duval County, Florida (duval_fl)

Build Mode, Phase 3. Completed 2026-05-21. Framework v5.3.1.
Build classification: PARTIAL_BUILD.

---

## Outcome: SUCCESS — primary event source built and verified (NOT blocked)

Phase 3 built the first PRIMARY EVENT SOURCE for the Duval build. This is the
source that originates lead rows (§13.2). The Phase 3 halt contingency — a
bot-gate / SPA / headless-browser blocker — did NOT trigger: the source is
fully drivable with the Python standard library.

## Adapter built

`scrapers/clerk_official_records.py` — Duval County Clerk of Courts Official
Records adapter.

- **Source:** `clerk_official_records` — `PRIMARY_LEAD_SOURCE` /
  `PRIMARY_EVENT_SOURCE`. The P0 `mvp_required` headline source in the recon
  Source-of-Record Matrix.
- **Portal:** `https://or.duvalclerk.com/` — Acclaim (ASP.NET MVC + Kendo UI).
- **Tooling:** Python standard library only (`urllib` + `http.cookiejar`).
  No browser, no SPA renderer, no third-party deps.

## Access path (recon-confirmed live)

The portal is reachable with stdlib HTTP — no WAF, no HTTP 403, no CAPTCHA,
no SPA wall. Drive sequence:

    1. GET  /                          -> disclaimer page
    2. POST /search/Disclaimer         -> session cookies (ASP.NET_SessionId,
       (Disclaimer=true)                  __RequestVerificationToken, ARRAffinity)
    3. POST /search/SearchTypeRecordDate  -> stores the search, returns the
       (RecordDate=M/D/YYYY)               Kendo results-grid page
    4. POST /Search/GridResults        -> JSON {"Data":[...],"Total":N},
       (Kendo aspnetmvc-ajax paging)       paginated

The recon flagged this source as MEDIUM difficulty with a possible disclaimer
cookie gate; Phase 3 confirmed exactly that — the disclaimer is a one-field
POST and the results come back as clean JSON from `/Search/GridResults`.

## Lead origination (the real test)

Each `/Search/GridResults` row is one recorded instrument — a dated, official
recorded event. Distress instruments in the live sample (record date
2026-05-20): LIS PENDENS, LIEN, JUDGMENT, CC COURT JUDGMENT,
JUDGMENT/SENTENCE, PROBATE, WARRANT. These are §13.2 primary lead events —
**Duval now has a source that originates lead rows.** Example captured rows:

    LIS PENDENS  inst 2026117213  LAKEVIEW LOAN SERVICING -> CANTY THEODORE R
    LIEN         inst 2026117183  BUILDERS FIRSTSOURCE    -> ALBARADO DANIELLE
    CC COURT JUDGMENT inst 2026117186  DNF ASSOCIATES LLC -> LEMUS PAUL

The recording index carries instrument number, doc type, record date, the
direct/indirect parties, book/page, and a legal description — but NO street
address or parcel id (clerk records are name + legal-description indexed). The
Phase 4 matcher joins these events to parcels via the Phase 2 gis_parcels
enrichment layer. Which party is the debtor is doc-type-specific — the §17
debtor party rules in the (not-yet-built) translator decide; the adapter
normalizes both `direct_name` and `indirect_name`.

## Contract conformance (§4.32)

The adapter normalizes Acclaim field names into framework-canonical fields and
writes wrapped records to `data/raw/clerk_official_records.jsonl`:
`instrument_number`, `doc_type` (raw label — canonicalized downstream),
`record_date`, `recording_year/month`, `book_type`, `book_page`,
`direct_name`, `indirect_name`, `legal_description`, `case_number`,
`transaction_id`. The adapter pulls the FULL recording index per date; doc-type
→ canonical-type → source-class (lead / enrichment / negative_signal)
classification is the downstream normalize + translator layer's job, not the
scraper's.

## Live verification

    python3 scrapers/clerk_official_records.py --date 5/20/2026 --max-rows 200
    -> status OK, 200 records written, 0 routed to review

Doc-type distribution (200-row sample): JUDGMENT 53, SATISFACTION 22, DEED 20,
NOTICE COMMENCEMENT 18, MORTGAGE 18, ORDER 15, AFFIDAVIT 14, CC COURT JUDGMENT
7, TERMINATION 7, LIS PENDENS 4, JUDGMENT/SENTENCE 4, LIEN 2, PROBATE 1,
WARRANT 1, + others. (Full day 2026-05-20 = 1,523 recordings.)

## Fixture gate (§05 — eight standard scenarios)

`tests/fixtures/clerk_official_records/` — 8 fixtures captured from real
Acclaim GridResults data. `tests/test_scrapers.py` now gates both adapters:

    python3 tests/test_scrapers.py
    -> PASS: 24   FAIL: 0   (clerk_official_records + gis_parcels) — exit 0

## Status

Phase 3 complete — first primary event source built, live-verified,
fixture-gated. Duval now has a lead-originating source.

**Not yet done (Phase 3 continuation / Phase 4):** a translator for
`clerk_official_records` (config `translator` is currently `""`), applying the
§17 debtor party rules + §18 signal aggregation; the pipeline run that turns
these raw events into scored/stacked leads; the evidence ledger
(`REVIEW_GATE_4`); and the Phase 4 matcher joining clerk events to gis_parcels
for the property address. No dashboard yet — and no dashboard is valid until
those leads flow.
