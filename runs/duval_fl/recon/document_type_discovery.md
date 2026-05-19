# Document Type Discovery — Duval County, Florida (duval_fl)

Phase 0.F output. Document type taxonomy for accessible primary / supporting
lead sources, per §01.12. Metadata-only — no records scraped.
Generated 2026-05-19. Framework v5.3.0.

Cross-referenced against knowledge_base/domain/canonical_doc_types.json.

---

## clerk_official_records

    source_name                          Clerk of Courts — Official Records Search
    document_type_taxonomy_field_name    "Doc Type" (search-form dropdown)
    total_types_observed                 Florida official records use a broad
                                         recorded-instrument type list. The
                                         distress-relevant subset below was
                                         identified from Florida standard
                                         recording practice; the exact dropdown
                                         label strings are confirmed during
                                         Build Mode portal fingerprinting.
    types_mapped_to_canonical_primary    Lis Pendens -> LIS_PENDENS
                                         Notice of Sale -> NOTICE_OF_SALE
                                         Final Judgment -> FINAL_JUDGMENT_OF_FORECLOSURE
                                         Certificate of Title -> CERTIFICATE_OF_TITLE
                                         Certificate of Sale -> CERTIFICATE_OF_SALE
                                         Claim of Lien -> CONSTRUCTION_LIEN
                                         Federal Tax Lien -> FEDERAL_TAX_LIEN
                                         State Tax Lien / DOR Warrant -> STATE_TAX_LIEN
                                         Judgment / Final Judgment (money) -> JUDGMENT
                                         Tax Deed -> TAX_DEED
                                         Personal Representative Deed -> EXECUTORS_DEED
                                         Affidavit of Heirship -> AFFIDAVIT_OF_HEIRSHIP
                                         Code Enforcement Lien -> CODE_LIEN
                                         Quit Claim Deed -> QUITCLAIM_DEED
    types_mapped_to_canonical_enrichment Warranty Deed, Mortgage, Assignment of
                                         Mortgage (context only — not distress)
    types_unknown                        County-specific raw abbreviations and
                                         numeric doc codes (if any) — captured
                                         into doc_type_synonyms during Build Mode.
    recommended_primary_doc_types_for_build
                                         LIS_PENDENS, NOTICE_OF_SALE,
                                         FINAL_JUDGMENT_OF_FORECLOSURE,
                                         CERTIFICATE_OF_TITLE, CONSTRUCTION_LIEN,
                                         FEDERAL_TAX_LIEN, STATE_TAX_LIEN,
                                         JUDGMENT, TAX_DEED, EXECUTORS_DEED,
                                         AFFIDAVIT_OF_HEIRSHIP, CODE_LIEN.

## clerk_core_court

    source_name                          CORE — court case search
    document_type_taxonomy_field_name    Case type / division (Civil, County
                                         Civil, Foreclosure, Eviction, Probate,
                                         Family)
    total_types_observed                 Case-type divisions rather than
                                         document types. Distress-relevant:
                                         Foreclosure (Circuit Civil), Eviction
                                         (County Civil), Civil Judgment.
    types_mapped_to_canonical_primary    Mortgage Foreclosure case -> FORECLOSURE
                                         Eviction / Removal of Tenant -> EVICTION
                                         Civil money judgment -> JUDGMENT
    types_mapped_to_canonical_enrichment n/a (case dockets, not parcel metadata)
    types_unknown                        Internal CORE division codes — captured
                                         during Build Mode.
    recommended_primary_doc_types_for_build
                                         FORECLOSURE (case docket), EVICTION.

## tax_certificate_sale

    source_name                          Tax Certificate Sale (LienHub)
    document_type_taxonomy_field_name    n/a — the advertised delinquent-parcel
                                         list is a single record type
    total_types_observed                 1 (tax certificate / delinquent parcel)
    types_mapped_to_canonical_primary    Tax Certificate -> TAX_SALE_CERTIFICATE
    types_mapped_to_canonical_enrichment n/a
    types_unknown                        none
    recommended_primary_doc_types_for_build  TAX_SALE_CERTIFICATE.

## tax_collector

    source_name                          Tax Collector — Property Tax Search
    document_type_taxonomy_field_name    n/a — per-account tax record
    total_types_observed                 1 (delinquent tax account)
    types_mapped_to_canonical_primary    Delinquent tax account -> TAX_DELINQUENCY
    types_mapped_to_canonical_enrichment n/a
    types_unknown                        none
    recommended_primary_doc_types_for_build  TAX_DELINQUENCY.

---

## Sources NOT document-type-discovered (and why)

    foreclosure_auction   access BLOCKED (RealAuction WAF) — single record type
                          (foreclosure sale item); discovery deferred to Build
                          Mode once browser access is established.
    tax_deed_auction      access BLOCKED (RealAuction WAF) — single record type
                          (tax deed sale item); discovery deferred to Build Mode.
    code_enforcement      access UNKNOWN — no portal to inspect.
    parcel_master / gis_parcels / dor_parcel_bulk   ENRICHMENT_SOURCE — document
                          type discovery applies to lead sources only (§01.12).
