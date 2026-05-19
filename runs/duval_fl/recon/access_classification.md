# Access Classification — Duval County, Florida (duval_fl)

Phase 0.D output. Access tier per source per §01.9.
Generated 2026-05-19. Framework v5.3.0.

Canonical enum: OPEN_PUBLIC · SEARCH_ONLY_PUBLIC · FREE_ACCOUNT_REQUIRED ·
PAID_SUBSCRIPTION_REQUIRED · LOGIN_REQUIRED · CAPTCHA_PROTECTED ·
DOCUMENT_IMAGES_LOCKED · BLOCKED · UNKNOWN.

No forbidden action (§01.17) was taken: no accounts created, no CAPTCHA solved,
no proxy used, no access control bypassed, no records scraped. Classifications
rest on observed page behavior and HTTP responses only.

---

## clerk_official_records

    access_classification  OPEN_PUBLIC
    evidence               or.duvalclerk.com returned a public records search
                           page exposing Grantor/Grantee, Instrument #, Doc Type,
                           Record Date, Consideration, Book/Page and Case #
                           search fields. Clerk documentation states online
                           search and uncertified-copy viewing are free, with
                           records since 1988. A one-time terms/disclaimer
                           acceptance (session cookie) may precede searching.
    notes                  Florida official records are public by statute.
                           Treated OPEN_PUBLIC; the disclaimer-gate detail is an
                           open question for Build Mode fingerprinting, not a
                           buildability blocker.

## clerk_core_court

    access_classification  OPEN_PUBLIC (civil / foreclosure / eviction dockets)
    evidence               core.duvalclerk.com public-access tier returns civil
                           and criminal case dockets free of charge; searchable
                           by party name, case number, filing date.
    notes                  Probate and family dockets are restricted — see
                           probate_court below. This source_id covers the
                           public civil/foreclosure docket tier.

## foreclosure_auction

    access_classification  BLOCKED
    evidence               duval.realforeclose.com returned HTTP 403 Forbidden
                           to a non-browser client — RealAuction anti-bot/WAF
                           headers. The auction calendar is publicly viewable in
                           a standard browser without login (registration is
                           required only to BID, not to view).
    notes                  Blocker is TECHNICAL (anti-scrape WAF), not a
                           permission wall. Auto-resolve candidate (Phase 0.5);
                           resolves with a real browser engine in Build Mode.

## tax_deed_auction

    access_classification  BLOCKED
    evidence               duval.realtaxdeed.com returned HTTP 403 Forbidden to
                           a non-browser client — same RealAuction WAF.
                           Browser-viewable without login. The companion Clerk
                           case search taxdeed.duvalclerk.com is server-rendered
                           and not WAF-blocked.
    notes                  TECHNICAL blocker; auto-resolve candidate.

## tax_certificate_sale

    access_classification  OPEN_PUBLIC (seasonal)
    evidence               lienhub.com/county/duval hosts the annual certificate
                           sale; the advertised delinquent-parcel list and FAQ
                           are publicly viewable. The live auction runs
                           May–June; outside that window the portal shows prior
                           results and the upcoming-sale notice.
    notes                  Coverage is SEASONAL — buildable but cadence-bound to
                           the annual sale window. P1 source.

## tax_collector

    access_classification  OPEN_PUBLIC
    evidence               fl-duval-taxcollector.publicaccessnow.com property
                           tax search is a free public per-account lookup
                           (name / address / account); surfaces amount due and
                           delinquency status. No login or payment to search.
    notes                  Per-record only — no bulk delinquent roll exposed.
                           See bulk_availability in the SoR matrix.

## code_enforcement

    access_classification  UNKNOWN
    evidence               No public structured code-enforcement case-search
                           portal or downloadable dataset was located on
                           jacksonville.gov. The department page directs
                           document requests to a Public Records Request.
    notes                  Cannot be classified to a concrete access tier
                           without a portal to observe → UNKNOWN per §01.9.
                           Recorded code-enforcement LIENS remain reachable via
                           clerk_official_records.

## parcel_master

    access_classification  OPEN_PUBLIC
    evidence               paopropertysearch.coj.net/Basic/Search.aspx is a free
                           public property search (RE number / owner / address)
                           exposing value, owner, situs, legal, sales history.
    notes                  Enrichment source.

## gis_parcels

    access_classification  OPEN_PUBLIC
    evidence               maps.coj.net/coj/rest/services responded as a public
                           ArcGIS REST directory (server v11.1) with f=pjson;
                           CityBiz/Parcels MapServer is reachable.
    notes                  Open documented ArcGIS API. Enrichment source.

## dor_parcel_bulk

    access_classification  OPEN_PUBLIC
    evidence               floridarevenue.com property data portal publishes
                           per-county NAL assessment-roll files and parcel GIS
                           shapefiles for free public download; counties deliver
                           data to DOR by April 1 annually.
    notes                  Bulk enrichment path for parcel_master.
