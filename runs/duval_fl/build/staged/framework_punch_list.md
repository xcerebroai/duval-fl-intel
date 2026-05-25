# Framework Punch-List — surfaced by the Duval FL build (2026-05-23)

Items in this file are **framework-level** gaps surfaced by running the Duval
County pipeline end-to-end on v5.4.0. They live here as the durable record for
the framework patch cycle. Do NOT fix any of them inside the Duval county
build — they belong to the framework.

---

## FW-PL-001 — Registry has no `CIVIL_JUDGMENT` / `ABSTRACT_OF_JUDGMENT` canonical type

**Status:** DEFERRED to a framework patch cycle. Do not fix in Duval.

**What's missing.** `knowledge_base/domain/canonical_doc_types.json` declares
three judgment-adjacent canonical types — `JUDGMENT_LIEN` (lead_generating,
implies property attachment is already established), `VACATED_JUDGMENT`
(negative_signal), and `FINAL_JUDGMENT_OF_FORECLOSURE` (lead_generating). There
is **no canonical concept for a recorded civil money judgment whose property
attachment is unverified.**

**Why it matters.** Under Fla. Stat. § 55.10, a civil money judgment becomes a
lien on real property only after a certified copy is recorded in the official
records of the county where the property is located **and** the debtor owns
real property in that county. A bare clerk-index row labeled `JUDGMENT` or
`CC COURT JUDGMENT` records the recording metadata only — parties, instrument
number, book/page, record date. The clerk index does not carry parcel id,
situs address, or legal description tied to real property (it is name-indexed,
not parcel-indexed). Whether the recorded judgment is a lien on real property
is a function of (a) the document body's lien language, and (b) the matcher
joining the judgment debtor → a parcel owner in the county.

**The diagnostic that surfaced it.** The Duval 60-row JUDGMENT / CC COURT
JUDGMENT diagnostic (`runs/duval_fl/build/staged/judgment_mapping_diagnostic.json`)
classified all 60 rows as `NAME_ONLY_JUDGMENT` (57) or `NON_PROPERTY_RECORD`
(3 explicit garnishments — `DISCOVER → VYSTAR GARNISHEE`, `CAVALRY → US DVA
GARNISHEE`). Zero of the 60 carried property-attachment evidence. The
party patterns reinforced this — debt-buyer creditors, medical creditors,
and apartment-landlord LLCs vs tenants who typically own no property in the
county.

**What the framework needs.** One or both of:

  - **`CIVIL_JUDGMENT`** — `lead_generating`, with an explicit matcher-required
    flag. Represents a recorded civil money judgment whose property
    attachment becomes provable only after the Phase 4 matcher joins debtor
    name → parcel owner. Without the matcher, rows of this type route to
    `REVIEW_REQUIRED`.
  - **`ABSTRACT_OF_JUDGMENT`** — the recorded instrument that makes a judgment
    operate as a real-property lien in jurisdictions that use it. (Florida
    uses a certified copy of the judgment under § 55.10 rather than a
    formally-titled "Abstract of Judgment" — both should be representable.)

The registry should also add `JUDGMENT_AGAINST_TENANT` / `EVICTION_MONEY_JUDGMENT`
or treat landlord-vs-tenant patterns as a known suppression class (the bulk
of bare-JUDGMENT volume in Florida is apartment-landlord eviction money
judgments where the defendant owns no real property in the county).

**Until then.** Bare `JUDGMENT` and `CC COURT JUDGMENT` raw labels on
Florida clerk OR feeds stay UNMAPPED in the per-county `doc_type_synonyms`.
The pipeline routes them through `REVIEW_REQUIRED` rather than asserting
property attachment. This is the honest-smaller-dashboard tradeoff: it
preserves the rows for operator triage without inflating the patterned
lead count with name-only civil judgments.

**Counties affected.** Every county whose clerk OR feed includes recorded
civil judgments without a distinct property-attached lien label. That is
essentially every Florida county and most other states that record
judgments in the clerk's official records. The fix lifts every county
build, not just Duval.

**Cross-reference.** Diagnostic detail in
`runs/duval_fl/build/staged/judgment_mapping_diagnostic.json`. The
Duval `doc_type_synonyms` map intentionally omits these two labels —
`config/counties/duval_fl.json` source `clerk_official_records.doc_type_synonyms`.

