"""Phase 0 Step 4 — build the Duval County SoR matrix + populated county config.

Writes:
  runs/duval_fl/recon/source_of_record_matrix.json   (schema-validated matrix)
  config/counties/duval_fl.json                       (via write_county_config.py)

Per MASTER_PROMPT 4.28: the county config is written through
scaffold/ops/write_county_config.py, never a text-streaming writer.
"""
import copy
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scaffold.ops.write_county_config import write_county_config  # noqa: E402

GENERATED_AT = "2026-05-19T14:30:00Z"
FRAMEWORK_VERSION = "v5.3.0"

template = json.loads((REPO / "config/counties/_template.json").read_text())
SRC_BASE = template["sources"]["clerk_recordings"]      # full proof-packet skeleton
PARCEL_BASE = template["sources"]["parcel_master"]      # skeleton w/ canonical fields map


def src(**over):
    """Build a source block from the canonical clerk_recordings skeleton."""
    s = copy.deepcopy(SRC_BASE)
    s.update(over)
    return s


def parcel_src(**over):
    s = copy.deepcopy(PARCEL_BASE)
    s.update(over)
    return s


# ---------------------------------------------------------------- sources
sources = {}

sources["clerk_official_records"] = src(
    category="lead", subtype="clerk_recordings",
    url="https://or.duvalclerk.com/",
    access_pattern="static_html",
    scraper_module="scrapers/clerk_official_records.py",
    translator="publicsearch_clerk_recordings",
    refresh_cadence="daily", ttl_days=1095,
    source_reliability_grade="A", source_priority="P0",
    build_priority="mvp_required",
    official_status="OFFICIAL_COUNTY", lead_value="LEAD_GENERATING",
    source_freshness="DAILY", auth_required=False, rate_limit_rpm=60,
    enabled=True, allowed_to_export=True,
    last_verified_at=GENERATED_AT,
    verified_from_url="https://www.duvalclerk.com/departments/county-services/official-records-and-research",
    verification_method="official_page_link",
    official_entity="Duval County Clerk of the Circuit Court & Comptroller",
    portal_type="land records / official records search",
    records_available=["deeds", "mortgages", "lis_pendens", "liens",
                       "claims_of_lien", "federal_tax_liens", "state_tax_liens",
                       "judgments", "certificates_of_title", "tax_deeds",
                       "affidavits", "satisfactions"],
    search_fields=["grantor_grantee_name", "instrument_number", "document_type",
                   "record_date", "consideration", "book_page", "case_number"],
    access_method="SEARCHABLE_PUBLIC_PORTAL",
    public_access_status="FULL_PUBLIC_ACCESS",
    document_access_status="DOCUMENTS_PUBLIC",
    source_role="PRIMARY_LEAD_SOURCE",
    verification_confidence="HIGH",
    verification_note="or.duvalclerk.com reached and confirmed as a free public "
        "official records search; records since 1988. Search fields confirmed: "
        "Grantor/Grantee, Instrument #, Doc Type, Record Date, Consideration, "
        "Book/Page, Case #. Linked from the Clerk's official Official Records & "
        "Research page. Headline P0 primary lead source.",
    open_questions=["Confirm whether a one-time terms/disclaimer acceptance "
                    "(session cookie) precedes searching, and capture the exact "
                    "document-type dropdown strings during Build Mode "
                    "fingerprinting."],
    sample_record_path_confirmed=True, sample_record_type="search_form",
    sample_search_possible=True, sample_document_view_possible=True,
    estimated_cost_category="FREE",
    portal_family="Custom county clerk recorder portal",
    expected_refresh_cadence="DAILY", stale_after_hours=48,
    source_freshness_status="UNKNOWN", record_ttl_days=1095,
    stale_record_policy="KEEP_UNTIL_RELEASED",
    auto_resolve_status="NOT_ATTEMPTED",
    notes="Primary recorder source. Originates foreclosure (lis pendens), all "
          "lien types, judgments, federal/state tax liens, tax deeds, personal "
          "representative deeds, affidavits of heirship, and recorded code liens.",
)

sources["clerk_core_court"] = src(
    category="lead", subtype="court_civil",
    url="https://core.duvalclerk.com/",
    access_pattern="static_html",
    scraper_module="scrapers/clerk_core_court.py",
    translator="", refresh_cadence="daily", ttl_days=1095,
    source_reliability_grade="A", source_priority="P0",
    build_priority="high_value",
    official_status="OFFICIAL_COUNTY", lead_value="LEAD_GENERATING",
    source_freshness="DAILY", auth_required=False, rate_limit_rpm=60,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://www.duvalclerk.com/online-option/court-records",
    verification_method="official_page_link",
    official_entity="Duval County Clerk of the Circuit Court & Comptroller",
    portal_type="court case docket search (CORE ePortal)",
    records_available=["foreclosure_cases", "civil_cases", "eviction_cases",
                       "probate_cases", "family_cases", "judgments"],
    search_fields=["party_name", "case_number", "filing_date", "case_type"],
    access_method="SEARCHABLE_PUBLIC_PORTAL",
    public_access_status="PUBLIC_SEARCH_ONLY",
    document_access_status="DOCUMENTS_PUBLIC",
    source_role="PRIMARY_LEAD_SOURCE",
    verification_confidence="HIGH",
    verification_note="core.duvalclerk.com confirmed as the Clerk's official "
        "court case portal. Public-access tier free for civil / foreclosure / "
        "eviction dockets. Probate and family DOCUMENTS require a free "
        "registered account (docket index still publicly searchable).",
    open_questions=["Decide whether to register the free enhanced-access "
                    "account for probate/family document retrieval."],
    sample_record_path_confirmed=True, sample_record_type="search_form",
    sample_search_possible=True, sample_document_view_possible=True,
    estimated_cost_category="FREE",
    portal_family="Custom county clerk court portal",
    expected_refresh_cadence="DAILY", stale_after_hours=48,
    source_freshness_status="UNKNOWN", auto_resolve_status="NOT_ATTEMPTED",
    notes="Originates eviction and foreclosure-docket leads; supports "
          "foreclosure leads with case detail. Probate/family access-limited.",
)

