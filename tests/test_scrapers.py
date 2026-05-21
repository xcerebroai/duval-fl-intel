#!/usr/bin/env python3
"""Phase 2 scraper fixture gate.

Per knowledge_base/engineering/05_verification_and_rollback.md "Scraper fixture
requirement": no scraper is production-ready until it passes saved-fixture
tests against the eight standard scenarios.

This harness discovers every adapter that has a `tests/fixtures/<source_id>/`
directory, imports `scrapers/<source_id>.py`, and calls its `parse_fixture()`
entry point against each of the eight fixtures. Tests never re-fetch from the
live source — fixtures are static, captured once during the build.

Assertions (per §05):
  1. empty_result      -> [] , no error
  2. single_result     -> exactly 1 wrapped record, required wrapper keys present
  3. multiple_results  -> 3 wrapped records, none dropped or duplicated
  4. pagination        -> records from all pages (sum across pages)
  5. record_detail     -> 1 enriched wrapped record
  6. document_download -> text-extraction-skipped marker (or downloaded doc)
  7. blocked_session   -> adapter signals blocked (SourceBlockedError / exit 4)
  8. malformed_record  -> record routed to review, parser_confidence < 80

Exit 0 iff every fixture passes for every discovered adapter.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"

# The §4.32 wrapped raw-record contract — universal across every adapter.
WRAPPER_KEYS = {
    "raw_record_id", "source_id", "source_url",
    "source_fetched_at", "parser_confidence", "raw_payload",
}

EIGHT_FIXTURES = [
    "empty_result.json",
    "single_result.json",
    "multiple_results.json",
    "pagination.json",
    "record_detail.json",
    "document_download.json",
    "blocked_session.json",
    "malformed_record.json",
]


class Result:
    def __init__(self) -> None:
        self.passes: list[str] = []
        self.fails: list[tuple[str, str]] = []

    def ok(self, label: str) -> None:
        self.passes.append(label)

    def fail(self, label: str, detail: str) -> None:
        self.fails.append((label, detail))

    def check(self, label: str, cond: bool, detail: str = "") -> None:
        (self.ok if cond else lambda l: self.fail(l, detail))(label)


def _is_wrapped(rec: dict) -> bool:
    return isinstance(rec, dict) and WRAPPER_KEYS.issubset(rec.keys())


def _test_adapter(source_id: str, res: Result) -> None:
    mod = importlib.import_module(f"scrapers.{source_id}")
    parse_fixture = getattr(mod, "parse_fixture", None)
    if parse_fixture is None:
        res.fail(f"{source_id}: parse_fixture", "adapter has no parse_fixture()")
        return

    blocked_exc = getattr(mod, "SourceBlockedError", RuntimeError)
    fdir = FIXTURES_ROOT / source_id
    for fx in EIGHT_FIXTURES:
        if not (fdir / fx).exists():
            res.fail(f"{source_id}/{fx}", "fixture file missing")

    # 1 — empty_result
    try:
        out = parse_fixture("empty_result.json")
        res.check(f"{source_id}/empty_result -> []",
                  isinstance(out, list) and len(out) == 0,
                  f"expected [], got {out!r}")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/empty_result", f"raised {e!r}")

    # 2 — single_result
    try:
        out = parse_fixture("single_result.json")
        ok = isinstance(out, list) and len(out) == 1 and _is_wrapped(out[0])
        res.check(f"{source_id}/single_result -> 1 wrapped record", ok,
                  f"got {out!r}")
        if ok:
            res.check(f"{source_id}/single_result confidence>=80",
                      out[0]["parser_confidence"] >= 80,
                      f"confidence={out[0]['parser_confidence']}")
            res.check(f"{source_id}/single_result raw_payload non-empty",
                      isinstance(out[0]["raw_payload"], dict)
                      and len(out[0]["raw_payload"]) > 0, "empty payload")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/single_result", f"raised {e!r}")

    # 3 — multiple_results
    try:
        out = parse_fixture("multiple_results.json")
        ok = isinstance(out, list) and len(out) == 3 and all(_is_wrapped(r) for r in out)
        res.check(f"{source_id}/multiple_results -> 3 wrapped records", ok,
                  f"got len={len(out) if isinstance(out, list) else out!r}")
        if ok:
            ids = [r["raw_record_id"] for r in out]
            res.check(f"{source_id}/multiple_results no duplicates",
                      len(set(ids)) == len(ids), f"ids={ids}")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/multiple_results", f"raised {e!r}")

    # 4 — pagination
    try:
        out = parse_fixture("pagination.json")
        ok = isinstance(out, list) and len(out) == 4 and all(_is_wrapped(r) for r in out)
        res.check(f"{source_id}/pagination -> records from all pages (4)", ok,
                  f"got len={len(out) if isinstance(out, list) else out!r}")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/pagination", f"raised {e!r}")

    # 5 — record_detail
    try:
        out = parse_fixture("record_detail.json")
        ok = isinstance(out, list) and len(out) == 1 and _is_wrapped(out[0])
        res.check(f"{source_id}/record_detail -> 1 enriched record", ok,
                  f"got {out!r}")
        if ok:
            res.check(f"{source_id}/record_detail payload populated",
                      len(out[0]["raw_payload"]) >= 5, "thin payload")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/record_detail", f"raised {e!r}")

    # 6 — document_download
    try:
        out = parse_fixture("document_download.json")
        ok = isinstance(out, list) and len(out) == 1 and (
            out[0].get("text_extraction_skipped") is True
            or out[0].get("document_path")
        )
        res.check(f"{source_id}/document_download -> doc handled or skip-flagged",
                  ok, f"got {out!r}")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/document_download", f"raised {e!r}")

    # 7 — blocked_session
    try:
        parse_fixture("blocked_session.json")
        res.fail(f"{source_id}/blocked_session", "no blocked signal raised")
    except blocked_exc:
        res.ok(f"{source_id}/blocked_session -> blocked signal (exit-4 class)")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/blocked_session",
                 f"raised {type(e).__name__}, expected SourceBlockedError")

    # 8 — malformed_record
    try:
        out = parse_fixture("malformed_record.json")
        ok = (isinstance(out, list) and len(out) == 1
              and _is_wrapped(out[0])
              and out[0]["parser_confidence"] < 80)
        res.check(f"{source_id}/malformed_record -> routed to review (conf<80)",
                  ok,
                  f"got {out!r}")
    except Exception as e:  # noqa: BLE001
        res.fail(f"{source_id}/malformed_record", f"raised {e!r}")


def main() -> int:
    if not FIXTURES_ROOT.exists():
        print("no tests/fixtures/ directory — nothing to test")
        return 0
    adapters = sorted(p.name for p in FIXTURES_ROOT.iterdir() if p.is_dir())
    if not adapters:
        print("no adapter fixture directories found")
        return 0

    res = Result()
    for source_id in adapters:
        print(f"# fixture suite: scrapers/{source_id}.py")
        _test_adapter(source_id, res)

    for label in res.passes:
        print(f"  [PASS] {label}")
    for label, detail in res.fails:
        print(f"  [FAIL] {label} — {detail}")

    print("=" * 60)
    print(f"PASS: {len(res.passes)}   FAIL: {len(res.fails)}")
    if res.fails:
        print("RESULT: FAIL — scraper fixture gate not satisfied.")
        return 1
    print("RESULT: PASS — scraper fixture gate satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
