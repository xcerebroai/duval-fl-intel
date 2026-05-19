# Phase 0 Change Manifest — Duval County, Florida (duval_fl)

Generated 2026-05-19. Framework v5.3.0. Phase: phase0 (Recon Mode).

---

## 1. Files created

    config/counties/duval_fl.json                         (populated county config — 91,304 bytes, schema VALIDATED)
    runs/duval_fl/recon/source_discovery.md
    runs/duval_fl/recon/source_verification.md
    runs/duval_fl/recon/portal_fingerprints.md
    runs/duval_fl/recon/access_classification.md
    runs/duval_fl/recon/source_role_classification.md
    runs/duval_fl/recon/document_type_discovery.md
    runs/duval_fl/recon/api_discovery_report.md
    runs/duval_fl/recon/operator_verified_sources.yml
    runs/duval_fl/recon/source_of_record_matrix.json      (schema VALIDATED via $defs/sourceOfRecordMatrix)
    runs/duval_fl/recon/source_of_record_matrix.md
    runs/duval_fl/recon/source_coverage_map.md
    runs/duval_fl/recon/build_eligibility_handoff.md
    runs/duval_fl/recon/build_eligibility_report.md
    runs/duval_fl/recon/recon_summary.md
    runs/duval_fl/recon/fingerprints/<10 per-source fingerprint JSONs>
    runs/duval_fl/PHASE0_CHANGE_MANIFEST.md               (this file)

Bootstrap-created earlier (scaffold/bootstrap_county.py): runs/duval_fl/LAUNCH_DUVAL_FL.md,
runs/duval_fl/operator_notes.md.

## 2. Files modified

    None. No pre-existing file was modified. operator_notes.md was left as the
    bootstrap template — no casual operator knowledge was volunteered this run.

## 3. Source URLs added (grouped by official_status / source_role)

PRIMARY_LEAD_SOURCE — OFFICIAL_COUNTY:
    clerk_official_records   https://or.duvalclerk.com/
    clerk_core_court         https://core.duvalclerk.com/
PRIMARY_LEAD_SOURCE — OFFICIAL_VENDOR_PORTAL:
    tax_certificate_sale     https://lienhub.com/county/duval
    tax_collector            https://fl-duval-taxcollector.publicaccessnow.com/PropertyTaxSearch.aspx
BLOCKED_SOURCE — OFFICIAL_VENDOR_PORTAL:
    foreclosure_auction      https://duval.realforeclose.com/
    tax_deed_auction         https://duval.realtaxdeed.com/
BLOCKED_SOURCE — OFFICIAL_CITY:
    code_enforcement         https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance
ENRICHMENT_SOURCE:
    parcel_master   OFFICIAL_COUNTY  https://paopropertysearch.coj.net/Basic/Search.aspx
    gis_parcels     OFFICIAL_CITY    https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer
    dor_parcel_bulk OFFICIAL_STATE   https://floridarevenue.com/property/Pages/DataPortal.aspx

## 4. Sources flagged UNVERIFIED

    None. All 10 sources reached VERIFIED_OFFICIAL official status.

## 5. Sources flagged NOT_FOUND

    None. Every applicable lead-type category mapped to at least one official
    candidate source.

## 6. Sources flagged BLOCKED_SOURCE (with next_access_strategy)

    foreclosure_auction   next_access_strategy = use_playwright
                          blocker: RealAuction anti-bot WAF (HTTP 403 to
                          non-browser clients). blocker_type TECHNICAL_BLOCKER.
    tax_deed_auction      next_access_strategy = use_playwright
                          blocker: same RealAuction WAF. TECHNICAL_BLOCKER.
    code_enforcement      next_access_strategy = manual_operator_assisted_pull
                          blocker: no public structured case-search portal.
                          blocker_type PUBLIC_ACCESS_UNCLEAR.

## 7. operator_override fields set to true

    None. No source required an operator override — the schema enforces
    operator_override only for UNVERIFIED / NOT_FOUND official_status, and no
    source landed there. The BLOCKED_SOURCE entries carry a clear
    next_access_strategy, satisfying the §4.7 confidence threshold without an
    override.

