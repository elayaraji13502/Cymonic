#!/usr/bin/env python3
"""
scripts/test_decisions.py
=========================
Standalone test runner for Module 3 — Adaptive Decision Engine.

Run with:
    python -m scripts.test_decisions

Or directly:
    python scripts/test_decisions.py

No LLM API key required — runs purely on the deterministic fallback.
Does NOT start the FastAPI server.
Does NOT modify any learner data.

Output format:
    CASE_01_IMPROVING_LEARNER
    Decision:    REINFORCE
    Confidence:  0.72
    Source:      fallback
    Signals:     mastery_not_reached | trend_improving | high_engagement
    Reasoning:   ...
    Rejected:    advance → ...  |  mentor → ...
    ✓ PASS (expected: reinforce)
    ----------------------------------------------------------
"""

from __future__ import annotations

import sys
import os

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.disable(logging.WARNING)  # suppress INFO logs during script run

from app.decision_engine.engine import run_decision_engine
from app.decision_engine.schemas import DecisionEnum
from app.decision_engine.test_cases import TEST_CASES, list_cases

# ---------------------------------------------------------------------------
# Expected outcomes for validation
# ---------------------------------------------------------------------------

EXPECTED_DECISIONS: dict[str, DecisionEnum | None] = {
    "CASE_01_IMPROVING_LEARNER":     DecisionEnum.reinforce,
    "CASE_02_CLEAR_MASTERY":         DecisionEnum.advance,
    "CASE_03_REPEATED_FAILURE":      DecisionEnum.mentor,
    "CASE_04_HIGH_SCORE_DECLINING":  None,           # Must NOT be advance
    "CASE_05_LOW_SCORE_IMPROVING":   DecisionEnum.reinforce,
    "CASE_06_INSUFFICIENT_HISTORY":  None,           # Must be low confidence
    "CASE_07_CONFLICTING_SIGNALS":   None,           # Must NOT be advance
    "CASE_08_INEFFECTIVE_REINFORCEMENT": DecisionEnum.mentor,
}

NOT_EXPECTED: dict[str, DecisionEnum] = {
    "CASE_04_HIGH_SCORE_DECLINING":  DecisionEnum.advance,
    "CASE_06_INSUFFICIENT_HISTORY":  DecisionEnum.advance,
    "CASE_07_CONFLICTING_SIGNALS":   DecisionEnum.advance,
}

LOW_CONFIDENCE_CASES = {"CASE_06_INSUFFICIENT_HISTORY"}

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEP = "-" * 66


def _color(text: str, code: str) -> str:
    # Only use color when stdout is a real terminal
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


def _truncate(text: str, max_len: int = 140) -> str:
    return text if len(text) <= max_len else text[:max_len] + "..."


def _pass_fail(case_name: str, result) -> tuple[bool, str]:
    """Return (passed, message) for a test case result."""
    dec = result.decision

    # Hard expected decision
    if case_name in EXPECTED_DECISIONS and EXPECTED_DECISIONS[case_name] is not None:
        if dec == EXPECTED_DECISIONS[case_name]:
            return True, f"expected: {EXPECTED_DECISIONS[case_name].value}"
        else:
            return False, (
                f"expected: {EXPECTED_DECISIONS[case_name].value}, "
                f"got: {dec.value}"
            )

    # Must-NOT-be rules
    if case_name in NOT_EXPECTED:
        if dec == NOT_EXPECTED[case_name]:
            return False, f"must NOT be {NOT_EXPECTED[case_name].value}, got: {dec.value}"

    # Low-confidence check
    if case_name in LOW_CONFIDENCE_CASES:
        from app.config.decision_policy import POLICY
        if result.confidence > POLICY.INSUFFICIENT_DATA_CONFIDENCE + 0.05:
            return False, (
                f"confidence {result.confidence:.2f} too high for insufficient-data case"
            )

    return True, "no binding assertion"


def run_all() -> int:
    """Run all test cases, print results, return number of failures."""
    cases = list_cases()
    failures = 0
    passes = 0

    print()
    print(_color(f"{'='*66}", BOLD))
    print(_color("  MODULE 3 — ADAPTIVE DECISION ENGINE  |  Test Runner", BOLD))
    print(_color(f"{'='*66}", BOLD))
    print(f"  Running {len(cases)} predefined test cases  (fallback mode — no LLM needed)")
    print()

    for case_name in cases:
        ctx = TEST_CASES[case_name]

        try:
            result = run_decision_engine(ctx)
        except Exception as exc:
            print(_color(f"\n{case_name}", CYAN))
            print(_color(f"  ERROR: {exc}", RED))
            failures += 1
            print(SEP)
            continue

        passed, verdict_msg = _pass_fail(case_name, result)

        # Header
        print(_color(f"\n{case_name}", CYAN))
        print(f"  Decision:    {_color(result.decision.value.upper(), BOLD)}")
        print(f"  Confidence:  {result.confidence:.2f}")
        print(f"  Source:      {result.reasoning_source.value}")
        print(f"  Signals:     {' | '.join(result.signals[:6])}")
        print(f"  Reasoning:   {_truncate(result.reasoning)}")

        # Rejected alternatives
        for alt, reason in result.rejected_alternatives.items():
            print(f"  Rejected [{alt}]: {_truncate(reason, 100)}")

        # Evidence scores (from metadata if present)
        if result.metadata and "evidence_scores" in result.metadata:
            ev = result.metadata["evidence_scores"]
            print(
                f"  Evidence:    reinforce={ev.get('reinforce', '?'):.3f}  "
                f"advance={ev.get('advance', '?'):.3f}  "
                f"mentor={ev.get('mentor', '?'):.3f}"
            )

        # Pass/Fail
        if passed:
            passes += 1
            print(_color(f"  ✓ PASS  ({verdict_msg})", GREEN))
        else:
            failures += 1
            print(_color(f"  ✗ FAIL  ({verdict_msg})", RED))

        print(SEP)

    # Summary
    total = len(cases)
    print()
    print(_color(f"{'='*66}", BOLD))
    if failures == 0:
        print(_color(f"  ALL {total} TESTS PASSED", GREEN + BOLD))
    else:
        print(_color(f"  {passes}/{total} PASSED  |  {failures} FAILED", RED + BOLD))
    print(_color(f"{'='*66}", BOLD))
    print()

    return failures


def run_single(case_name: str) -> int:
    """Run a single named case. Returns 0 on pass, 1 on fail."""
    case_name = case_name.upper()
    if case_name not in TEST_CASES:
        print(_color(f"Unknown case: '{case_name}'", RED))
        print(f"Available: {', '.join(list_cases())}")
        return 1

    # Temporarily restrict to just this case
    from app.decision_engine import test_cases as _tc
    saved = dict(_tc.TEST_CASES)
    _tc.TEST_CASES = {case_name: saved[case_name]}
    failures = run_all()
    _tc.TEST_CASES = saved
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(run_single(sys.argv[1]))
    else:
        sys.exit(run_all())
