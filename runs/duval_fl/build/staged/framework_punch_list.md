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
