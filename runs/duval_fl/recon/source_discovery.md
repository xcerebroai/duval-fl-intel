# Source Discovery — Duval County, Florida (duval_fl)

Phase 0.A output. Candidate official sources discovered via web search.
Generated 2026-05-19. Framework v5.3.0.

Context: Duval County operates under a consolidated city-county government
(the City of Jacksonville). County constitutional officers — Clerk of Courts,
Tax Collector, Property Appraiser, Sheriff — remain distinct authorities;
municipal functions (code compliance, GIS) run under the City of Jacksonville.
Florida is a JUDICIAL foreclosure state.

Municipalities in Duval County: Jacksonville (consolidated), Jacksonville Beach,
Atlantic Beach, Neptune Beach, Baldwin.

---

## clerk_official_records

    name                 Duval County Clerk of Courts — Official Records Search
    official_url         https://or.duvalclerk.com/
    page_title           Duval County Public Records Search
    gov_or_aggregator    gov (Clerk of the Circuit Court & Comptroller)
    records_covered      Recorded instruments since 1988 — deeds, mortgages,
                         judgments, claims of lien, lis pendens, satisfactions,
                         federal/state tax liens, certificates of title/sale,
                         affidavits, and all statutorily recorded documents.
    discovered_via_query "Duval County Florida county clerk official records"

## clerk_core_court

    name                 Clerk Online Resource ePortal (CORE) — court case search
    official_url         https://core.duvalclerk.com/
    page_title           CORE - Clerk Online Resource ePortal
    gov_or_aggregator    gov (Clerk of the Circuit Court & Comptroller)
    records_covered      Circuit and county court case dockets — civil,
                         foreclosure, eviction, probate, family, criminal.
    discovered_via_query "Duval County clerk CORE ePortal court case search"

## foreclosure_auction

    name                 Duval County Foreclosure Sales (RealAuction)
    official_url         https://duval.realforeclose.com/
    page_title           Duval County Foreclosure Auctions
    gov_or_aggregator    gov-contracted vendor portal (RealAuction.com),
                         officially designated by the Clerk per Ch. 45 Fla. Stat.
    records_covered      Online foreclosure auction calendar — sale date, case
                         number, plaintiff, defendant, property address, final
                         judgment amount, opening bid, sale status.
    discovered_via_query "Duval County Florida foreclosure auction realforeclose"

## tax_deed_auction

    name                 Duval County Tax Deed Sales (RealAuction)
    official_url         https://duval.realtaxdeed.com/
    page_title           Duval County Tax Deed Auctions
    gov_or_aggregator    gov-contracted vendor portal (RealAuction.com),
                         designated by the Clerk per Ch. 197 Fla. Stat.
    records_covered      Tax deed auction calendar — sale date, parcel/RE number,
                         property address, opening bid, applicant, status.
                         Companion Clerk case search at taxdeed.duvalclerk.com.
    discovered_via_query "Duval County tax deed sale online auction"

## tax_certificate_sale

    name                 Duval County Tax Certificate Sale (LienHub)
    official_url         https://lienhub.com/county/duval
    page_title           Duval County Tax Certificate Sale — LienHub
    gov_or_aggregator    gov-contracted vendor portal (LienHub / RealAuction),
                         designated by the Tax Collector per Ch. 197 Fla. Stat.
    records_covered      Annual tax certificate (tax lien) auction — delinquent
                         parcels, face amount, advertised list, winning rates.
    discovered_via_query "Duval County tax certificate sale online auction"

## tax_collector

    name                 Duval County Tax Collector — Property Tax Search
    official_url         https://fl-duval-taxcollector.publicaccessnow.com/PropertyTaxSearch.aspx
    page_title           Property Tax Search — Fl-Duval-TaxCollector
    gov_or_aggregator    gov-contracted vendor portal (Grant Street Group),
                         linked from taxcollector.jacksonville.gov.
    records_covered      Per-account property tax bill, value, amount due, paid
                         status, delinquency status, account history.
    discovered_via_query "Duval County Tax Collector delinquent property tax search"

## code_enforcement

    name                 City of Jacksonville — Municipal Code Compliance Division
    official_url         https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance
    page_title           Jacksonville.gov - Municipal Code Compliance
    gov_or_aggregator    gov (City of Jacksonville)
    records_covered      Code compliance cases — property nuisance, unsafe
                         structures, minimum building standards, zoning, junk
                         vehicles. No public structured case-search portal
                         located; document access via Public Records Request.
    discovered_via_query "City of Jacksonville code enforcement open data"

## parcel_master

    name                 Duval County Property Appraiser — Property Search
    official_url         https://paopropertysearch.coj.net/Basic/Search.aspx
    page_title           Property Search — Duval County Property Appraiser
    gov_or_aggregator    gov (Duval County Property Appraiser)
    records_covered      Parcel master — RE number, owner, situs/mailing address,
                         land/building/market/assessed/taxable value, year built,
                         legal description, sales history. Annual NAL tax roll
                         available in bulk via Florida DOR data portal.
    discovered_via_query "Duval County Property Appraiser parcel data"

## gis_parcels

    name                 City of Jacksonville (JaxGIS) — Parcels ArcGIS REST
    official_url         https://maps.coj.net/coj/rest/services
    page_title           ArcGIS REST Services Directory (CityBiz/Parcels)
    gov_or_aggregator    gov (City of Jacksonville GIS)
    records_covered      Parcel geometry, parcel IDs, address points, land-use
                         layers. Public ArcGIS REST endpoint, server v11.1.
    discovered_via_query "City of Jacksonville Duval County GIS ArcGIS REST"

## dor_parcel_bulk

    name                 Florida Dept. of Revenue — Property Tax Data Portal
    official_url         https://floridarevenue.com/property/Pages/DataPortal.aspx
    page_title           Florida DOR — Property Tax Data Portal
    gov_or_aggregator    gov (State of Florida — Department of Revenue)
    records_covered      Statewide assessment roll (NAL/Name-Address-Legal) and
                         parcel GIS shapefiles, per-county, delivered annually by
                         each county property appraiser. Duval = county 16.
    discovered_via_query "Florida appraisal district / property assessor (state)"

---

## Aggregators identified and EXCLUDED (per §01.6)

The following surfaced in search and are explicitly out of scope — reseller /
SEO layers over official data, not the official record authority:

    duvalcountypropertyappraiser.org, floridapropertyappraiser.org,
    duvalcountycourt.us, duvalcountycourt.org, duvalcountycourts.org,
    duvalrecords.org, govbackgroundchecks.com, floridacourtrecords.us,
    taxnetusa.com, regrid.com, foreclosure.com, redfin.com, trulia.com,
    realtytrac.com, auction.com, propertyonion.com, countyoffice.org,
    duvalforeclosureauctions.com, netronline.com.
