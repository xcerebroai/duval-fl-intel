# Source Verification — Duval County, Florida (duval_fl)

Phase 0.B output. Official-source verification layers per §01.7.
Generated 2026-05-19. Framework v5.3.0.

Layers: L1 government domain · L2 vendor portal check · L3 cross-reference
(linked from county .gov) · L4 records-authority check.
Rule: pass L1 OR (L2 AND L3), AND pass L4 → VERIFIED_OFFICIAL.

---

## clerk_official_records

    name                 Clerk of Courts — Official Records Search
    official_url         https://or.duvalclerk.com/
    layers_passed        L1 (duvalclerk.com is the official Clerk domain;
                         or.* is a Clerk subdomain), L3 (linked from
                         duvalclerk.com Official Records & Research page),
                         L4 (Clerk of the Circuit Court & Comptroller is the
                         statutory recorder of deeds in Florida).
    verification_status  VERIFIED_OFFICIAL
    notes                Confirmed via duvalclerk.com → "Official Records and
                         Research" → links to or.duvalclerk.com. Free public
                         search of recorded instruments since 1988.

## clerk_core_court

    name                 CORE — Clerk Online Resource ePortal
    official_url         https://core.duvalclerk.com/
    layers_passed        L1 (Clerk subdomain), L3 (linked from duvalclerk.com
                         court records & foreclosure pages), L4 (Clerk is the
                         custodian of circuit/county court case records).
    verification_status  VERIFIED_OFFICIAL
    notes                Official court case portal. Public-access tier is free
                         for civil/foreclosure/criminal dockets; family and
                         probate documents are restricted (free registered
                         account for enhanced access).

## foreclosure_auction

    name                 Duval County Foreclosure Sales (RealAuction)
    official_url         https://duval.realforeclose.com/
    layers_passed        L2 (RealAuction.com is a recognized government auction
                         vendor), L3 (duvalclerk.com Foreclosure page states
                         "foreclosure sales are held online at
                         www.duval.realforeclose.com"), L4 (Florida Clerks
                         conduct foreclosure sales per Ch. 45 Fla. Stat.).
    verification_status  VERIFIED_OFFICIAL
    notes                Officially designated foreclosure auction venue.
                         Vendor-hosted; verified by inbound link from the
                         Clerk's own .com foreclosure page.

## tax_deed_auction

    name                 Duval County Tax Deed Sales (RealAuction)
    official_url         https://duval.realtaxdeed.com/
    layers_passed        L2 (RealAuction vendor), L3 (duvalclerk.com Tax Deeds
                         page designates the auction site; companion Clerk case
                         search at taxdeed.duvalclerk.com), L4 (Clerk conducts
                         tax deed sales per Ch. 197 Fla. Stat.).
    verification_status  VERIFIED_OFFICIAL
    notes                Officially designated tax deed auction venue.

## tax_certificate_sale

    name                 Duval County Tax Certificate Sale (LienHub)
    official_url         https://lienhub.com/county/duval
    layers_passed        L2 (LienHub/RealAuction vendor), L3 (Tax Collector site
                         taxcollector.jacksonville.gov designates lienhub.com/duval
                         for the annual certificate sale), L4 (Tax Collector
                         conducts the certificate sale per Ch. 197 Fla. Stat.).
    verification_status  VERIFIED_OFFICIAL
    notes                Annual delinquent-tax certificate auction (May–June).

## tax_collector

    name                 Tax Collector — Property Tax Search
    official_url         https://fl-duval-taxcollector.publicaccessnow.com/PropertyTaxSearch.aspx
    layers_passed        L2 (Grant Street Group "publicaccessnow" is a recognized
                         tax-collector vendor), L3 (linked from
                         taxcollector.jacksonville.gov), L4 (Duval County Tax
                         Collector is the statutory tax authority).
    verification_status  VERIFIED_OFFICIAL
    notes                Per-account tax search; surfaces delinquency status.

## code_enforcement

    name                 City of Jacksonville — Municipal Code Compliance
    official_url         https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance
    layers_passed        L1 (jacksonville.gov is the official City domain),
                         L4 (Municipal Code Compliance Division is the city
                         code-enforcement authority). L3 n/a (own domain).
    verification_status  VERIFIED_OFFICIAL (authority) — but no public record
                         portal: see access_classification.md.
    notes                The DEPARTMENT is verified official; no public
                         structured case-search portal or dataset was located.
                         Recorded code-enforcement LIENS are separately
                         retrievable via clerk_official_records.

## parcel_master

    name                 Duval County Property Appraiser — Property Search
    official_url         https://paopropertysearch.coj.net/Basic/Search.aspx
    layers_passed        L1 (paopropertysearch.coj.net is a Property Appraiser
                         subdomain of the consolidated-government coj.net),
                         L3 (linked from jacksonville.gov Property Appraiser
                         dept page), L4 (Property Appraiser is the statutory
                         assessment authority).
    verification_status  VERIFIED_OFFICIAL
    notes                Official parcel master. Enrichment role.

## gis_parcels

    name                 JaxGIS — Parcels ArcGIS REST
    official_url         https://maps.coj.net/coj/rest/services
    layers_passed        L1 (maps.coj.net is the City of Jacksonville GIS host),
                         L3 (referenced from jacksonville.gov GIS dept page),
                         L4 (City GIS is the official geospatial authority).
    verification_status  VERIFIED_OFFICIAL
    notes                Public ArcGIS REST endpoint, server v11.1. Enrichment.

## dor_parcel_bulk

    name                 Florida DOR — Property Tax Data Portal
    official_url         https://floridarevenue.com/property/Pages/DataPortal.aspx
    layers_passed        L1 (floridarevenue.com is the official State of Florida
                         Department of Revenue domain), L4 (DOR is the statutory
                         custodian of county assessment-roll submissions).
    verification_status  VERIFIED_OFFICIAL
    notes                State portal hosting per-county NAL tax roll + parcel
                         GIS bulk files. Enrichment role; bulk path for
                         parcel_master.
