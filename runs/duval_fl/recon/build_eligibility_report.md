# Build Eligibility Report — Duval County, Florida (duval_fl)

County-level build verdict derived from the Source-of-Record Matrix, per
§16.D and MASTER_PROMPT §4.34/§4.35. Generated 2026-05-19. Framework v5.3.0.

---

## Verdict

    build_verdict            READY_TO_BUILD
    matrix county_build_status  READY_TO_BUILD
    auto_resolve_status      PARTIALLY_RESOLVED
    final_resolution_status  PARTIALLY_RESOLVED
    recommended build label  PARTIAL_BUILD

## Build Mode entry preconditions (§4.34) — check

    [x] Source-of-Record Matrix validates against $defs/sourceOfRecordMatrix.
    [x] Required SoR artifacts present (matrix JSON + MD, coverage map, API
        discovery report, this report, 10 per-source fingerprints).
    [x] county_build_status is READY_TO_BUILD.
    [x] At least one lead type has status LIVE_SOURCE_FOUND (15 do).
    [x] §01 recon sub-steps complete — see PDF/sample-inspection, API discovery,
        and bulk-availability notes below.

## Lead-type status tally (27 canonical types)

    LIVE_SOURCE_FOUND                    13
        Foreclosure, Lis Pendens, Civil Judgment, Abstract of Judgment,
        Mechanic Lien, Construction Lien, Federal Tax Lien, State Tax Lien,
        Affidavit of Heirship, Executor Deed, Administrator Deed, Code Lien,
        Eviction
    LIVE_SOURCE_FOUND_LIMITED_COVERAGE   2   Tax Sale Certificate, Tax Delinquency
    SOURCE_FOUND_BLOCKED                 4   Sheriff Sale, Tax Lien Foreclosure,
                                             Tax Sale, Demolition, Condemnation (5)
    SOURCE_FOUND_NEEDS_LOGIN             2   Probate, Divorce
    SOURCE_FOUND_PAID                    1   Bankruptcy
    NEEDS_OPERATOR_REVIEW                1   Surplus
    NOT_APPLICABLE_IN_STATE              3   Trustee Sale, Notice of Trustee Sale,
                                             Notice of Substitute Trustee Sale
    (tally: 13+2+5+2+1+1+3 = 27)

## Required §01 recon sub-steps

### PDF / Sample Document Inspection (§01.22)

Sample documents inspected: PARTIAL. The headline source
(clerk_official_records) is a live public search portal; its recorded-document
PDFs are free to view. Direct document fetches were NOT performed during recon
because recon is metadata-only (§01.17) and record extraction belongs to Build
Mode. The document type taxonomy and field availability were established from
Florida standard recording practice and the portal's search-field set
(Grantor/Grantee, Doc Type, Record Date, Book/Page, Instrument #,
Consideration, Case #). Recorded instruments in Florida carry property legal
description, parties, recording date, instrument number, and (for distress
instruments) case number — sufficient to originate leads. The two RealAuction
auction sources returned HTTP 403 to the recon fetch tool, so their sample
documents could not be inspected — flagged for Build Mode once browser access
is established.

### Documented API Discovery (§01.23)

Documented API found: Y for enrichment (JaxGIS ArcGIS REST at
maps.coj.net/coj/rest/services; FL DOR bulk file portal). N for every primary
lead source — search paths /api, /swagger, /docs, /api-docs, Postman, GitHub,
and vendor docs were checked per api_discovery_report.md. Primary lead ingestion
uses HTML adapters; this is not a blocker.

### Bulk-Data Availability Classification (§01.24)

    clerk_official_records   BATCH_QUERY    — searchable by date range + doc
                             type; daily windows enumerate new recordings.
    clerk_core_court         BATCH_QUERY    — searchable by filing date + division.
    foreclosure_auction      BATCH_QUERY    — auction calendar by date (blocked).
    tax_deed_auction         BATCH_QUERY    — auction calendar by date (blocked).
    tax_certificate_sale     FULL_COUNTY_BULK — advertised delinquent list is the
                             full county delinquent set (seasonal).
    tax_collector            PER_RECORD_ONLY — per-account lookup; coverage
                             bounded by the externally-resolved parcel set.
    parcel_master            PER_RECORD_ONLY (portal) / FULL_COUNTY_BULK via DOR.
    gis_parcels              FULL_COUNTY_BULK — ArcGIS layer query.
    dor_parcel_bulk          FULL_COUNTY_BULK — annual NAL roll + parcel GIS.

## Why READY_TO_BUILD and not READY_WITH_BLOCKERS

The §4.10 READY_TO_BUILD test — a verified primary lead source fully accessible
without escalation, an accessible primary document type, enrichment available,
no critical blocker — is fully met by clerk_official_records plus the three
enrichment layers. The verified headline source itself has zero residual access
work; the blockers sit on ADDITIONAL primary sources whose lead types are
already independently covered by recorded instruments. Coverage is partial (the
recommended dashboard label is PARTIAL_BUILD), but build eligibility is not in
doubt. No Do Not Proceed Matrix condition fired.

## Operator decisions carried forward

    1. Build Mode: resolve the RealAuction WAF (foreclosure_auction,
       tax_deed_auction) with Playwright — FREE, no credentials needed.
    2. code_enforcement: confirm a non-public portal or accept manual/records
       ingestion — low priority, recorded code liens already covered.
    3. Bankruptcy: decide whether to fund PACER access.
    4. clerk_core_court probate/family: decide whether to register the free
       enhanced-access account.
