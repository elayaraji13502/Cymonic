"""
decision_engine/engine.py
=========================
Top-level orchestrator.

Execution pipeline
------------------
1.  Extract signals     (signals.py)
2.  Check overrides     (overrides.py)
3.  Score evidence      (evaluator.py)
4.  Select candidate    (evaluator.py)
5a. Try LLM reasoning   (agent.py)   → on success: build LLM response
5b. On any failure      → build fallback response (fallback.py)
6.  Return DecisionResponse

This is the ONLY file that other layers (api, tests, scripts) should import.
"""

from __future__ import annotations

import logging
from typing import List

from app.config.decision_policy import POLICY
from app.decision_engine.agent import LLMUnavailableError, call_llm
from app.decision_engine.evaluator import evaluate, select_candidate
from app.decision_engine.fallback import build_fallback_response
from app.decision_engine.overrides import evaluate_advance_blockers, evaluate_overrides
from app.decision_engine.schemas import (
    AllDecisionFactors,
    DecisionEnum,
    DecisionFactors,
    DecisionResponse,
    EvidenceScore,
    LearnerContext,
    ReasoningSourceEnum,
)
from app.decision_engine.signals import SignalBundle, extract_signals
from app.decision_engine.validator import LLMValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: build DecisionResponse from validated LLM output
# ---------------------------------------------------------------------------

def _llm_response(
    ctx: LearnerContext,
    llm_data: dict,
    decision: DecisionEnum,
    confidence: float,
    ev: EvidenceScore,
) -> DecisionResponse:
    """Assemble a DecisionResponse from validated LLM output."""
    from app.decision_engine.fallback import _build_decision_factors  # reuse factor builder
    factors = _build_decision_factors(ev)

    return DecisionResponse(
        learner_id=ctx.learner_id,
        lesson_id=ctx.lesson_id,
        context_version=ctx.context_version,
        decision=decision,
        reasoning=llm_data["reasoning"],
        confidence=llm_data["confidence"],
        signals=llm_data["signals"],
        decision_factors=factors,
        rejected_alternatives=llm_data["rejected_alternatives"],
        reasoning_source=ReasoningSourceEnum.llm,
        metadata={
            "evidence_scores": {
                "reinforce": round(ev.reinforce, 3),
                "advance":   round(ev.advance, 3),
                "mentor":    round(ev.mentor, 3),
            },
        },
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_decision_engine(ctx: LearnerContext) -> DecisionResponse:
    """
    Full decision pipeline.

    Parameters
    ----------
    ctx : LearnerContext
        Complete learner context from Module 2 (or a test mock).

    Returns
    -------
    DecisionResponse
        Complete decision with reasoning, confidence, and all supporting data.
    """

    # Step 1: Extract signals
    b: SignalBundle = extract_signals(ctx)

    # Step 2: Handle insufficient data early
    if not b.data_sufficient:
        logger.info(
            "Insufficient data for learner=%d lesson=%d. "
            "Missing: %s. Returning low-confidence default.",
            ctx.learner_id, ctx.lesson_id, b.missing_fields,
        )
        ev = evaluate(b)
        return build_fallback_response(
            ctx=ctx,
            decision=DecisionEnum.reinforce,  # safe default: ask for more evidence
            confidence=POLICY.INSUFFICIENT_DATA_CONFIDENCE,
            ev=ev,
            b=b,
            selection_note="Insufficient data — safe default applied",
            override_reason=(
                f"Key data is missing ({', '.join(b.missing_fields)}). "
                "Cannot produce a high-confidence decision. "
                "Defaulting to REINFORCE as the safest option pending more data."
            ),
        )

    # Step 3: Check hard overrides
    override = evaluate_overrides(b)
    if override:
        logger.info(
            "Override fired for learner=%d: %s → %s",
            ctx.learner_id, override.signals, override.decision.value,
        )
        ev = evaluate(b)
        base_confidence = min(
            0.95,
            POLICY.MIN_DECISION_CONFIDENCE + 0.2 + override.confidence_modifier,
        )
        try:
            llm_data = call_llm(ctx, override.decision, base_confidence, ev, b)
            return _llm_response(ctx, llm_data, override.decision, base_confidence, ev)
        except (LLMUnavailableError, LLMValidationError, TimeoutError, Exception) as exc:
            logger.warning("LLM unavailable/invalid after override: %s", exc)
            return build_fallback_response(
                ctx=ctx,
                decision=override.decision,
                confidence=base_confidence,
                ev=ev,
                b=b,
                selection_note=f"Override: {override.reason}",
                override_reason=override.reason,
                advance_block_reasons=[],
            )

    # Step 4: Score evidence
    ev = evaluate(b)

    # Step 5: Select candidate
    decision, confidence, selection_note = select_candidate(ev, b)

    # Collect advance block reasons if relevant
    advance_blocks: List[str] = []
    if decision != DecisionEnum.advance:
        adv_block = evaluate_advance_blockers(b)
        if adv_block.blocked:
            advance_blocks = adv_block.reasons

    logger.info(
        "Evidence decision for learner=%d: %s (conf=%.2f) | scores R=%.2f A=%.2f M=%.2f",
        ctx.learner_id, decision.value, confidence,
        ev.reinforce, ev.advance, ev.mentor,
    )

    # Step 6: Attempt LLM reasoning
    try:
        llm_data = call_llm(ctx, decision, confidence, ev, b)
        return _llm_response(ctx, llm_data, decision, confidence, ev)
    except (LLMUnavailableError, LLMValidationError, TimeoutError, Exception) as exc:
        logger.info("LLM path failed (%s); using deterministic fallback.", type(exc).__name__)

    # Step 7: Fallback
    return build_fallback_response(
        ctx=ctx,
        decision=decision,
        confidence=confidence,
        ev=ev,
        b=b,
        selection_note=selection_note,
        override_reason=None,
        advance_block_reasons=advance_blocks,
    )
