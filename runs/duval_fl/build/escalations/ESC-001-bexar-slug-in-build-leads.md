# ESCALATION ESC-001 — hardcoded `bexar_tx` slug blocks the Phase 1 verifier

Raised 2026-05-19 during Build Mode, Phase 1 (synthetic harness).
County: duval_fl. Framework v5.3.0.

## Context

Phase 1's acceptance gate is `scaffold/tests/verify_synthetic_harness.py`
(REVIEW_GATE_2 cannot be signed off until it exits 0). That verifier invokes
the pipeline as:

    python3 scaffold/pipeline/build_leads.py --synthetic

with NO `--county-config` argument.

`scaffold/pipeline/build_leads.py` line 724 declares:

    parser.add_argument("--county-config",
                        default="config/counties/bexar_tx.json", ...)

So when no `--county-config` is passed, the pipeline tries to open
`config/counties/bexar_tx.json` — a config from the PRIOR county build
(Bexar County, TX) that does not exist in this Duval repo. The verifier
fails immediately with:

    county config not found: .../config/counties/bexar_tx.json
    [FAIL] pipeline exited with code 2

## Why this is a framework defect, not a Duval problem

This is a **§4.31.1 universality-contract violation**: a real US county slug
(`bexar_tx`) is hardcoded inside a universal pipeline file
(`scaffold/pipeline/build_leads.py`). MASTER_PROMPT §4.31.1 forbids exactly
this — "No county name ... in `scaffold/pipeline/`." The v5.1.2-beta audit
claimed to have scrubbed 11 Bexar leaks from `scaffold/pipeline/`; this
`--county-config` default was missed. `test_county_agnostic_regression.py`
did not catch it (it passed in the Phase 0 gate run), so the regression
scanner has a gap for default-argument string literals.

The Duval pipeline ITSELF is healthy — running it with the explicit flag

    python3 scaffold/pipeline/build_leads.py --synthetic \
        --county-config config/counties/duval_fl.json

succeeds and produces a correct `data/leads_synthetic.json`
(lead_total 12, all 11 patterns, all score tiers, all deal paths). Only the
verifier's no-argument invocation path is blocked.

## Impact

Phase 1 cannot reach REVIEW_GATE_2 — the synthetic harness verifier is the
gate, and it cannot run for any county other than `bexar_tx` as the framework
currently stands. This blocks every new county build, not just Duval.

## Recommended action

A minimal, contract-COMPLIANT fix to two universal framework files:

1. `scaffold/pipeline/build_leads.py` — change the `--county-config` default
   from `"config/counties/bexar_tx.json"` to a county-agnostic value. Cleanest:
   `default=None`, and when `--synthetic` is set with no `--county-config`,
   auto-discover the single populated county config under `config/counties/`
   (the one non-underscore-prefixed `*.json`), or fall back to synthetic
   metadata. This removes the §4.31.1 violation.

2. `scaffold/tests/verify_synthetic_harness.py` — pass the discovered county
   config explicitly to the pipeline subprocess, so the verifier is
   county-agnostic by construction.

Both changes are bug fixes that bring the framework into compliance with its
own §4.31.1 universality contract. Neither changes architecture, a locked
rule, or any documented contract. Per MASTER_PROMPT §7, any framework-file
change must ship with a change manifest — that manifest will be produced.

## Operator decision required

This modifies universal framework code (`scaffold/`). Per §7's "no silent
architecture change" discipline, Claude Code is surfacing it rather than
patching silently. Options:

- **A — Authorize the minimal fix** above (recommended). Claude Code applies
  the two-file fix, emits a change manifest, completes Phase 1.
- **B — Operator fixes the framework defect** separately, then Claude Code
  resumes Phase 1.
- **C — Halt Build Mode** until the framework defect is resolved upstream.

Build Mode is paused at Phase 1 pending this decision. No framework file has
been modified.

---

## RESOLUTION (2026-05-19)

Operator decision: **C — Halt Build Mode.** Do NOT inline-patch the framework.

The operator confirmed this defect is a documented v5.3.0 known issue —
`VERSION_NOTES_v5.3.0.md` "Known Issues — Deferred to v5.3.1", item 1
(`_state`-suffix slug pattern blind spot; hardcoded county slugs as default
parameter values; pre-existing as of v5.2.0). It is scheduled for the v5.3.1
patch cycle and must NOT be inline-patched during this client-experience test
build. No framework file was modified by Claude Code. See
`runs/duval_fl/build/halt_log.md` for the §02.9 halt record.