PHASE05_AT = "2026-05-19T14:25:00Z"
REALAUCTION_ATTEMPTS = [
    {"attempt_order": 1, "timestamp": PHASE05_AT,
     "blocker_type": "TECHNICAL_BLOCKER",
     "strategy": "find_official_vendor_link", "status": "SUCCESS",
     "result": "Official designation confirmed — duvalclerk.com links this "
               "RealAuction portal as the designated auction venue.",
     "next_step": "Portal confirmed correct; remaining work is WAF access."},
    {"attempt_order": 2, "timestamp": PHASE05_AT,
     "blocker_type": "TECHNICAL_BLOCKER",
     "strategy": "discover_public_search_endpoint", "status": "FAILED",
     "result": "The RealAuction calendar IS the search endpoint, but it sits "
               "behind the anti-bot WAF (HTTP 403 to non-browser clients).",
     "next_step": "Escalate to a browser-engine strategy."},
    {"attempt_order": 3, "timestamp": PHASE05_AT,
     "blocker_type": "TECHNICAL_BLOCKER",
     "strategy": "inspect_network_requests", "status": "PENDING",
     "result": "RealAuction index.cfm?zaction= XHR endpoints exist but require "
               "a browser session to observe; recon is metadata-only (protocol "
               "01.17 forbids access-control bypass during recon).",
     "next_step": "Deferred to Build Mode."},
    {"attempt_order": 4, "timestamp": PHASE05_AT,
     "blocker_type": "TECHNICAL_BLOCKER",
     "strategy": "use_playwright", "status": "PENDING",
     "result": "A real browser engine resolves the WAF — a Build Mode "
               "capability. FREE cost, no operator approval required.",
     "next_step": "Resolve in Build Mode via Playwright."},
]

sources["foreclosure_auction"] = src(
    category="lead", subtype="sheriff_sales",
    url="https://duval.realforeclose.com/",
    access_pattern="waf_imperva",
    scraper_module="scrapers/foreclosure_auction.py",
    translator="", refresh_cadence="daily", ttl_days=120,
    source_reliability_grade="A", source_priority="P0",
    build_priority="high_value",
    official_status="OFFICIAL_VENDOR_PORTAL", lead_value="LEAD_GENERATING",
    source_freshness="DAILY", auth_required=False, rate_limit_rpm=30,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    blocked_unblock_paths=["seeded_session", "stealth_browser"],
    verified_from_url="https://www.duvalclerk.com/departments/civil-court-services/foreclosure",
    verification_method="official_vendor_link",
    official_entity="Duval County Clerk of Courts (RealAuction.com vendor)",
    portal_type="online foreclosure auction calendar (Ch. 45 Fla. Stat.)",
    records_available=["foreclosure_sales", "auction_calendar", "sale_status"],
    search_fields=["sale_date", "case_number", "parcel_id"],
    access_method="PUBLIC_BUT_WAF_PROTECTED",
    public_access_status="WAF_PROTECTED",
    document_access_status="DOCUMENTS_UNKNOWN",
    source_role="BLOCKED_SOURCE",
    verification_confidence="BLOCKED",
    verification_note="duval.realforeclose.com returned HTTP 403 to a "
        "non-browser client (RealAuction anti-bot WAF). Officially designated "
        "by the Clerk's foreclosure page. Calendar is publicly viewable in a "
        "standard browser without login.",
    open_questions=["Build Mode: confirm the RealAuction calendar XHR endpoints "
                    "and per-sale field set behind a browser session."],
    sample_record_path_confirmed=True, sample_record_type="auction_calendar",
    sample_search_possible=False, sample_document_view_possible=False,
    blocker="RealAuction anti-bot WAF — HTTP 403 to non-browser clients.",
    next_access_strategy="use_playwright",
    blocker_type="TECHNICAL_BLOCKER",
    auto_resolve_status="PARTIALLY_RESOLVED",
    final_resolution_status="PARTIALLY_RESOLVED",
    auto_resolve_attempts=copy.deepcopy(REALAUCTION_ATTEMPTS),
    estimated_cost_category="FREE",
    portal_family="RealAuction foreclosure auction portal",
    recommended_adapter="scrapers/foreclosure_auction_playwright.py",
    expected_refresh_cadence="DAILY", stale_after_hours=48,
    source_freshness_status="UNKNOWN", record_ttl_days=120,
    stale_record_policy="EXPIRE_IF_NOT_SEEN",
    notes="Foreclosure sale calendar. Foreclosure leads do not depend on it — "
          "lis pendens and final judgments are LIVE via clerk_official_records.",
)

