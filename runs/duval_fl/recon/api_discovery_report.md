# API Discovery Report — Duval County, Florida (duval_fl)

Phase 0 documented-API discovery per §01.23 / §16.D.
Generated 2026-05-19. Framework v5.3.0.

For each candidate source, documented APIs were searched before settling on
HTML scraping. Search locations checked: <domain>/api, /api/swagger, /swagger,
/docs, /api-docs; Postman public collections; GitHub; vendor documentation.

---

## Documented APIs FOUND

### gis_parcels — JaxGIS ArcGIS REST API

    api_url            https://maps.coj.net/coj/rest/services
    api_type           ArcGIS
    documentation_url  https://maps.coj.net/coj/rest/services?f=help
    auth_required      false
    rate_limited       unknown (standard ArcGIS Server throttling assumed)
    source_role        ENRICHMENT_SOURCE
    notes              Public ArcGIS Server 11.1 REST directory. 34 service
                       folders enumerated; CityBiz/Parcels/MapServer exposes a
                       Parcels layer queryable via the standard ArcGIS /query
                       endpoint (f=json, where, geometry, outFields). This is
                       the documented, stable enrichment-index API — preferred
                       over HTML scraping the Property Appraiser search.

### dor_parcel_bulk — Florida DOR bulk file directory

    api_url            https://floridarevenue.com/property/Pages/DataPortal.aspx
    api_type           Other (HTTP bulk file directory, not a query API)
    documentation_url  https://floridarevenue.com/property/Pages/DataPortal.aspx
    auth_required      false
    rate_limited       false
    source_role        ENRICHMENT_SOURCE
    notes              Per-county NAL assessment-roll files and parcel GIS
                       shapefiles, published annually. FULL_COUNTY_BULK
                       enrichment path. Not a programmatic API but a documented
                       public download surface.

---

## Documented APIs NOT FOUND (search log)

### clerk_official_records
    Searched: or.duvalclerk.com/api, /swagger, /docs, /api-docs; "duvalclerk
    api" on GitHub; Kofile/clerk-portal vendor docs. Documented API found: N.
    Falls back to the ASP.NET search form (server-rendered HTML).

### clerk_core_court
    Searched: core.duvalclerk.com/api, /swagger, /docs; Florida statewide
    e-portal API docs; GitHub "duvalclerk core api". Documented API found: N.
    Note: Florida courts have a statewide e-filing portal (myflcourtaccess.com)
    with no public read API. Falls back to CORE HTML case search.

### foreclosure_auction / tax_deed_auction
    Searched: realforeclose.com / realtaxdeed.com /api, /swagger; RealAuction
    developer docs; GitHub "realauction api". Documented API found: N.
    RealAuction exposes internal index.cfm?zaction= XHR endpoints that back the
    calendar UI; these are undocumented and behind the WAF. Build Mode should
    inspect network requests behind a browser session (Phase 0.5 strategy
    inspect_network_requests / discover_hidden_api) rather than assume an API.

### tax_certificate_sale
    Searched: lienhub.com/api, /docs; LienHub/RealAuction docs; GitHub.
    Documented API found: N. The advertised delinquent list is published as a
    downloadable file during the sale window — treat as a seasonal file export.

### tax_collector
    Searched: publicaccessnow.com/api, /swagger; Grant Street Group developer
    docs. Documented API found: N. Falls back to PropertyTaxSearch.aspx form.

### parcel_master
    Searched: paopropertysearch.coj.net/api, /swagger, /docs. Documented API
    found: N. Enrichment is better served by gis_parcels (ArcGIS API) and
    dor_parcel_bulk (NAL file) — see enrichment_index_strategy in the config.

### code_enforcement
    Searched: jacksonville.gov code-compliance pages, /api; ArcGIS COURT folder.
    Documented API found: N. No public code-enforcement query surface located.

---

## Summary

Documented APIs were found for the ENRICHMENT layer (ArcGIS parcels REST +
DOR bulk roll). No documented API was found for any PRIMARY lead source —
clerk records, court dockets, and the RealAuction calendars are all
HTML/portal-based. This does not block the build: the primary headline source
(clerk_official_records) is a server-rendered public search form, fully
buildable via HTML adapter. The RealAuction undocumented XHR endpoints are a
Build Mode investigation item, not a recon blocker.