---

## FW-PL-002 — Registry has no `CERTIFICATE_OF_TITLE` canonical type

**Status:** DEFERRED to a framework patch cycle. Do not fix in Duval.

**What's missing.** Florida's judicial-foreclosure process culminates in the
Clerk issuing a **Certificate of Title** to the auction purchaser ~10 days
after the foreclosure sale closes (Fla. Stat. § 45.031). This is the
post-sale title-conveyance instrument — the analog of a non-judicial
state's `TRUSTEES_DEED_UPON_SALE`, but for judicial foreclosure. The
registry has `TRUSTEES_DEED_UPON_SALE` and `FINAL_JUDGMENT_OF_FORECLOSURE`
but **no `CERTIFICATE_OF_TITLE`** canonical.

**Where it surfaced.** The Duval 30-day clerk feed (2026-04-25 →
2026-05-24) contained **54 rows** with raw label `CERTIFICATE OF TITLE
DEED`. Each represents a real foreclosure sale that just closed — a
high-value primary distress signal. Without a canonical, the rows are
unmapped → REVIEW_REQUIRED.

**What the framework needs.** `CERTIFICATE_OF_TITLE` canonical
(lead_generating, source_class lead_generating, fires the `foreclosure`
pattern). The county synonym for Duval would then be `CERTIFICATE OF
TITLE DEED` → `CERTIFICATE_OF_TITLE`.

**Counties affected.** Every Florida county (judicial foreclosure state)
and every other judicial-foreclosure state whose clerk records the
post-sale title instrument under this label.

---

## FW-PL-003 — §17 picks filer-as-owner on a small subset of HOA / lender lis pendens rows

**Status:** OBSERVATIONAL — deferred to a framework refinement cycle. Do not
fix in Duval.

**What was observed.** On a 25,412-event Duval clerk run with 240
LIS_PENDENS lead-pattern rows, the filer-as-owner spot-check flagged 3
suspicious cases:
  - `BARTRAM SPRINGS HOMEOWNERS ASSOCIATION INC` (HOA foreclosure)
  - `WESTLAKE ESTATES HOMEOWNERS ASSOCIATION INC` (HOA foreclosure)
  - `ANDREWS FEDERAL CREDIT UNION` (possibly legitimate REO ownership)

That's a 1.25% suspicious rate (3/240) on LIS_PENDENS — small but real.
The two HOA cases are clear filer-as-owner inversions: in an HOA
foreclosure suit, the HOA is the plaintiff/filer (PL) and the homeowner
is the defendant/debtor (DF). The current Duval party mapping
(LIS_PENDENS override: Direct→PL, Indirect→DF) should have §17 pick the
DF side, but in these 3 cases the HOA name appears as resolved
owner_name.

**Likely cause.** Either the party fields in Acclaim are reversed for
specific HOA-recorded instruments, OR §17's debtor rule for LIS_PENDENS
has an edge case when the DF party is an individual and the PL party is
an entity (LLC / INC / "ASSOCIATION") and filer-suppression matches both
sides ambiguously.

**Counties affected.** Every county whose clerk feed has HOA / association
foreclosures. The rate is small (~1%) but real.

**Not a halt.** Per operator rule "Gaps → punch-list", logged here.

---

## FW-PL-004 — RealAuction family (RealForeclose / RealTaxDeed / LienHub) requires bidder registration

**Status:** PERMISSION blocker per §17/§01.13. Requires operator-provided credentials.

**What was probed.** Playwright (authorized 2026-05-25) with browser-like UA,
viewport, locale, timezone successfully bypassed the stdlib HTTP 403 and reached:

  - https://duval.realforeclose.com/index.cfm    → 200 OK
  - https://duval.realtaxdeed.com/index.cfm      → 200 OK
  - https://lienhub.com/county/duval             → 200 OK
  - https://duval.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR → 200 OK
  - https://duval.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW → 200 OK

But every public-facing path the auction-calendar UI lives behind shows only
the login chrome (`User Name / Password / Submit`) — the public-preview pages
return zero `AID=N` deep-links without an authenticated session. Per the Duval
clerk's own foreclosure-information page, "third-party bidders must register"
(no fee). Phase 0 recon's `next_access_strategy: use_operator_login` is the
operator-authorized resolution; Playwright alone is not enough.