sources["tax_deed_auction"] = src(
    category="lead", subtype="tax_certificates",
    url="https://duval.realtaxdeed.com/",
    access_pattern="waf_imperva",
    scraper_module="scrapers/tax_deed_auction.py",
    translator="", refresh_cadence="weekly", ttl_days=120,
    source_reliability_grade="A", source_priority="P1",
    build_priority="optional",
    official_status="OFFICIAL_VENDOR_PORTAL", lead_value="LEAD_GENERATING",
    source_freshness="WEEKLY", auth_required=False, rate_limit_rpm=30,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    blocked_unblock_paths=["seeded_session", "stealth_browser"],
    verified_from_url="https://www.duvalclerk.com/departments/county-services/tax-deed-files",
    verification_method="official_vendor_link",
    official_entity="Duval County Clerk of Courts (RealAuction.com vendor)",
    portal_type="online tax deed auction calendar (Ch. 197 Fla. Stat.)",
    records_available=["tax_deed_sales", "auction_calendar"],
    search_fields=["sale_date", "parcel_id", "applicant"],
    access_method="PUBLIC_BUT_WAF_PROTECTED",
    public_access_status="WAF_PROTECTED",
    document_access_status="DOCUMENTS_UNKNOWN",
    source_role="BLOCKED_SOURCE",
    verification_confidence="BLOCKED",
    verification_note="duval.realtaxdeed.com returned HTTP 403 to a non-browser "
        "client (same RealAuction WAF). Companion Clerk case search "
        "taxdeed.duvalclerk.com is server-rendered. Browser-viewable.",
    open_questions=["Build Mode: resolve the RealAuction WAF via Playwright."],
    sample_record_path_confirmed=True, sample_record_type="auction_calendar",
    sample_search_possible=False, sample_document_view_possible=False,
    blocker="RealAuction anti-bot WAF — HTTP 403 to non-browser clients.",
    next_access_strategy="use_playwright",
    blocker_type="TECHNICAL_BLOCKER",
    auto_resolve_status="PARTIALLY_RESOLVED",
    final_resolution_status="PARTIALLY_RESOLVED",
    auto_resolve_attempts=copy.deepcopy(REALAUCTION_ATTEMPTS),
    estimated_cost_category="FREE",
    portal_family="RealAuction tax deed auction portal",
    recommended_adapter="scrapers/tax_deed_auction_playwright.py",
    expected_refresh_cadence="WEEKLY", stale_after_hours=240,
    source_freshness_status="UNKNOWN", record_ttl_days=120,
    stale_record_policy="EXPIRE_IF_NOT_SEEN",
    notes="Tax deed sale calendar. Recorded TAX_DEED instruments are LIVE via "
          "clerk_official_records — post-sale coverage is not lost.",
)

sources["tax_certificate_sale"] = src(
    category="lead", subtype="tax_certificates",
    url="https://lienhub.com/county/duval",
    access_pattern="spa_with_api",
    scraper_module="scrapers/tax_certificate_sale.py",
    translator="", refresh_cadence="on_demand", ttl_days=400,
    source_reliability_grade="B", source_priority="P1",
    build_priority="optional",
    official_status="OFFICIAL_VENDOR_PORTAL", lead_value="LEAD_GENERATING",
    source_freshness="ANNUAL", auth_required=False, rate_limit_rpm=30,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://taxcollector.jacksonville.gov/taxes/property-taxes/tax-sale,-certificates,-and-tax-deeds",
    verification_method="official_vendor_link",
    official_entity="Duval County Tax Collector (LienHub / RealAuction vendor)",
    portal_type="annual tax certificate (tax lien) auction",
    records_available=["tax_certificates", "advertised_delinquent_list"],
    search_fields=["parcel_id", "certificate_number", "owner_name"],
    access_method="SEARCHABLE_PUBLIC_PORTAL",
    public_access_status="PUBLIC_SEARCH_ONLY",
    document_access_status="DOCUMENTS_PUBLIC",
    source_role="PRIMARY_LEAD_SOURCE",
    verification_confidence="MEDIUM",
    verification_note="lienhub.com/county/duval hosts the official annual tax "
        "certificate sale, designated by the Tax Collector. The advertised "
        "delinquent-parcel list and FAQ are publicly viewable. SEASONAL: the "
        "live auction runs May–June.",
    open_questions=["Confirm the advertised-list export format and the exact "
                    "publication date each year (~3-4 weeks before the sale)."],
    sample_record_path_confirmed=True, sample_record_type="auction_list",
    sample_search_possible=True, sample_document_view_possible=True,
    estimated_cost_category="FREE",
    portal_family="LienHub tax certificate sale portal",
    expected_refresh_cadence="MANUAL", stale_after_hours=8760,
    source_freshness_status="UNKNOWN", record_ttl_days=400,
    stale_record_policy="EXPIRE_AFTER_TTL",
    known_limitations=["Seasonal — advertised list publishes ~3-4 weeks before "
                       "the annual June sale; off-season shows prior results."],
    auto_resolve_status="NOT_ATTEMPTED",
    notes="Annual delinquent-tax certificate auction. The advertised list is "
          "the full county tax-delinquent parcel set for the year.",
)

sources["tax_collector"] = src(
    category="lead", subtype="tax_delinquency",
    url="https://fl-duval-taxcollector.publicaccessnow.com/PropertyTaxSearch.aspx",
    access_pattern="static_html",
    scraper_module="scrapers/tax_collector.py",
    translator="", refresh_cadence="daily", ttl_days=400,
    source_reliability_grade="A", source_priority="P1",
    build_priority="high_value",
    official_status="OFFICIAL_VENDOR_PORTAL", lead_value="LEAD_GENERATING",
    source_freshness="DAILY", auth_required=False, rate_limit_rpm=60,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://taxcollector.jacksonville.gov/",
    verification_method="official_vendor_link",
    official_entity="Duval County Tax Collector (Grant Street Group vendor)",
    portal_type="per-account property tax search / delinquency lookup",
    records_available=["tax_accounts", "delinquency_status", "amount_due"],
    search_fields=["owner_name", "property_address", "account_number"],
    access_method="SEARCHABLE_PUBLIC_PORTAL",
    public_access_status="FULL_PUBLIC_ACCESS",
    document_access_status="DOCUMENTS_PUBLIC",
    source_role="PRIMARY_LEAD_SOURCE",
    verification_confidence="HIGH",
    verification_note="fl-duval-taxcollector.publicaccessnow.com is the Tax "
        "Collector's free public per-account search; surfaces amount due and "
        "delinquency status. No login or payment to search.",
    open_questions=["No bulk delinquent roll is exposed — confirm whether the "
                    "Tax Collector will provide a delinquency extract, else "
                    "coverage stays bounded to the resolved parcel set."],
    sample_record_path_confirmed=True, sample_record_type="search_form",
    sample_search_possible=True, sample_document_view_possible=True,
    estimated_cost_category="FREE",
    portal_family="Grant Street Group tax portal",
    expected_refresh_cadence="DAILY", stale_after_hours=72,
    source_freshness_status="UNKNOWN",
    known_limitations=["PER_RECORD_ONLY — no bulk delinquent roll; coverage "
                       "bounded by the externally-resolved parcel set."],
    auto_resolve_status="NOT_ATTEMPTED",
    notes="Per-account tax delinquency lookup. The annual certificate sale "
          "(tax_certificate_sale) provides the bulk delinquent universe.",
)

