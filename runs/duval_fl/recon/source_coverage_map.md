# Source Coverage Map — Duval County, Florida (duval_fl)

Recon coverage summary per §16.D. Generated 2026-05-19. Framework v5.3.0.

---

## Live sources (accessible now, no operator escalation)

    clerk_official_records   OR portal — recorded instruments since 1988.
                             OPEN_PUBLIC. The headline P0 primary lead source.
    clerk_core_court         CORE court portal — civil / foreclosure / eviction
                             dockets, public-access tier free. OPEN_PUBLIC.
    tax_collector            Per-account tax search, free public. OPEN_PUBLIC.
                             PER_RECORD_ONLY coverage constraint.
    tax_certificate_sale     Annual tax certificate auction (LienHub).
                             OPEN_PUBLIC but SEASONAL (May–June window).
    parcel_master            Property Appraiser parcel search. OPEN_PUBLIC.
    gis_parcels              JaxGIS ArcGIS REST API. OPEN_PUBLIC, documented API.
    dor_parcel_bulk          FL DOR bulk NAL roll + parcel GIS. OPEN_PUBLIC.

## Blocked sources (found, currently inaccessible)

    foreclosure_auction      duval.realforeclose.com — HTTP 403 / RealAuction
                             anti-bot WAF. TECHNICAL blocker. Browser-viewable;
                             resolvable in Build Mode via Playwright.
    tax_deed_auction         duval.realtaxdeed.com — same RealAuction WAF.
                             TECHNICAL blocker; resolvable in Build Mode.

## Limited-coverage sources

    tax_collector            PER_RECORD_ONLY — no bulk delinquent roll exposed;
                             coverage bounded by the externally-resolved parcel
                             set (parcels surfaced by clerk recordings, the
                             certificate sale list, etc.).
    tax_certificate_sale     SEASONAL — the advertised delinquent list publishes
                             ~3–4 weeks before the annual June sale; off-season
                             the portal shows prior-year results only.
    clerk_core_court         Probate and family dockets are restricted to a free
                             registered-account tier; civil/foreclosure/eviction
                             are fully public.

## Not-found lead types (no primary source located)

    (none — every applicable lead type has at least one candidate source)

## Operator-review-required

    code_enforcement         No public structured code-enforcement case-search
                             portal or dataset located on jacksonville.gov.
                             Operator must confirm whether a non-public portal
                             exists, or accept a manual-assisted / records-request
                             path. Recorded code LIENS remain reachable via
                             clerk_official_records, so code-lien leads are not
                             lost — only pre-lien code cases / demolition /
                             condemnation case data is affected.
    Sheriff Sale (lead type) In Florida, foreclosure sales are conducted by the
                             Clerk's online auction, not the sheriff. Sheriff
                             execution sales on money judgments are rare and have
                             no located public portal — operator review.
    Probate / Divorce        Free registered-account tier needed for enhanced
                             document access on CORE family/probate divisions.
    Bankruptcy               Federal (US Bankruptcy Court, M.D. Fla., Jacksonville
                             Division) — PACER, paid. Out of the county-source
                             scope; operator decides whether to fund PACER.
