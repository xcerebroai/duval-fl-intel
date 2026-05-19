# Recon Summary — Duval County, Florida (duval_fl)

Operator-facing executive summary of Phase 0 recon.
Generated 2026-05-19. Framework v5.3.0. Phase: phase0 (Recon Mode).

---

## Bottom line

**Duval County is READY_TO_BUILD.** It has a verified, fully-open primary lead
source — the Clerk of Courts Official Records search — that independently
originates the bulk of the canonical lead types, plus three working enrichment
layers. A daily-refresh distress lead board can be built now.

Coverage is partial: two foreclosure/tax auction calendars (RealAuction) are
anti-bot-blocked and the city code-enforcement case system has no public portal.
None of that blocks the build — those lead types are already covered by recorded
instruments — but it makes the recommended first dashboard a **PARTIAL_BUILD**.

## What was found

Duval County is a consolidated city-county government (City of Jacksonville).
Florida is a judicial-foreclosure state. Ten official sources were verified:

Primary lead sources (6):
  - **clerk_official_records** — or.duvalclerk.com — OPEN_PUBLIC. The moat.
    Recorded instruments since 1988: lis pendens, all lien types, federal/state
    tax liens, judgments, tax deeds, personal-representative deeds, affidavits
    of heirship, recorded code liens. P0.
  - **clerk_core_court** — core.duvalclerk.com — OPEN_PUBLIC for civil /
    foreclosure / eviction dockets (probate & family need a free account). P0.
  - **tax_collector** — fl-duval-taxcollector.publicaccessnow.com — OPEN_PUBLIC
    per-account delinquency lookup. P1.
  - **tax_certificate_sale** — lienhub.com/county/duval — OPEN_PUBLIC, seasonal
    (annual May–June certificate auction). P1.
  - **foreclosure_auction** — duval.realforeclose.com — BLOCKED (RealAuction
    anti-bot WAF). P0, resolvable in Build Mode.
  - **tax_deed_auction** — duval.realtaxdeed.com — BLOCKED (same WAF). P1.

Enrichment sources (3):
  - **parcel_master** — paopropertysearch.coj.net — Property Appraiser. P2.
  - **gis_parcels** — maps.coj.net ArcGIS REST API (documented). P2.
  - **dor_parcel_bulk** — floridarevenue.com — FL DOR bulk NAL roll + GIS. P2.

Blocked / review (1):
  - **code_enforcement** — jacksonville.gov Municipal Code Compliance — no
    public structured portal; operator review needed.

## P0 gate

**GATE PASS.** clerk_official_records is a P0 daily-refresh distress source,
currently unblocked and publicly searchable. The product premise — fresh
county distress intelligence with daily refresh — is satisfiable today.

## Lead-type sweep (27 canonical types)

13 LIVE · 2 LIVE-limited · 5 blocked · 2 needs-login · 1 paid · 1 review ·
3 not-applicable-in-state (Trustee Sale family — FL is judicial). Full detail
in source_of_record_matrix.md / .json.

## Verdict and next action

    build_verdict   READY_TO_BUILD
    next action     Authorize Build Mode (PARTIAL_BUILD) to build from the four
                    accessible primary sources + three enrichment layers. In
                    Build Mode, resolve the RealAuction WAF via Playwright and
                    decide the code-enforcement / PACER / family-records paths.

This recon stops here. Build Mode does not begin without explicit operator
authorization (Build Mode Approval Gate, MASTER_PROMPT §4.15).

## Artifact index (runs/duval_fl/recon/)

    source_discovery.md            source_role_classification.md
    source_verification.md         document_type_discovery.md
    portal_fingerprints.md         api_discovery_report.md
    access_classification.md       operator_verified_sources.yml
    source_of_record_matrix.json   source_coverage_map.md
    source_of_record_matrix.md     build_eligibility_handoff.md
    build_eligibility_report.md    fingerprints/<10 source fingerprints>
    recon_summary.md (this file)