sources["code_enforcement"] = src(
    category="lead", subtype="code_enforcement",
    url="https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance",
    access_pattern="public_records_only",
    scraper_module="scrapers/code_enforcement.py",
    translator="", refresh_cadence="on_demand", ttl_days=365,
    source_reliability_grade="C", source_priority="P1",
    build_priority="future",
    official_status="OFFICIAL_CITY", lead_value="UNKNOWN",
    source_freshness="ON_REQUEST", auth_required=False, rate_limit_rpm=None,
    enabled=False, paused_reason="No public structured case-search portal "
        "located — operator review required before building.",
    allowed_to_export=False, last_verified_at=GENERATED_AT,
    blocked_unblock_paths=["public_records", "manual_pull"],
    verified_from_url="https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance",
    verification_method="official_domain",
    official_entity="City of Jacksonville — Municipal Code Compliance Division",
    portal_type="code-enforcement department page (no public record portal)",
    records_available=[],
    search_fields=[],
    access_method="REQUEST_ONLY",
    public_access_status="REQUEST_ONLY",
    document_access_status="DOCUMENTS_NOT_AVAILABLE",
    source_role="BLOCKED_SOURCE",
    verification_confidence="LOW",
    verification_note="The Municipal Code Compliance Division is a verified "
        "official authority, but no public structured code-enforcement "
        "case-search portal or downloadable dataset was located. Document "
        "access is via Public Records Request. Recorded code-enforcement LIENS "
        "remain reachable via clerk_official_records.",
    open_questions=["Operator: does a non-public code-enforcement case portal "
                    "exist? If not, accept a manual-assisted / records-request "
                    "ingestion path, or rely on recorded code liens via OR."],
    sample_record_path_confirmed=False, sample_record_type="",
    sample_search_possible=False, sample_document_view_possible=False,
    blocker="No public structured code-enforcement case-search portal located.",
    next_access_strategy="manual_operator_assisted_pull",
    blocker_type="PUBLIC_ACCESS_UNCLEAR",
    auto_resolve_status="REQUIRES_OPERATOR_APPROVAL",
    final_resolution_status="OPERATOR_REQUIRED",
    auto_resolve_attempts=[
        {"attempt_order": 1, "timestamp": PHASE05_AT,
         "blocker_type": "PUBLIC_ACCESS_UNCLEAR",
         "strategy": "find_official_vendor_link", "status": "FAILED",
         "result": "No code-enforcement vendor portal (Accela / EnerGov / "
                   "Cityworks) is linked from jacksonville.gov.",
         "next_step": "Try a direct public search endpoint."},
        {"attempt_order": 2, "timestamp": PHASE05_AT,
         "blocker_type": "PUBLIC_ACCESS_UNCLEAR",
         "strategy": "discover_public_search_endpoint", "status": "FAILED",
         "result": "No public code-enforcement case-search endpoint located; "
                   "the department page directs to a Public Records Request.",
         "next_step": "Operator review — confirm a non-public portal or accept "
                      "a manual / records-request path."},
        {"attempt_order": 3, "timestamp": PHASE05_AT,
         "blocker_type": "PUBLIC_ACCESS_UNCLEAR",
         "strategy": "manual_operator_assisted_pull", "status":
         "REQUIRES_OPERATOR_APPROVAL",
         "result": "A manual-assisted pull or records-request channel is the "
                   "remaining path; requires operator decision.",
         "next_step": "Await operator decision (low priority — recorded code "
                      "liens are already LIVE via clerk_official_records)."},
    ],
    estimated_cost_category="UNKNOWN",
    expected_refresh_cadence="REQUEST_BASED", stale_after_hours=None,
    source_freshness_status="UNKNOWN",
    notes="Demolition / condemnation / pre-lien code cases depend on this "
          "source. Recorded code LIENS are independently LIVE via "
          "clerk_official_records, so code-lien leads are not lost.",
)

sources["parcel_master"] = parcel_src(
    category="enrichment", subtype="parcel_master",
    url="https://paopropertysearch.coj.net/Basic/Search.aspx",
    access_pattern="static_html",
    scraper_module="scrapers/parcel_master.py",
    translator="parcel_master", refresh_cadence="weekly", ttl_days=9999,
    source_reliability_grade="B", source_priority="P2",
    build_priority="enrichment",
    official_status="OFFICIAL_COUNTY", lead_value="ENRICHMENT",
    source_freshness="WEEKLY", auth_required=False, rate_limit_rpm=60,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://www.jacksonville.gov/departments/property-appraiser",
    verification_method="official_page_link",
    official_entity="Duval County Property Appraiser",
    portal_type="parcel master / property record search",
    records_available=["parcel_records", "ownership", "valuation",
                       "sales_history", "legal_description"],
    search_fields=["real_estate_number", "owner_name", "property_address"],
    access_method="SEARCHABLE_PUBLIC_PORTAL",
    public_access_status="FULL_PUBLIC_ACCESS",
    document_access_status="DOCUMENTS_PUBLIC",
    source_role="ENRICHMENT_SOURCE",
    verification_confidence="HIGH",
    verification_note="paopropertysearch.coj.net is the official Property "
        "Appraiser parcel search (free public). Bulk path available via "
        "dor_parcel_bulk (FL DOR NAL roll).",
    open_questions=["Decide enrichment ingestion: per-record portal scrape vs "
                    "DOR bulk NAL file vs JaxGIS ArcGIS query (recommended: "
                    "ArcGIS for index + DOR NAL for attributes)."],
    sample_record_path_confirmed=True, sample_record_type="search_form",
    sample_search_possible=True, sample_document_view_possible=True,
    estimated_cost_category="FREE",
    portal_family="Custom property appraiser portal",
    expected_refresh_cadence="WEEKLY", stale_after_hours=336,
    source_freshness_status="UNKNOWN", auto_resolve_status="NOT_ATTEMPTED",
    notes="Enrichment only. Never originates a lead (13.4.1).",
)

