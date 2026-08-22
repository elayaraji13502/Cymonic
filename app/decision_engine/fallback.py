"""
decision_engine/fallback.py
===========================
Deterministic fallback reasoning generator.

When the LLM is unavailable, times out, or returns invalid output,
this module generates the final DecisionResponse using the SAME policy,
signals, overrides, and evidence scores already computed by the evaluator.

The fallback is NOT a different set of rules.
It is a structured natural-language renderer of the evaluator's output.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.config.decision_policy import POLICY
from app.decision_engine.policy import SIGNAL_LABELS, label
from app.decision_engine.schemas import (
    AllDecisionFactors,
    DecisionEnum,
    DecisionFactors,
    DecisionResponse,
    EvidenceScore,
    LearnerContext,
    ReasoningSourceEnum,
)
from app.decision_engine.signals import SignalBundle


# ---------------------------------------------------------------------------
# Reasoning text builders
# ---------------------------------------------------------------------------

def _build_main_reasoning(
    decision: DecisionEnum,
    confidence: float,
    ev: EvidenceScore,
    b: SignalBundle,
    selection_note: str,
    override_reason: str | None,
) -> str:
    """Construct the plain-English reasoning paragraph."""

    parts: List[str] = []

    if override_reason:
        parts.append(f"[Override applied] {override_reason}")
    else:
        parts.append(f"Decision reached by evidence evaluation ({selection_note}).")

    # Winning signals
    winning_signals = {
        DecisionEnum.advance:   ev.advance_signals,
        DecisionEnum.reinforce: ev.reinforce_signals,
        DecisionEnum.mentor:    ev.mentor_signals,
    }[decision]

    if winning_signals:
        human_signals = [label(s) for s in winning_signals[:5]]
        parts.append(
            f"Primary supporting evidence for {decision.value.upper()}: "
            + "; ".join(human_signals) + "."
        )

    # Mention conflict if it exists
    if (
        b.trend_declining and b.score_above_mastery
        and decision != DecisionEnum.advance
    ):
        parts.append(
            "NOTE: Despite a high latest score, the declining trend signals "
            "that performance may not be sustainably mastered."
        )

    if b.trend_improving and b.engagement_high and decision != DecisionEnum.reinforce:
        parts.append(
            "NOTE: The improving trend and high engagement are positive but "
            "insufficient alone to satisfy advance criteria."
        )

    # Data quality note
    if not b.data_sufficient:
        parts.append(
            f"WARNING: Key data is missing ({', '.join(b.missing_fields)}). "
            f"Confidence is capped at {POLICY.INSUFFICIENT_DATA_CONFIDENCE:.0%}."
        )

    return " ".join(parts)


def _build_rejected_alternatives(
    decision: DecisionEnum,
    ev: EvidenceScore,
    b: SignalBundle,
    advance_block_reasons: List[str],
) -> Dict[str, str]:
    """Explain why the non-winning candidates were rejected."""

    explanations: Dict[str, str] = {}

    for candidate in DecisionEnum:
        if candidate == decision:
            continue

        if candidate == DecisionEnum.advance:
            if advance_block_reasons:
                explanations["advance"] = (
                    "ADVANCE was blocked by hard conditions: "
                    + "; ".join(advance_block_reasons)
                )
            elif not b.mastery_achieved:
                explanations["advance"] = (
                    "ADVANCE requires confirmed mastery; mastery has not been achieved."
                )
            elif ev.advance < ev.reinforce and ev.advance < ev.mentor:
                explanations["advance"] = (
                    f"ADVANCE evidence score ({ev.advance:.2f}) was lower than the "
                    f"winning candidate."
                )
            else:
                explanations["advance"] = (
                    "ADVANCE had insufficient supporting evidence compared to the selected decision."
                )

        elif candidate == DecisionEnum.reinforce:
            if b.max_reinforcement_hit and b.intervention_ineffective:
                explanations["reinforce"] = (
                    "REINFORCE was rejected: maximum reinforcement cycles reached "
                    "and previous reinforcement was explicitly ineffective. "
                    "Continuing would not benefit the learner."
                )
            elif b.mastery_achieved:
                explanations["reinforce"] = (
                    "REINFORCE is not appropriate: mastery has already been achieved."
                )
            elif ev.reinforce < ev.mentor:
                explanations["reinforce"] = (
                    f"REINFORCE evidence score ({ev.reinforce:.2f}) was lower than "
                    f"MENTOR ({ev.mentor:.2f}), driven by declining performance / "
                    "high inactivity / ineffective prior reinforcement."
                )
            else:
                explanations["reinforce"] = (
                    "REINFORCE evidence score was lower than the selected decision."
                )

        elif candidate == DecisionEnum.mentor:
            if not b.has_risk_flags and not b.max_reinforcement_hit and not b.trend_declining:
                explanations["mentor"] = (
                    "MENTOR was not indicated: no critical risk flags, no declining trend, "
                    "and reinforcement limit has not been reached. Automated support "
                    "can still be effective."
                )
            elif ev.mentor < ev.reinforce:
                explanations["mentor"] = (
                    f"MENTOR evidence score ({ev.mentor:.2f}) was lower than "
                    f"REINFORCE ({ev.reinforce:.2f}): the learner shows recoverable "
                    "gaps and positive engagement signals."
                )
            else:
                explanations["mentor"] = (
                    "MENTOR evidence score was lower than the selected decision."
                )

    return explanations


def _build_decision_factors(ev: EvidenceScore) -> AllDecisionFactors:
    return AllDecisionFactors(
        reinforce=DecisionFactors(
            supporting=ev.reinforce_signals,
            blocking=ev.reinforce_blockers,
        ),
        advance=DecisionFactors(
            supporting=ev.advance_signals,
            blocking=ev.advance_blockers,
        ),
        mentor=DecisionFactors(
            supporting=ev.mentor_signals,
            blocking=ev.mentor_blockers,
        ),
    )


def _build_active_signals(decision: DecisionEnum, ev: EvidenceScore, b: SignalBundle) -> List[str]:
    """Return the top signals for the winning decision."""
    base = {
        DecisionEnum.advance:   ev.advance_signals,
        DecisionEnum.reinforce: ev.reinforce_signals,
        DecisionEnum.mentor:    ev.mentor_signals,
    }[decision]

    extras: List[str] = []
    if not b.data_sufficient:
        extras.append("data_insufficient")
    if b.single_high_spike:
        extras.append("single_high_spike")
    if b.trend_declining and (b.score_above_mastery or b.mastery_achieved):
        extras.append("conflicting_signals")

    return base + extras


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_fallback_response(
    ctx: LearnerContext,
    decision: DecisionEnum,
    confidence: float,
    ev: EvidenceScore,
    b: SignalBundle,
    selection_note: str,
    override_reason: str | None = None,
    advance_block_reasons: List[str] | None = None,
) -> DecisionResponse:
    """
    Build a complete DecisionResponse using only deterministic reasoning.

    This is called when:
      - FORCE_FALLBACK is set.
      - LLM is unavailable.
      - LLM times out.
      - LLM output fails validation.
    """

    _advance_blocks = advance_block_reasons or []

    reasoning = _build_main_reasoning(
        decision, confidence, ev, b, selection_note, override_reason
    )
    rejected = _build_rejected_alternatives(decision, ev, b, _advance_blocks)
    factors = _build_decision_factors(ev)
    signals = _build_active_signals(decision, ev, b)

    return DecisionResponse(
        learner_id=ctx.learner_id,
        lesson_id=ctx.lesson_id,
        context_version=ctx.context_version,
        decision=decision,
        reasoning=reasoning,
        confidence=confidence,
        signals=signals,
        decision_factors=factors,
        rejected_alternatives=rejected,
        reasoning_source=ReasoningSourceEnum.fallback,
        metadata={
            "evidence_scores": {
                "reinforce": round(ev.reinforce, 3),
                "advance":   round(ev.advance, 3),
                "mentor":    round(ev.mentor, 3),
            },
            "selection_note": selection_note,
        },
    )
