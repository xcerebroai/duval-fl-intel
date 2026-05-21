# Build Mode Halt Log — Duval County, Florida (duval_fl)

Halted 2026-05-19. Framework v5.3.0. Phase reached: Phase 1 (synthetic harness).
Build classification: PARTIAL_BUILD. Operator decision: HALT.

---

## Halt record (§02.9)

    halt_reason        Pre-existing v5.3.0 known issue — hardcoded county slug
                       in build_leads.py:724 caught by Phase 1 verifier
    halt_class         documented_v5_3_0_known_issue
    halt_phase         Phase 1 (synthetic harness)
    halt_at            2026-05-19
    references         VERSION_NOTES_v5.3.0.md "Known Issues — Deferred to
                       v5.3.1" (item 1 — the `_state`-suffix slug pattern
                       blind spot; hardcoded county slugs as default parameter
                       values in ops/pipeline files; pre-existing as of
                       v5.2.0, not introduced by v5.3.0 or this build)
    recommended_action Fix in v5.3.1 patch cycle; do not inline-patch during
                       this client-experience test build
    auto_resume        false — operator will address in the v5.3.1 patch cycle
    build_outcome      HALTED (documented v5.3.0 known issue)

Verification: the cited known-issue entry was confirmed present in
VERSION_NOTES_v5.3.0.md lines 169–177. Item 1 explicitly names the
`<county>_<state>` slug form (`bexar_tx`) appearing as a "default parameter
value" not caught by the universality scanner — `build_leads.py:724`
(`--county-config default="config/counties/bexar_tx.json"`) is exactly that
pattern. Not introduced by the Duval build.

---

## Halt reason

Phase 1's acceptance verifier — `scaffold/tests/verify_synthetic_harness.py`,
the gate for REVIEW_GATE_2 — cannot run for Duval County because of a
framework defect carried over from the prior Bexar County build:

`scaffold/pipeline/build_leads.py:724` hardcodes
`--county-config` `default="config/counties/bexar_tx.json"`, and the verifier
invokes the pipeline without a `--county-config` argument. The default points
at a county config that does not exist in this repo. This is a §4.31.1
universality-contract violation (a real county slug inside `scaffold/pipeline/`).

Full detail: `runs/duval_fl/build/escalations/ESC-001-bexar-slug-in-build-leads.md`.

## What works (verified before the halt)

The Duval County pipeline itself is healthy. Run with the explicit flag:

    python3 scaffold/pipeline/build_leads.py --synthetic \
        --county-config config/counties/duval_fl.json

it succeeds and produces `data/leads_synthetic.json`:
  - lead_total: 12 (all 12 synthetic parcels)
  - pattern_counts: all 11 patterns present
  - score_tier_distribution: Hot 3 / Strong 3 / Workable 4 / Low 2
  - deal_path_distribution: wholesale, sub_to, messy_title, partial_interest,
    seller_finance, flip, surplus_recovery — all fire
  - stack_depth_distribution: 1->6, 2->4, 3->2

Only the verifier's no-argument invocation path is blocked.

## Operator decision

The operator was offered (A) authorize a minimal §4.31.1-compliance fix to
`build_leads.py` + `verify_synthetic_harness.py`, or (B) halt. The operator
chose **HALT**. No framework file was modified by Claude Code.

## State at halt

- Phase 0: COMPLETE. `config/counties/duval_fl.json` written and schema-valid;
  recon dossier + SoR matrix complete; build_verdict READY_TO_BUILD.
- REVIEW_GATE_1: signed off (`runs/duval_fl/gates/REVIEW_GATE_1.signoff.json`,
  decision proceed_full).
- Phase 1: STARTED, pipeline verified working for duval_fl, verifier BLOCKED.
- REVIEW_GATE_2: NOT reached.
- No git commit, no push, no deploy occurred.
- Files written this Build Mode session: `data/leads_synthetic.json`
  (Phase 1 synthetic output), `runs/duval_fl/build/escalations/ESC-001-*.md`,
  `runs/duval_fl/gates/REVIEW_GATE_1.signoff.json`, this halt log.

## To resume

Resolve the framework defect (ESC-001) upstream — fix the hardcoded `bexar_tx`
default in `scaffold/pipeline/build_leads.py` and make
`scaffold/tests/verify_synthetic_harness.py` county-agnostic — then re-enter
Build Mode at Phase 1. The build does not auto-resume (§02.9).

> RESOLVED: the v5.3.1 hotfix landed `_auto_discover_county_config`; Build Mode
> resumed and completed Phase 1 (synthetic harness), Phase 2 (gis_parcels
> enrichment foundation), and Phase 3 (clerk_official_records primary event
> source adapter). See halt 002 below for the next stop.

---

# Build Mode Halt 002 — v5.3.0 §16–§20 pipeline architecture not shipped

Halted 2026-05-21. Framework v5.3.1. Phase reached: Phase 3→4 (translator +
pipeline + matcher + evidence ledger). Build classification: PARTIAL_BUILD.

## Halt record (§02.9)

    halt_reason        Step 2 (build clerk translator -> *_leads_base.json ->
                       aggregator -> matched_leads.json, applying §17 debtor
                       party rules + §18 signal aggregation) instructs against a
                       pipeline architecture that is not implemented in shipped
                       code. The v5.3.0 §16–§20 + §4.34 Build Mode Protocol is
                       contract/doc surface only; the executable pipeline
                       (scaffold/pipeline/build_leads.py) is the v5.1.2-beta
                       monolithic orchestrator.
    halt_class         framework_architecture_not_shipped
    halt_phase         Phase 3 continuation / Phase 4
    halt_at            2026-05-21
    references         runs/duval_fl/build/escalations/ESC-002-v5.3.0-pipeline-
                       architecture-not-shipped.md ; MASTER_PROMPT §7 (no silent
                       architecture change), §4.34–§4.39, §4.21, README
                       ("v5.3.0 ships the contract surface").
    recommended_action Operator decision A / B / C in ESC-002. Do not improvise
                       a §16–§20 subsystem inside the county build; do not
                       silently substitute the monolithic pipeline.
    auto_resume        false
    build_outcome      HALTED (framework architecture gap — operator decision
                       required)

## What carries over unchanged

Phase 0 (recon + config), Phase 1 (synthetic harness), Phase 2 (gis_parcels
enrichment foundation), and Phase 3 (clerk_official_records primary event source
adapter) are complete and committed (commits 412aa66, fce61df, b398a85,
83a6a89). REVIEW_GATE_1/2/3 signed. No framework file modified by Claude Code
(the v5.3.1 hotfix to build_leads.py / FRAMEWORK_VERSION.json /
verify_synthetic_harness.py is the operator's, uncommitted in the working tree).

## To resume

Operator picks A (build the §16–§20 pipeline subsystem as a scoped framework
patch), B (authorize the shipped monolithic pipeline for Duval), or C (defer
§16–§20 to a framework patch cycle). See ESC-002. The build does not
auto-resume (§02.9).