sources["gis_parcels"] = src(
    category="enrichment", subtype="gis_parcels",
    url="https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer",
    access_pattern="open_api",
    scraper_module="scrapers/gis_parcels.py",
    translator="", refresh_cadence="monthly", ttl_days=9999,
    source_reliability_grade="B", source_priority="P2",
    build_priority="enrichment",
    official_status="OFFICIAL_CITY", lead_value="ENRICHMENT",
    source_freshness="MONTHLY", auth_required=False, rate_limit_rpm=120,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://www.jacksonville.gov/departments/finance/information-technologies/geographic-information-systems-(gis)",
    verification_method="official_page_link",
    official_entity="City of Jacksonville — Geographic Information Systems",
    portal_type="ArcGIS REST parcel feature service",
    records_available=["parcel_geometry", "parcel_ids", "address_points"],
    search_fields=["objectid", "parcel_id", "geometry", "where_clause"],
    access_method="API_ENDPOINT",
    public_access_status="FULL_PUBLIC_ACCESS",
    document_access_status="DOCUMENTS_NOT_AVAILABLE",
    source_role="ENRICHMENT_SOURCE",
    verification_confidence="HIGH",
    verification_note="maps.coj.net ArcGIS REST endpoint confirmed public "
        "(server v11.1); CityBiz/Parcels/MapServer Parcels layer queryable via "
        "the standard /query endpoint. Documented enrichment-index API.",
    open_questions=[],
    sample_record_path_confirmed=True, sample_record_type="api_endpoint",
    sample_search_possible=True, sample_document_view_possible=False,
    estimated_cost_category="FREE",
    portal_family="ArcGIS REST feature services",
    recommended_adapter="scrapers/gis_parcels_arcgis.py",
    expected_refresh_cadence="MONTHLY", stale_after_hours=1440,
    source_freshness_status="UNKNOWN", auto_resolve_status="NOT_ATTEMPTED",
    notes="Enrichment only — parcel geometry and the enrichment index.",
)

sources["dor_parcel_bulk"] = src(
    category="enrichment", subtype="parcel_master",
    url="https://floridarevenue.com/property/Pages/DataPortal.aspx",
    access_pattern="static_html",
    scraper_module="scrapers/dor_parcel_bulk.py",
    translator="", refresh_cadence="on_demand", ttl_days=9999,
    source_reliability_grade="B", source_priority="P2",
    build_priority="enrichment",
    official_status="OFFICIAL_STATE", lead_value="ENRICHMENT",
    source_freshness="ANNUAL", auth_required=False, rate_limit_rpm=None,
    enabled=True, allowed_to_export=True, last_verified_at=GENERATED_AT,
    verified_from_url="https://floridarevenue.com/property/Pages/DataPortal.aspx",
    verification_method="state_portal",
    official_entity="Florida Department of Revenue — Property Tax Oversight",
    portal_type="bulk assessment-roll (NAL) + parcel GIS download portal",
    records_available=["nal_assessment_roll", "parcel_gis_shapefiles",
                       "sales_files"],
    search_fields=["county", "roll_year"],
    access_method="DOWNLOADABLE_FILE",
    public_access_status="FULL_PUBLIC_ACCESS",
    document_access_status="DOCUMENTS_NOT_AVAILABLE",
    source_role="ENRICHMENT_SOURCE",
    verification_confidence="HIGH",
    verification_note="floridarevenue.com property data portal publishes "
        "per-county NAL assessment rolls and parcel GIS shapefiles for free "
        "public download; counties deliver data to DOR by April 1 annually. "
        "Duval = DOR county 16. FULL_COUNTY_BULK enrichment path.",
    open_questions=[],
    sample_record_path_confirmed=True, sample_record_type="pdf_index",
    sample_search_possible=True, sample_document_view_possible=False,
    estimated_cost_category="FREE",
    portal_family="FL DOR property tax data portal",
    expected_refresh_cadence="MANUAL", stale_after_hours=8760,
    source_freshness_status="UNKNOWN", auto_resolve_status="NOT_ATTEMPTED",
    notes="Enrichment only — the FULL_COUNTY_BULK NAL roll backing parcel_master.",
)

# ---------------------------------------------------- Source-of-Record Matrix
def cs(source_id, url, authority, role, access, bulk, *,
       relevance="PASS", extract="PASS", refresh="PASS",
       path=True, docview=False, fields=None, notes=""):
    return {
        "source_id": source_id, "official_url": url,
        "authority_type": authority, "source_role": role,
        "access_status": access, "bulk_availability": bulk,
        "verification_layers": {
            "authority": "PASS",
            "lead_type_relevance": relevance,
            "access": "PASS" if access in ("OPEN_PUBLIC", "SEARCH_ONLY_PUBLIC")
                      else "BLOCKED" if access == "BLOCKED" else "PARTIAL",
            "extractability": extract,
            "refresh_provenance": refresh,
        },
        "sample_record_path_confirmed": path,
        "sample_document_view_possible": docview,
        "minimum_lead_fields_available": fields or [
            "property_address", "party_name", "event_date",
            "instrument_or_case_number"],
        "operator_verified": False,
        "notes": notes,
    }


OR_URL = "https://or.duvalclerk.com/"
CORE_URL = "https://core.duvalclerk.com/"
FA_URL = "https://duval.realforeclose.com/"
TDA_URL = "https://duval.realtaxdeed.com/"
TCS_URL = "https://lienhub.com/county/duval"
TC_URL = "https://fl-duval-taxcollector.publicaccessnow.com/PropertyTaxSearch.aspx"
CE_URL = "https://www.jacksonville.gov/departments/neighborhoods/municipal-code-compliance"