## 8. Open questions for the operator

    clerk_official_records  Confirm whether a one-time terms/disclaimer
                            acceptance precedes searching; capture the exact
                            document-type dropdown strings (Build Mode).
    clerk_core_court        Decide whether to register the free CORE
                            enhanced-access account for probate/family
                            document retrieval.
    tax_certificate_sale    Confirm the advertised-list export format and the
                            annual publication date (~3-4 weeks pre-sale).
    tax_collector           No bulk delinquent roll is exposed — decide whether
                            to request a delinquency extract from the Tax
                            Collector, else coverage stays per-record-bounded.
    code_enforcement        Does a non-public code-enforcement case portal
                            exist? If not, accept a manual / records-request
                            path, or rely on recorded code liens via OR.
    foreclosure_auction /   Build Mode: resolve the RealAuction WAF via
    tax_deed_auction        Playwright (FREE, no credentials).
    Bankruptcy lead type    Decide whether to fund PACER access (federal).
    parcel_master           Choose enrichment ingestion: ArcGIS REST index +
                            DOR NAL roll (recommended) vs per-record scrape.

## 9. Build Eligibility Gate result

    build_verdict            READY_TO_BUILD
    build_verdict_reason     A verified, fully public primary lead source
                             (clerk_official_records) independently originates
                             13+ canonical lead types; three enrichment layers
                             are available; the P0 gate passes. Blocked auction
                             calendars and the code-enforcement case system
                             reduce coverage of specific lead types but those
                             lead types are already covered by recorded
                             instruments — no critical blocker prevents Build
                             Mode. Recommended dashboard label: PARTIAL_BUILD.
    build_verdict_at         2026-05-19T14:30:00Z
    auto_resolve_status      PARTIALLY_RESOLVED
    final_resolution_status  PARTIALLY_RESOLVED
    matrix county_build_status  READY_TO_BUILD

## 10. Do Not Proceed Matrix conditions that fired

    None. All 11 conditions checked (build_eligibility_handoff.md) — none
    fired. A verified primary event source is accessible; primary sources are
    verified; the build is not enrichment-only; not all P0 sources are blocked;
    config validates; portal proof present for the headline P0 source; the
    dashboard will carry real event-based leads; data is not parcel-only; no
    paid/login wall on the headline source; public access to records is
    confirmed; verification_confidence HIGH on the headline P0 source.

## 11. Schema validation result

    PASS. config/counties/duval_fl.json validated against
    config/counties/_schema.json by scaffold/ops/write_county_config.py —
    status OK, schema_validation VALIDATED (jsonschema 4.26.0 installed).

    Note on the write process (transparency, §4.28.4): the writer rejected two
    earlier in-memory builds on distinct, precisely-located schema-enum errors
    — (a) source blocker_type "technical" -> "TECHNICAL_BLOCKER"; (b)
    auto_resolve_attempts entries missing the required attempt_order/timestamp/
    status fields. Each rejection was a different error showing forward
    progress, and the canonical writer functioned correctly throughout (no
    streaming-write corruption, the failure mode §4.28 exists to prevent). The
    build dict was re-built in memory each time per §4.28.1 and never streamed.
    The third in-memory build validated cleanly. This iterative
    schema-conformance is surfaced here explicitly for operator awareness.

## 12. Framework gate result (python scaffold/tests/run_all.py)

    PASS — all 4 gate tests green:
      [PASS] Golden path (test_golden_path.py)
      [PASS] County-agnostic regression (test_county_agnostic_regression.py)
      [PASS] Atomic county config writer (test_write_county_config.py)
      [PASS] Translator registry (test_translator_registry.py)
    Environment: python3 3.14.5, jsonschema 4.26.0. No environment setup issue.

## 13. Confirmation — no out-of-scope framework files modified

    CONFIRMED. The only files created or modified are config/counties/duval_fl.json
    and files under runs/duval_fl/. No knowledge_base/, scaffold/, MASTER_PROMPT.md,
    schema, template, README, or any other framework file was touched. The
    county-agnostic regression test passing independently confirms no Duval- or
    Florida-specific data leaked into universal framework directories.

## Human review gate

    REVIEW_GATE_1 (end of Phase 0) is now due. Operator signoff
    (gates/REVIEW_GATE_1.signoff.json) is required before Phase 1 may begin.
    Phase 1 (synthetic harness) cannot start without it.
