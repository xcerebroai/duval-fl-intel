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

