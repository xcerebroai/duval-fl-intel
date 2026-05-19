# Source Role Classification — Duval County, Florida (duval_fl)

Phase 0.E output. Source role per §01.10, grounded in the §13 Lead Origination
Contract. Generated 2026-05-19. Framework v5.3.0.

Enum: PRIMARY_LEAD_SOURCE · SUPPORTING_LEAD_SOURCE · ENRICHMENT_SOURCE ·
REFERENCE_ONLY · REJECTED_SOURCE. Only PRIMARY_LEAD_SOURCE originates leads.

---

## clerk_official_records

    source_role          PRIMARY_LEAD_SOURCE
    rationale            Recorded instruments are dated, official distress /
                         encumbrance / legal-status events: lis pendens,
                         claims of lien, federal & state tax liens, recorded
                         judgments, certificates of title/sale, personal
                         representative's deeds, affidavits of heirship,
                         recorded code-enforcement liens. The single richest
                         primary event source in the county.
    section_13_reference §13.2 — clerk/recorder records, lis pendens, liens,
                         tax liens, judgments, estate records.

## clerk_core_court

    source_role          PRIMARY_LEAD_SOURCE
    rationale            Originates leads not visible in recorded instruments —
                         eviction filings and civil/foreclosure case dockets
                         (filing date, parties, cause of action). Also supports
                         foreclosure leads with case detail.
    section_13_reference §13.2 — court events: foreclosure, eviction, civil
                         judgments.

## foreclosure_auction

    source_role          PRIMARY_LEAD_SOURCE  (access currently BLOCKED)
    rationale            The official Ch. 45 foreclosure sale calendar — sale
                         date, case number, parties, judgment amount, status.
                         A primary event source; access is technically blocked
                         (RealAuction WAF), so it also carries BLOCKED_SOURCE
                         status in the SoR matrix candidate entry.
    section_13_reference §13.2 — foreclosure sales / auctions.

## tax_deed_auction

    source_role          PRIMARY_LEAD_SOURCE  (access currently BLOCKED)
    rationale            Ch. 197 tax deed sale calendar — delinquent parcels
                         advancing to auction. Primary event source; access
                         technically blocked (RealAuction WAF).
    section_13_reference §13.2 — tax sale / tax deed events.

## tax_certificate_sale

    source_role          PRIMARY_LEAD_SOURCE
    rationale            Annual delinquent-tax certificate auction — the
                         advertised list is the universe of tax-delinquent
                         parcels for the year. Primary tax-distress event source.
    section_13_reference §13.2 — tax lien / tax sale certificate events.

## tax_collector

    source_role          PRIMARY_LEAD_SOURCE
    rationale            Per-account tax records surface delinquency status — a
                         tax-distress event. Per-record access only; coverage
                         bounded by the externally-resolved parcel set.
    section_13_reference §13.2 — tax delinquency events.

## code_enforcement

    source_role          BLOCKED_SOURCE
    rationale            The Municipal Code Compliance Division is a legitimate
                         primary event authority (violations, unsafe structures,
                         demolition, condemnation), but no public structured
                         case-search portal or dataset was located. Found but
                         inaccessible. Recorded code LIENS remain reachable via
                         clerk_official_records, so code-lien leads are not lost.
    section_13_reference §13.2 — code liens / demolition / condemnation.

## parcel_master

    source_role          ENRICHMENT_SOURCE
    rationale            Property Appraiser parcel master — value, owner,
                         situs/mailing address, year built, legal, sales
                         history. Property STATE, not an event. Decorates leads;
                         never originates one.
    section_13_reference §13.3 — parcel / assessor / valuation data.

## gis_parcels

    source_role          ENRICHMENT_SOURCE
    rationale            Parcel geometry and address points. Geospatial
                         enrichment; supports matching and map deep-links.
    section_13_reference §13.3 — GIS / parcel geometry.

## dor_parcel_bulk

    source_role          ENRICHMENT_SOURCE
    rationale            State DOR bulk NAL assessment roll + parcel GIS — the
                         FULL_COUNTY_BULK enrichment index for parcel_master.
    section_13_reference §13.3 — assessor / tax-roll data.

---

## Excluded sources (REJECTED_SOURCE)

All third-party aggregators listed in source_discovery.md are REJECTED_SOURCE —
reseller / SEO layers over official data, not the record authority. Not built
against, not enriched from. Reason: failed §01.6 official-origin requirement.