**To unblock.** Operator provides:
  - RealForeclose Duval bidder account credentials (the same login covers
    RealTaxDeed and LienHub Duval).
  - OR an extracted session cookie from an authenticated browser session
    that Playwright can replay (`use_seeded_session`).

**Lead value if unblocked.**
  - RealForeclose: live foreclosure-auction calendar with sale dates +
    plaintiff + defendant + case number + opening bid + status (active /
    cancelled / sold) — directly fuels the dashboard's "Foreclosure sale
    window" filter.
  - RealTaxDeed: tax-deed auction calendar with parcel_id + applicant +
    status + assessed value (post-sale, surplus indicators).
  - LienHub: annual delinquent-parcel certificate list (seasonal — May/June).

---

## FW-PL-005 — `taxdeed.duvalclerk.com` jqGrid endpoint not discovered

**Status:** TECHNICAL blocker — could be cracked with Playwright in a follow-up.

The Tax Deed File Search at `https://taxdeed.duvalclerk.com/` is a jQuery
jqGrid client. Inline JS doesn't reference the data endpoint (config is in a
bundled .js). Without an open browser to inspect Network XHRs, the AJAX URL
(probably `/Grid/Read`, `/GetCases`, or `/Search/Records`) is undiscovered
this turn.

**To build.** Playwright probe: load the page, intercept the XHR fired by
the grid's `loadComplete` event, capture the URL + POST body shape, then
replay with stdlib (or Playwright route interception). One-session of
20-30 min reverse-engineering.

**Lead value.** The Clerk tax-deed case search yields per-parcel tax-deed
events with status (`SALE` / `SOLD` / `UNSOLD` / `REDEEMED` / `REMOVESALE`
/ `RESCHED` / `LANDS AVAILABLE` / `BANKRUPTCY` / `ESCHEATED`) keyed to
parcel_id — primary distress events with property already attached.

---

## FW-PL-006 — `core.duvalclerk.com` (CORE court records) not built this pass

**Status:** Stdlib-buildable in principle (ASP.NET WebForms with __VIEWSTATE),
similar pattern to `or.duvalclerk.com` (which IS built). Deferred for time.

Reaches HTTP 200 with stdlib + browser-UA; carries 9 tables and 41 td cells
in the landing HTML. Has a captcha reference but in the disclaimer-acceptance
gate (similar to OR portal, which accepts a one-line POST). The actual case
search lives at `/CoreCms.aspx?mode=PublicAccess` and exposes civil,
foreclosure, eviction, probate dockets.

**Lead value.** Eviction filings (county civil) and probate-case dockets are
not directly carried in `or.duvalclerk.com` — CORE is the canonical source.

---

## FW-PL-007 — `floridapublicnotices.com` (React SPA) not built this pass

**Status:** Playwright-buildable, deferred for time.

Statewide notice search; potentially redundant with `legals.jaxdailyrecord.com`
for Duval but useful as a backup feed and for cross-county work. React app
shell requires Playwright + post-render extraction (no server-rendered table).

---

## FW-PL-008 — `tclieninfo.coj.net` (Angular SPA) not built this pass

**Status:** Playwright-buildable, deferred for time.

Municipal lien info portal (nuisance / demolition / city liens). Angular
`<app-root>` SPA. Distinct value: surfaces city-level distress events that
aren't recorded as clerk liens until much later. Worth building on the next
Playwright pass.

---

## FW-PL-009 — `jaxdailyrecord_foreclosures` parser quality

**Status:** OPERATIONAL — heuristic regex, not a halt.

The stdlib scraper at `scrapers/jaxdailyrecord_foreclosures.py` extracts
publication_id + sale_date + property_address + case_no cleanly on most
rows, but the plaintiff/defendant text-parse is best-effort and not always
clean (about 25% of the 23 sampled rows have empty plaintiff/defendants).
This causes §17 to mark some foreclosure-notice rows REVIEW_REQUIRED
(`owner_name = "notice_of_sale against unidentified party"`) even though
the sale_date and case_no are populated.

**To fix.** Tighten the regex around the Florida courts' standard "Plaintiff,
vs. Defendant(s), NOTICE IS HEREBY GIVEN" template (the template is
predictable; current regex is too lenient).

