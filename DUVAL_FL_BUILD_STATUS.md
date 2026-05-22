# Duval County, FL — Build Status

Status as of 2026-05-21. Framework v5.3.1. County: `duval_fl`.

**Build outcome: PARKED at Phase 3→4** — framework architecture gap (ESC-002).
County builds do not resume until the **v5.4.0 pipeline engine** ships. Not a
final delivery.

---

## Wide-recon input captured (2026-05-21)

The operator completed a wide manual recon of Duval County / Jacksonville — a
43-source dossier across foreclosure auctions, tax deed auctions, the tax
certificate sale, clerk/court records, property/parcel research, public notice
portals, code/permit/municipal-lien portals, surplus sources, and third-party
aggregators.

Captured as recon INPUT only:

  - `runs/duval_fl/recon/operator_source_dossier_2026-05-21.md` — the dossier,
    labeled UNVERIFIED, pending empirical probe + §13 classification.
  - `runs/duval_fl/recon/RECON_REOPEN_PENDING.md` — a wide Phase 0 re-recon,
    using the dossier as input, is scheduled **post-v5.4.0**.

The dossier is NOT written into `config/counties/duval_fl.json`. The §16
Source-of-Record Matrix is NOT rebuilt now. The existing built adapters are NOT
reclassified now. A **full re-recon + §16 matrix rebuild is scheduled
post-v5.4.0**, at which point all 43 sources are empirically probed and
classified PRIMARY / SUPPORTING / ENRICHMENT / REFERENCE / REJECTED per §13.

Duval remains parked at **ESC-002** — the wide-recon dossier does not change the
framework engine gap. Build resumption still waits on the v5.4.0 pipeline
engine.

---

## Phases complete

| Phase | Status | Evidence |
|---|---|---|
| 0 — Recon + Source-of-Record Matrix + county config | ✅ complete | `config/counties/duval_fl.json` (schema-valid), `runs/duval_fl/recon/` (14 artifacts + 10 fingerprints), verdict `READY_TO_BUILD` |
| 1 — Synthetic harness | ✅ complete | `verify_synthetic_harness.py` 110/110 PASS |
| 2 — Enrichment foundation (`gis_parcels`) | ✅ complete | `scrapers/gis_parcels.py`; ArcGIS adapter; fixture gate 12/12; **enrichment only — zero lead rows** |
| 3 — First primary event source (`clerk_official_records`) | ✅ adapter complete | `scrapers/clerk_official_records.py`; Acclaim portal, stdlib HTTP; lead-originating distress events verified; fixture gate 24/24 |

Gates signed: `REVIEW_GATE_1`, `REVIEW_GATE_2`, `REVIEW_GATE_3`.
Commits: `412aa66`, `fce61df`, `b398a85`, `83a6a89` (all local; repo has no remote).

## Where the build is blocked

**Phase 3 continuation / Phase 4** — translator, pipeline run, matcher, evidence
ledger. The operator's build plan instructs the v5.3.0 §16–§20 / §4.34 pipeline
architecture (`<source>_leads_base.json` → aggregator → `matched_leads.json`,
applying §17 debtor party rules + §18 signal aggregation + §19 idempotency).

A codebase search confirms that architecture is **v5.3.0 contract/doc surface
only — not implemented in `scaffold/pipeline/` executable code**. The shipped
pipeline (`build_leads.py`) is the v5.1.2-beta monolithic orchestrator. Full
detail: `runs/duval_fl/build/escalations/ESC-002-v5.3.0-pipeline-architecture-not-shipped.md`.

This is structurally the same class of gap as the `bexar_tx` halt (ESC-001):
v5.3.0 shipped documentation ahead of implementation. ESC-001 was a one-line
defect; ESC-002 is a multi-contract subsystem.

## Primary event source — proven, not blocked

Unlike a source-reality blocker, the Phase 3 source itself is fully built and
working: `clerk_official_records` (or.duvalclerk.com) is reachable with the
Python standard library, the adapter pulls recorded distress instruments
(lis pendens, liens, judgments, tax deeds, probate) and normalizes them to the
§4.32 contract. Duval HAS a verified lead-originating source. What is missing is
the framework pipeline stage that turns those raw events into scored, matched,
deduplicated lead rows.

## What is needed to resume

An operator decision (ESC-002):

  - **A** — authorize building the §16–§20 / §4.34 pipeline subsystem as a
    scoped, change-manifested framework patch (debtor party rules, signal
    aggregation, aggregator + idempotency self-check, base-file / matched-leads
    pipeline shape, clerk translator + wiring).
  - **B** — authorize the shipped v5.1.2-beta monolithic pipeline for the Duval
    build (translator → `run_pipeline` → `leads.json` + `evidence.jsonl`),
    accepting that §17/§18/§19 are not applied as discrete contract stages.
  - **C** — defer §16–§20 implementation to a framework patch cycle and hold
    Duval at Phase 3-complete.

No dashboard has been built or deployed. No leads have been produced. No false
dashboard exists. Build Mode does not auto-resume (§02.9).
