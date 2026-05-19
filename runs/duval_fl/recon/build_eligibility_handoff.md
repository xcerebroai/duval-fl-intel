# Build Eligibility Handoff — Duval County, Florida (duval_fl)

Phase 0.G + verdict computation per §01.15. Generated 2026-05-19. Framework v5.3.0.

---

## Counts

    VERIFIED_OFFICIAL sources        10 of 10 discovered
    By role:
        PRIMARY_LEAD_SOURCE          6  (clerk_official_records, clerk_core_court,
                                         foreclosure_auction, tax_deed_auction,
                                         tax_certificate_sale, tax_collector)
        BLOCKED_SOURCE               1  (code_enforcement)
        ENRICHMENT_SOURCE            3  (parcel_master, gis_parcels, dor_parcel_bulk)
    By access classification:
        OPEN_PUBLIC                  6  (clerk_official_records, clerk_core_court,
                                         tax_collector, tax_certificate_sale,
                                         parcel_master, gis_parcels, dor_parcel_bulk
                                         — 7; tax_certificate_sale seasonal)
        BLOCKED                      2  (foreclosure_auction, tax_deed_auction)
        UNKNOWN                      1  (code_enforcement)

## Accessible primary sources count

    3 fully-accessible primary lead sources without operator escalation:
        clerk_official_records  (OPEN_PUBLIC)
        clerk_core_court        (OPEN_PUBLIC — civil/foreclosure/eviction tier)
        tax_collector           (OPEN_PUBLIC — per-record)
    + tax_certificate_sale (OPEN_PUBLIC but seasonal) = 4 with the seasonal caveat.

## Accessible primary document types

From clerk_official_records (the headline source), all LIVE:
    LIS_PENDENS, NOTICE_OF_SALE, FINAL_JUDGMENT_OF_FORECLOSURE,
    CERTIFICATE_OF_TITLE, JUDGMENT, CONSTRUCTION_LIEN, FEDERAL_TAX_LIEN,
    STATE_TAX_LIEN, TAX_DEED, EXECUTORS_DEED, AFFIDAVIT_OF_HEIRSHIP, CODE_LIEN.
From clerk_core_court: FORECLOSURE (docket), EVICTION.
From tax_collector: TAX_DELINQUENCY.  From tax_certificate_sale: TAX_SALE_CERTIFICATE.

## Blockers by type

    TECHNICAL   foreclosure_auction, tax_deed_auction — RealAuction anti-bot
                WAF (HTTP 403 to non-browser clients). Auto-resolvable in Build
                Mode with a real browser engine (Playwright). FREE cost.
    PERMISSION  clerk_core_court probate/family document tier — free registered
                account needed for enhanced access (docket index still public).
    HARD/UNKNOWN code_enforcement — no public structured portal located;
                requires operator review (confirm a non-public portal, or accept
                a manual-assisted / records-request path).
    PAID        Bankruptcy via PACER — federal, paid; out of county-source scope.

## Recommended provisional verdict

    READY_TO_BUILD

Rationale: §4.10 READY_TO_BUILD requires at least one verified PRIMARY lead
source fully accessible (OPEN_PUBLIC / SEARCH_ONLY_PUBLIC) with at least one
accessible primary document type, plus enrichment available, and no critical
blocker preventing Phase 1+. All conditions hold:
  - clerk_official_records is verified, OPEN_PUBLIC, and independently
    originates ~15 of the 27 lead types (foreclosure via lis pendens, all lien
    types, judgments, tax deeds, estate deeds, recorded code liens).
  - Enrichment is available three ways (parcel_master, gis_parcels ArcGIS API,
    dor_parcel_bulk NAL roll).
  - The blocked sources (auction calendars, code-enforcement cases) reduce
    COVERAGE of specific lead types but do not block Build Mode — a complete,
    honest lead board is buildable from recorded instruments today.

## Justification trail

    clerk_official_records  PRIMARY · OPEN_PUBLIC · verified via duvalclerk.com
        official link → contributes the verdict's accessible-primary requirement.
    clerk_core_court        PRIMARY · OPEN_PUBLIC (civil) · adds eviction +
        foreclosure docket coverage.
    tax_collector           PRIMARY · OPEN_PUBLIC · adds tax-delinquency, bounded
        per-record coverage.
    tax_certificate_sale    PRIMARY · OPEN_PUBLIC seasonal · adds tax-certificate
        coverage; cadence-bound to the annual June sale.
    foreclosure_auction     PRIMARY · BLOCKED (technical WAF) · not required for
        the verdict; foreclosure already LIVE via clerk_official_records.
    tax_deed_auction        PRIMARY · BLOCKED (technical WAF) · not required;
        recorded tax deeds already LIVE via clerk_official_records.
    code_enforcement        BLOCKED_SOURCE · no public portal · not required;
        recorded code liens already LIVE via clerk_official_records.
    parcel_master / gis_parcels / dor_parcel_bulk  ENRICHMENT · OPEN_PUBLIC ·
        satisfy the verdict's enrichment-available requirement.

## Do Not Proceed Matrix (§4.11) — check

    No condition fired. A verified primary event source is accessible; primary
    lead sources are verified; not enrichment-only; not all P0 sources blocked;
    config validates (Step 4); portal proof present for the headline P0 source;
    the dashboard will contain real event-based leads; data is not parcel-only;
    no paid/login wall on the headline source; public access to records is
    confirmed; verification_confidence HIGH on the headline P0 source.

## Recommended operator next actions

    1. Authorize Build Mode (PARTIAL_BUILD label) to build from
       clerk_official_records + clerk_core_court + tax_collector +
       tax_certificate_sale, with the three enrichment layers.
    2. In Build Mode, resolve the RealAuction WAF on foreclosure_auction and
       tax_deed_auction via Playwright + network-request inspection.
    3. Decide the code_enforcement path: confirm a non-public portal exists, or
       accept manual-assisted / records-request ingestion (low priority —
       recorded code liens are already covered).
    4. Decide whether to fund PACER for the Bankruptcy lead type.
