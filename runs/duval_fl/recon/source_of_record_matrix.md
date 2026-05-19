# Source-of-Record Matrix — Duval County, Florida (duval_fl)

Human-readable companion to `source_of_record_matrix.json`.
Generated 2026-05-19. Framework v5.3.0.

County build status: **READY_TO_BUILD** — multiple lead types have a verified
LIVE primary source; enrichment available; no critical blocker prevents Build
Mode. Several lead types are access-blocked (coverage is partial); see notes.

The 27-lead-type canonical sweep (§16.B), classified per-county:

| # | Lead type | Applicability | Selected source | Status |
|---|---|---|---|---|
| 1 | Foreclosure | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 2 | Trustee Sale | NOT_APPLICABLE_IN_STATE | — | NOT_APPLICABLE_IN_STATE |
| 3 | Notice of Trustee Sale | NOT_APPLICABLE_IN_STATE | — | NOT_APPLICABLE_IN_STATE |
| 4 | Notice of Substitute Trustee Sale | NOT_APPLICABLE_IN_STATE | — | NOT_APPLICABLE_IN_STATE |
| 5 | Sheriff Sale | APPLICABLE | foreclosure_auction | SOURCE_FOUND_BLOCKED |
| 6 | Tax Lien Foreclosure | APPLICABLE | tax_deed_auction | SOURCE_FOUND_BLOCKED |
| 7 | Tax Sale | APPLICABLE | tax_deed_auction | SOURCE_FOUND_BLOCKED |
| 8 | Tax Sale Certificate | APPLICABLE | tax_certificate_sale | LIVE_SOURCE_FOUND_LIMITED_COVERAGE |
| 9 | Tax Delinquency | APPLICABLE | tax_collector | LIVE_SOURCE_FOUND_LIMITED_COVERAGE |
| 10 | Lis Pendens | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 11 | Civil Judgment | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 12 | Abstract of Judgment | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 13 | Mechanic Lien | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 14 | Construction Lien | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 15 | Federal Tax Lien | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 16 | State Tax Lien | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 17 | Probate | APPLICABLE | clerk_core_court | SOURCE_FOUND_NEEDS_LOGIN |
| 18 | Affidavit of Heirship | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 19 | Executor Deed | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 20 | Administrator Deed | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 21 | Code Lien | APPLICABLE | clerk_official_records | LIVE_SOURCE_FOUND |
| 22 | Demolition | APPLICABLE | code_enforcement | SOURCE_FOUND_BLOCKED |
| 23 | Condemnation | APPLICABLE | code_enforcement | SOURCE_FOUND_BLOCKED |
| 24 | Eviction | APPLICABLE | clerk_core_court | LIVE_SOURCE_FOUND |
| 25 | Divorce | APPLICABLE | clerk_core_court | SOURCE_FOUND_NEEDS_LOGIN |
| 26 | Bankruptcy | APPLICABLE | pacer_mdfl | SOURCE_FOUND_PAID |
| 27 | Surplus | APPLICABLE | clerk_core_court | NEEDS_OPERATOR_REVIEW |

## Coverage notes

- **Florida is a judicial-foreclosure state.** Lead types 2–4 (Trustee Sale and
  its notices) are non-judicial-state instruments and do not exist in Florida —
  classified NOT_APPLICABLE_IN_STATE.
- **Foreclosure (1) is LIVE** via `clerk_official_records`: lis pendens, notices
  of sale, final judgments of foreclosure, and certificates of title are all
  recorded instruments, fully searchable on the open OR portal. The
  `foreclosure_auction` calendar (RealAuction) adds sale-date detail but is
  WAF-blocked; foreclosure leads do not depend on it.
- **Sheriff Sale (5):** In Florida the Clerk — not the sheriff — conducts
  foreclosure sales (the online RealAuction calendar). Sheriff levy sales on
  money judgments are rare and have no located public portal. Selected source is
  the clerk foreclosure auction; status SOURCE_FOUND_BLOCKED (WAF).
- **Tax Lien Foreclosure / Tax Sale (6, 7):** the Florida tax-deed process. The
  `tax_deed_auction` calendar is WAF-blocked, but recorded TAX_DEED instruments
  are LIVE via `clerk_official_records` — post-sale coverage is not lost.
- **Code Lien (21) is LIVE** because recorded code-enforcement liens appear in
  the OR portal. Demolition (22) and Condemnation (23) depend on the
  code-enforcement case system, which has no public portal — BLOCKED.
- **Bankruptcy (26)** is federal (PACER, paid); outside the county-source scope.
- **Surplus (27):** foreclosure / tax-deed surplus funds. The Clerk publishes
  unclaimed-surplus lists; build priority is low — flagged for operator review.

Authoritative machine-readable matrix: `source_of_record_matrix.json`
(schema-validated against `$defs/sourceOfRecordMatrix`).
