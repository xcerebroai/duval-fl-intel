# Portal Fingerprints — Duval County, Florida (duval_fl)

Phase 0.C output. Portal vendor + architecture per §01.8.
Generated 2026-05-19. Framework v5.3.0.

Per-source machine-readable fingerprints: runs/duval_fl/recon/fingerprints/<source_id>.fingerprint.json

---

## clerk_official_records

    name              Clerk of Courts — Official Records Search
    vendor            Kofile / county-hosted official records portal
                      (or.duvalclerk.com); recognized FL clerk OR-search family
    detection_heuristics  *.duvalclerk.com subdomain; ASP.NET search form;
                      Grantor/Grantee + Doc Type + Book/Page + Instrument #
                      + Record Date + Consideration + Case # search fields
    architecture      server-rendered HTML with ASP.NET postback search form
    search_interface  form-based POST (ASP.NET WebForms)
    result_url_pattern  /Search/SearchResults (postback-driven result grid)
    detail_url_pattern  /Document/<instrument_or_book_page> document viewer
    scrape_difficulty MEDIUM — server-rendered, free, no CAPTCHA observed; a
                      one-time disclaimer/terms acceptance gate may need a
                      session cookie. Confirm during Build Mode fingerprinting.

## clerk_core_court

    name              CORE — Clerk Online Resource ePortal
    vendor            Clerk-hosted court case portal (core.duvalclerk.com)
    detection_heuristics  core.duvalclerk.com; case-number / party-name search;
                      public-access vs registered-account tiers
    architecture      server-rendered HTML / light SPA case search
    search_interface  form-based search (party name, case number, filing date)
    result_url_pattern  case-list result grid
    detail_url_pattern  /case/<case_number> docket detail
    scrape_difficulty MEDIUM — civil/foreclosure dockets public and free;
                      family/probate documents gated behind a free account.

## foreclosure_auction

    name              Duval County Foreclosure Sales
    vendor            RealAuction.com (duval.realforeclose.com)
    detection_heuristics  *.realforeclose.com; RealAuction calendar UI;
                      "Auction Calendar" / "Auction Sale List" views
    architecture      JS-rendered single-page auction calendar
    search_interface  vendor-proprietary calendar + per-date sale list
    result_url_pattern  /index.cfm?zaction=AUCTION&zmethod=...&AID=<auctionId>
    detail_url_pattern  per-auction-item modal / sale detail
    scrape_difficulty VERY_HIGH (recon-tool layer) — HTTP 403 to non-browser
                      clients; anti-bot/WAF headers. Publicly viewable in a
                      real browser. Recommended adapter: Playwright (Build Mode).

## tax_deed_auction

    name              Duval County Tax Deed Sales
    vendor            RealAuction.com (duval.realtaxdeed.com)
    detection_heuristics  *.realtaxdeed.com; identical RealAuction calendar UI
    architecture      JS-rendered single-page auction calendar
    search_interface  vendor-proprietary calendar + per-date sale list
    result_url_pattern  /index.cfm?zaction=AUCTION&...
    detail_url_pattern  per-item sale detail
    scrape_difficulty VERY_HIGH (recon-tool layer) — HTTP 403 to non-browser
                      clients; same RealAuction WAF. Browser-viewable.
                      Companion Clerk case search taxdeed.duvalclerk.com is
                      server-rendered (lower difficulty).

## tax_certificate_sale

    name              Duval County Tax Certificate Sale
    vendor            LienHub / RealAuction (lienhub.com/county/duval)
    detection_heuristics  lienhub.com county path; certificate-sale UI
    architecture      JS-rendered SPA; seasonal (auction live May–June)
    search_interface  vendor-proprietary; advertised-list export during sale
    result_url_pattern  /county/duval/certsale/...
    detail_url_pattern  per-certificate detail
    scrape_difficulty HIGH — seasonal availability; advertised delinquent list
                      published ~3–4 weeks before the June sale.

## tax_collector

    name              Tax Collector — Property Tax Search
    vendor            Grant Street Group ("publicaccessnow")
    detection_heuristics  *.publicaccessnow.com; PropertyTaxSearch.aspx
    architecture      server-rendered ASP.NET search
    search_interface  form-based search (name / address / account)
    result_url_pattern  /PropertyTaxSearch.aspx result list
    detail_url_pattern  per-account tax bill detail
    scrape_difficulty MEDIUM — free public per-account search; no bulk
                      delinquency list exposed (per-record only).

## code_enforcement

    name              Municipal Code Compliance
    vendor            none identified (department page on jacksonville.gov CMS)
    detection_heuristics  jacksonville.gov departmental CMS page
    architecture      static informational page; no record portal
    search_interface  none public — Public Records Request only
    result_url_pattern  n/a
    detail_url_pattern  n/a
    scrape_difficulty N/A — no public structured source to fingerprint.

## parcel_master

    name              Property Appraiser — Property Search
    vendor            county-hosted ASP.NET (paopropertysearch.coj.net)
    detection_heuristics  paopropertysearch.coj.net; Basic/Search.aspx;
                      Real Estate Number / Owner / Address search
    architecture      server-rendered ASP.NET WebForms
    search_interface  form-based POST
    result_url_pattern  /Basic/Detail.aspx?RE=<re_number>
    detail_url_pattern  /Basic/Detail.aspx?RE=<re_number>
    scrape_difficulty LOW–MEDIUM — server-rendered, free; bulk preferred via
                      DOR NAL file (see dor_parcel_bulk).

## gis_parcels

    name              JaxGIS — Parcels ArcGIS REST
    vendor            Esri ArcGIS Server 11.1 (maps.coj.net)
    detection_heuristics  /rest/services directory; ArcGIS f=pjson responses;
                      CityBiz/Parcels MapServer
    architecture      ArcGIS REST API (documented protocol)
    search_interface  REST API — query endpoints, f=json
    result_url_pattern  /coj/rest/services/CityBiz/Parcels/MapServer/<layer>/query
    detail_url_pattern  feature objectId query
    scrape_difficulty LOW — open documented ArcGIS REST API.

## dor_parcel_bulk

    name              Florida DOR — Property Tax Data Portal
    vendor            State of Florida DOR (floridarevenue.com)
    detection_heuristics  floridarevenue.com property data portal
    architecture      static download directory of per-county files
    search_interface  file download (NAL roll + parcel GIS shapefiles)
    result_url_pattern  per-county / per-year file links
    detail_url_pattern  n/a (bulk file)
    scrape_difficulty LOW — public bulk file download; annual cadence.
