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