C_OR = lambda notes="": cs("clerk_official_records", OR_URL,
    "County Clerk / Recorder", "PRIMARY_EVENT_SOURCE", "OPEN_PUBLIC",
    "BATCH_QUERY", docview=True, notes=notes)
C_CORE = lambda access="OPEN_PUBLIC", notes="": cs("clerk_core_court", CORE_URL,
    "County Clerk / Circuit Court", "PRIMARY_EVENT_SOURCE", access,
    "BATCH_QUERY", docview=(access == "OPEN_PUBLIC"), notes=notes)


def lt(name, applicability, authorities, candidates, selected, status, notes):
    return {
        "lead_type": name, "state_applicability": applicability,
        "expected_authorities": authorities, "candidate_sources": candidates,
        "selected_source_id": selected, "status": status,
        "coverage_notes": notes,
    }


NA = "NOT_APPLICABLE_IN_STATE"
lead_types = [
    lt("Foreclosure", "APPLICABLE",
       ["County Clerk", "Circuit Court", "Clerk foreclosure auction"],
       [C_OR("Lis pendens, notice of sale, final judgment, certificate of "
             "title recorded here."),
        C_CORE(notes="Foreclosure case docket."),
        cs("foreclosure_auction", FA_URL, "Clerk foreclosure auction",
           "BLOCKED_SOURCE", "BLOCKED", "BATCH_QUERY", path=True,
           notes="RealAuction WAF; resolvable in Build Mode.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE via recorded lis pendens / final judgments on the open OR portal."),
    lt("Trustee Sale", NA, ["n/a — judicial-foreclosure state"], [], "",
       NA, "Florida is a judicial-foreclosure state; no trustee sales."),
    lt("Notice of Trustee Sale", NA, ["n/a — judicial-foreclosure state"], [],
       "", NA, "Non-judicial-state instrument; not applicable in Florida."),
    lt("Notice of Substitute Trustee Sale", NA,
       ["n/a — judicial-foreclosure state"], [], "", NA,
       "Non-judicial-state instrument; not applicable in Florida."),
    lt("Sheriff Sale", "APPLICABLE",
       ["Clerk foreclosure auction", "County Sheriff"],
       [cs("foreclosure_auction", FA_URL, "Clerk foreclosure auction",
           "BLOCKED_SOURCE", "BLOCKED", "BATCH_QUERY",
           notes="In FL the Clerk conducts foreclosure sales online.")],
       "foreclosure_auction", "SOURCE_FOUND_BLOCKED",
       "In FL the Clerk — not the sheriff — conducts foreclosure sales. "
       "Auction calendar WAF-blocked; sheriff levy sales are rare with no "
       "public portal."),
    lt("Tax Lien Foreclosure", "APPLICABLE",
       ["Clerk tax deed auction", "County Clerk"],
       [cs("tax_deed_auction", TDA_URL, "Clerk tax deed auction",
           "BLOCKED_SOURCE", "BLOCKED", "BATCH_QUERY",
           notes="RealAuction WAF."),
        C_OR("Recorded tax deeds (post-sale) are LIVE via OR.")],
       "tax_deed_auction", "SOURCE_FOUND_BLOCKED",
       "Tax-deed process. Auction calendar WAF-blocked; recorded tax deeds "
       "LIVE via clerk_official_records."),
    lt("Tax Sale", "APPLICABLE", ["Clerk tax deed auction"],
       [cs("tax_deed_auction", TDA_URL, "Clerk tax deed auction",
           "BLOCKED_SOURCE", "BLOCKED", "BATCH_QUERY",
           notes="RealAuction WAF.")],
       "tax_deed_auction", "SOURCE_FOUND_BLOCKED",
       "FL tax deed sale. Auction calendar WAF-blocked; resolvable in Build "
       "Mode."),
    lt("Tax Sale Certificate", "APPLICABLE", ["Tax Collector"],
       [cs("tax_certificate_sale", TCS_URL, "Tax Collector certificate sale",
           "PRIMARY_EVENT_SOURCE", "SEARCH_ONLY_PUBLIC", "FULL_COUNTY_BULK",
           docview=True,
           notes="Annual certificate sale; advertised list = full delinquent "
                 "set.")],
       "tax_certificate_sale", "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
       "LIVE but SEASONAL — advertised list publishes ~3-4 weeks before the "
       "annual June sale."),
    lt("Tax Delinquency", "APPLICABLE", ["Tax Collector"],
       [cs("tax_collector", TC_URL, "Tax Collector", "PRIMARY_EVENT_SOURCE",
           "OPEN_PUBLIC", "PER_RECORD_ONLY", docview=True,
           notes="Per-account delinquency lookup.")],
       "tax_collector", "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
       "LIVE but PER_RECORD_ONLY — coverage bounded by the resolved parcel "
       "set; the annual certificate sale supplies the bulk universe."),
    lt("Lis Pendens", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("Lis pendens recorded as official records.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — searchable by document type on the open OR portal."),
    lt("Civil Judgment", "APPLICABLE", ["County Clerk", "Circuit Court"],
       [C_OR("Recorded final money judgments."), C_CORE()],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — recorded judgments on the OR portal; CORE adds case detail."),
    lt("Abstract of Judgment", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("Recorded judgment liens / certified copies of judgment.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — recorded judgment liens on the OR portal."),
    lt("Mechanic Lien", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("FL Claim of Lien (Ch. 713) recorded here.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — FL records mechanic/construction liens as Claims of Lien."),
    lt("Construction Lien", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("FL Construction Lien / Claim of Lien (Ch. 713).")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — Florida's statutory term is Construction Lien."),
    lt("Federal Tax Lien", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("IRS federal tax liens recorded in official records.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — federal tax liens recorded on the OR portal."),
    lt("State Tax Lien", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("FL Dept. of Revenue warrants recorded in official records.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — FL DOR tax warrants recorded on the OR portal."),
    lt("Probate", "APPLICABLE", ["Circuit Court — Probate Division"],
       [C_CORE(access="FREE_ACCOUNT_REQUIRED",
               notes="Probate docket index public; documents need a free "
                     "registered account."),
        C_OR("Personal-representative deeds and heirship affidavits recorded "
             "in OR.")],
       "clerk_core_court", "SOURCE_FOUND_NEEDS_LOGIN",
       "Probate docket index is publicly searchable; document access needs a "
       "free CORE account. Related recorded deeds are LIVE via OR."),
    lt("Affidavit of Heirship", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("Affidavits of heirship recorded in official records.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — recorded on the OR portal."),
    lt("Executor Deed", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("FL Personal Representative's Deed recorded in OR.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — Florida's term is Personal Representative's Deed."),
    lt("Administrator Deed", "APPLICABLE", ["County Clerk / Recorder"],
       [C_OR("FL Personal Representative's Deed (intestate) recorded in OR.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — covered by the FL Personal Representative's Deed instrument."),
    lt("Code Lien", "APPLICABLE",
       ["County Clerk / Recorder", "City Municipal Code Compliance"],
       [C_OR("City code-enforcement liens are recorded in official records."),
        cs("code_enforcement", CE_URL, "City Municipal Code Compliance",
           "BLOCKED_SOURCE", "UNKNOWN", "UNKNOWN", path=False,
           notes="No public case portal.")],
       "clerk_official_records", "LIVE_SOURCE_FOUND",
       "LIVE — recorded code-enforcement liens appear on the OR portal."),
    lt("Demolition", "APPLICABLE", ["City Municipal Code Compliance"],
       [cs("code_enforcement", CE_URL, "City Municipal Code Compliance",
           "BLOCKED_SOURCE", "UNKNOWN", "UNKNOWN", path=False,
           notes="No public code-enforcement case portal located.")],
       "code_enforcement", "SOURCE_FOUND_BLOCKED",
       "Depends on the city code-enforcement case system — no public portal. "
       "Operator review required."),
    lt("Condemnation", "APPLICABLE", ["City Municipal Code Compliance"],
       [cs("code_enforcement", CE_URL, "City Municipal Code Compliance",
           "BLOCKED_SOURCE", "UNKNOWN", "UNKNOWN", path=False,
           notes="No public code-enforcement case portal located.")],
       "code_enforcement", "SOURCE_FOUND_BLOCKED",
       "Unsafe-structure / condemnation cases — no public portal. Operator "
       "review required."),
    lt("Eviction", "APPLICABLE", ["County Court — Civil Division"],
       [C_CORE(notes="County civil eviction dockets, public-access tier.")],
       "clerk_core_court", "LIVE_SOURCE_FOUND",
       "LIVE — county civil eviction dockets are public on CORE."),
    lt("Divorce", "APPLICABLE", ["Circuit Court — Family Division"],
       [C_CORE(access="FREE_ACCOUNT_REQUIRED",
               notes="Family docket index public; documents restricted.")],
       "clerk_core_court", "SOURCE_FOUND_NEEDS_LOGIN",
       "Family-division records are access-restricted in Florida; document "
       "access needs a free CORE account."),
    lt("Bankruptcy", "APPLICABLE",
       ["US Bankruptcy Court — M.D. Fla., Jacksonville Division"],
       [cs("pacer_mdfl", "https://pacer.uscourts.gov/",
           "Federal Bankruptcy Court", "BLOCKED_SOURCE",
           "PAID_SUBSCRIPTION_REQUIRED", "BATCH_QUERY", path=True,
           notes="Federal PACER — paid, outside county-source scope.")],
       "pacer_mdfl", "SOURCE_FOUND_PAID",
       "Federal jurisdiction (PACER, paid). Operator decides whether to fund "
       "access."),
    lt("Surplus", "APPLICABLE",
       ["County Clerk — foreclosure / tax-deed surplus funds"],
       [cs("clerk_core_court", CORE_URL, "County Clerk",
           "SUPPORTING_EVENT_SOURCE", "OPEN_PUBLIC", "BATCH_QUERY",
           docview=True,
           notes="The Clerk publishes unclaimed foreclosure/tax-deed surplus "
                 "lists.")],
       "clerk_core_court", "NEEDS_OPERATOR_REVIEW",
       "The Clerk publishes surplus-funds lists; build priority is low — "
       "flagged for operator review."),
]

assert len(lead_types) == 27, f"expected 27 lead types, got {len(lead_types)}"

matrix = {
    "county_slug": "duval_fl",
    "county_name": "Duval County",
    "state": "FL",
    "framework_version": FRAMEWORK_VERSION,
    "generated_at": GENERATED_AT,
    "county_build_status": "READY_TO_BUILD",
    "lead_types": lead_types,
}

coverage_map = {
    "live_sources": ["clerk_official_records", "clerk_core_court",
                     "tax_collector", "tax_certificate_sale", "parcel_master",
                     "gis_parcels", "dor_parcel_bulk"],
    "blocked_sources": ["foreclosure_auction", "tax_deed_auction"],
    "limited_coverage_sources": ["tax_collector", "tax_certificate_sale",
                                 "clerk_core_court"],
    "not_found_lead_types": [],
    "operator_review_required": ["code_enforcement", "Sheriff Sale", "Probate",
                                 "Divorce", "Bankruptcy", "Surplus"],
}

api_discovery = {
    "searched": [
        "or.duvalclerk.com/api|/swagger|/docs", "core.duvalclerk.com/api|/docs",
        "realforeclose.com|realtaxdeed.com /api|/swagger",
        "lienhub.com/api|/docs", "publicaccessnow.com/api|/swagger",
        "paopropertysearch.coj.net/api", "maps.coj.net/coj/rest/services",
        "Postman public collections", "GitHub (duvalclerk / realauction api)",
    ],
    "found": [
        {"api_url": "https://maps.coj.net/coj/rest/services",
         "api_type": "ArcGIS",
         "documentation_url": "https://maps.coj.net/coj/rest/services?f=help",
         "auth_required": False, "rate_limited": False,
         "source_role": "ENRICHMENT_SOURCE",
         "notes": "Public ArcGIS Server 11.1 REST directory; "
                  "CityBiz/Parcels/MapServer Parcels layer queryable."},
        {"api_url": "https://floridarevenue.com/property/Pages/DataPortal.aspx",
         "api_type": "Other", "documentation_url": "",
         "auth_required": False, "rate_limited": False,
         "source_role": "ENRICHMENT_SOURCE",
         "notes": "FL DOR bulk file directory — per-county NAL roll + parcel "
                  "GIS. Documented public download surface, not a query API."},
    ],
    "search_notes": "No documented API for any PRIMARY lead source — clerk "
        "records, court dockets, and RealAuction calendars are HTML/portal "
        "based. RealAuction exposes undocumented index.cfm?zaction= XHR "
        "endpoints behind its WAF — a Build Mode investigation item, not a "
        "recon blocker. Enrichment is well served by the ArcGIS REST API.",
}

enrichment_index_strategy = {
    "bulk_index_available": True,
    "bulk_index_source": "gis_parcels",
    "per_record_query_required": False,
    "per_record_query_cost_estimate": "FREE",
    "recommended_strategy": "Use the JaxGIS ArcGIS REST Parcels layer "
        "(gis_parcels) as the FULL_COUNTY_BULK enrichment index, joined to the "
        "FL DOR NAL assessment roll (dor_parcel_bulk) for owner/value/legal "
        "attributes. The Property Appraiser per-record portal (parcel_master) "
        "is the fallback for spot lookups. Enrichment never originates a lead.",
    "deferred_to_version": None,
}

# ---------------------------------------------------------------- assemble
config = copy.deepcopy(template)
config["county_id"] = "duval_fl"
config["county_name"] = "Duval County"
config["state"] = "FL"
config["subject_state_full"] = "Florida"
config["fips_code"] = "12031"
config["timezone"] = "America/New_York"
config["operator_market_priority"] = "exploratory"
config["state_rule_family"] = "FL_judicial_foreclosure"

config["geography"] = {
    "municipalities": [
        {"name": "Jacksonville", "code": "JAX", "fips_place": "1235000"},
        {"name": "Jacksonville Beach", "code": "JXB", "fips_place": "1235516"},
        {"name": "Atlantic Beach", "code": "ATB", "fips_place": "1202975"},
        {"name": "Neptune Beach", "code": "NPB", "fips_place": "1248450"},
        {"name": "Baldwin", "code": "BLD", "fips_place": "1203400"},
    ],
    "accepted_municipalities": [
        {"name": "JACKSONVILLE", "kind": "incorporated"},
        {"name": "JACKSONVILLE BEACH", "kind": "incorporated"},
        {"name": "ATLANTIC BEACH", "kind": "incorporated"},
        {"name": "NEPTUNE BEACH", "kind": "incorporated"},
        {"name": "BALDWIN", "kind": "incorporated"},
    ],
    "parcel_id_format": "^[0-9]{6}[- ]?[0-9]{4}$",
    "parcel_id_normalization": "strip-dashes-and-spaces",
    "address_format_notes": "Duval County uses a 10-digit Real Estate (RE) "
        "number as the parcel identifier, conventionally formatted "
        "'NNNNNN-NNNN'. Consolidated city-county (City of Jacksonville); most "
        "addresses carry city 'Jacksonville'.",
}

config["sources"] = sources

config["dashboard"]["title"] = "Duval County Lead Intelligence"
config["dashboard"]["subtitle"] = "Daily-refreshed real estate distress signals — Duval County, FL"
config["dashboard"]["default_view"] = "all_leads"
config["dashboard"]["build_label"] = ""
config["dashboard"]["build_label_reason"] = ""

config["deployment"]["github_org"] = "xcerebroai"
config["deployment"]["github_repo"] = "duval-fl-intel"
config["deployment"]["scheduler_runtime_class"] = ""
config["deployment"]["production_verification_status"] = ""

config["build_verdict"] = "READY_TO_BUILD"
config["build_verdict_reason"] = (
    "Duval County (consolidated City of Jacksonville government) has a "
    "verified, fully public primary lead source — the Clerk of Courts Official "
    "Records search (or.duvalclerk.com) — that independently originates 13+ of "
    "the 27 canonical lead types (foreclosure via lis pendens, all lien types, "
    "judgments, federal/state tax liens, tax deeds, personal-representative "
    "deeds, affidavits of heirship, recorded code liens). The CORE court "
    "portal adds public eviction and foreclosure-docket coverage. Three "
    "enrichment layers are available (Property Appraiser parcel master, JaxGIS "
    "ArcGIS REST API, FL DOR bulk NAL roll). The P0 gate passes. Two "
    "RealAuction auction calendars (foreclosure, tax deed) and the city "
    "code-enforcement case system are blocked, reducing coverage of specific "
    "lead types, but those lead types are already covered by recorded "
    "instruments — no critical blocker prevents Build Mode. Recommended "
    "dashboard label: PARTIAL_BUILD."
)
config["build_verdict_at"] = GENERATED_AT
config["auto_resolve_status"] = "PARTIALLY_RESOLVED"
config["final_resolution_status"] = "PARTIALLY_RESOLVED"
config["operator_override_audit"] = []
config["source_of_record_matrix"] = matrix
config["source_coverage_map"] = coverage_map
config["api_discovery"] = api_discovery
config["enrichment_index_strategy"] = enrichment_index_strategy

# ------------------------------------------------ write matrix artifact
matrix_path = REPO / "runs/duval_fl/recon/source_of_record_matrix.json"
matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
print(f"wrote {matrix_path.relative_to(REPO)}")

# ------------------------------------------------ write county config
result = write_county_config(
    config_dict=config,
    target_path=str(REPO / "config/counties/duval_fl.json"),
    schema_path=str(REPO / "config/counties/_schema.json"),
    overwrite=False,
)
print()
print(result.summary())
sys.exit(0 if result.is_ok() else 1)
