"""
decision_engine/overrides.py
============================
Hard override conditions that can force-promote or force-block a candidate
decision BEFORE the evidence scores are compared.

Override precedence (highest → lowest):
  1. Critical-risk  → force MENTOR
  2. Intervention-failure override → force MENTOR
  3. Clear-mastery override → force ADVANCE  (unless a hard block exists)
  4. Max-reinforcement + ineffective → force MENTOR
  5. Advance hard-blockers (applied after ADVANCE is selected)

Each override returns an OverrideResult.  The evaluator applies them in
order and stops at the first non-None result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.config.decision_policy import POLICY
from app.decision_engine.schemas import DecisionEnum
from app.decision_engine.signals import SignalBundle


@dataclass
class OverrideResult:
    """When an override fires, it locks the decision and explains why."""
    decision: DecisionEnum
    reason: str
    signals: List[str] = field(default_factory=list)
    confidence_modifier: float = 0.0   # added to base confidence


@dataclass
class AdvanceBlockResult:
    """An advance-specific blocker: signals that prevent ADVANCE even if
    evidence favours it."""
    blocked: bool
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_overrides(b: SignalBundle) -> Optional[OverrideResult]:
    """
    Evaluate all hard override conditions in priority order.

    Returns the first OverrideResult that fires, or None if no override
    applies and normal evidence evaluation should proceed.
    """

    # --- 1. Critical risk: always escalate to MENTOR -------------------
    if b.critical_risk_present:
        return OverrideResult(
            decision=DecisionEnum.mentor,
            reason=(
                "A critical risk flag is present. Automated adaptation is "
                "not appropriate; immediate human support is required."
            ),
            signals=["critical_risk"],
            confidence_modifier=0.20,
        )

    # --- 2. Intervention failure: repeated reinforcement + ineffective --
    # Condition: max reinforcement hit AND intervention was explicitly
    # ineffective AND mastery not achieved
    if (
        b.max_reinforcement_hit
        and b.intervention_ineffective
        and b.mastery_not_reached
    ):
        return OverrideResult(
            decision=DecisionEnum.mentor,
            reason=(
                f"Reinforcement has been attempted {b.reinforcement_count} time(s) "
                f"(≥ maximum of {POLICY.MAX_REINFORCEMENT_ATTEMPTS}) and has been "
                "explicitly ineffective. Continuing automated reinforcement would "
                "produce no benefit. Human mentor escalation is required."
            ),
            signals=["max_reinforcement_hit", "intervention_ineffective", "mastery_not_reached"],
            confidence_modifier=0.15,
        )

    # --- 3. Clear mastery: strong advance signal -----------------------
    # Condition: mastered + consistent + sufficient history + score above threshold
    # Must NOT have a hard advance blocker.
    if (
        b.mastery_achieved
        and b.mastery_consistent
        and b.sufficient_history
        and b.score_above_mastery
        and not b.critical_risk_present
        and not b.single_high_spike   # not just a lucky last attempt
    ):
        block = evaluate_advance_blockers(b)
        if not block.blocked:
            return OverrideResult(
                decision=DecisionEnum.advance,
                reason=(
                    "Mastery is confirmed: the learner has achieved mastery status, "
                    "with consistent scores above threshold across sufficient history. "
                    "No blocking conditions exist."
                ),
                signals=["mastery_achieved", "mastery_consistent", "sufficient_history", "score_above_mastery"],
                confidence_modifier=0.15,
            )
        # Mastery is clear but a hard block exists — fall through to normal evaluation

    # --- 4. Max reinforcement + not ineffective (borderline) -----------
    # If reinforcement count is maxed but effectiveness wasn't
    # explicitly 'ineffective', it still strongly signals MENTOR
    # unless trend is improving AND engagement is high.
    if (
        b.max_reinforcement_hit
        and b.mastery_not_reached
        and not b.intervention_ineffective   # handled above
    ):
        # Allow reinforce to continue only if trend improving + high engagement
        if not (b.trend_improving and b.engagement_high):
            return OverrideResult(
                decision=DecisionEnum.mentor,
                reason=(
                    f"Maximum reinforcement cycles ({POLICY.MAX_REINFORCEMENT_ATTEMPTS}) "
                    "have been reached without achieving mastery. Without a clear "
                    "improving trend and high engagement, continued automated "
                    "reinforcement is unlikely to succeed."
                ),
                signals=["max_reinforcement_hit", "mastery_not_reached"],
                confidence_modifier=0.10,
            )

    return None   # no override fired


def evaluate_advance_blockers(b: SignalBundle) -> AdvanceBlockResult:
    """
    Hard conditions that prevent ADVANCE even when evidence favours it.
    Called both inside evaluate_overrides (for the clear-mastery path)
    and by the evaluator after candidate selection.
    """
    reasons: List[str] = []

    # Score is below the absolute advance floor
    if b.latest_score is not None and b.latest_score < POLICY.ADVANCE_BLOCK_BELOW_SCORE:
        reasons.append(
            f"Latest score ({b.latest_score:.0f}) is below the absolute "
            f"advance floor ({POLICY.ADVANCE_BLOCK_BELOW_SCORE:.0f})."
        )

    # Single high spike without consistent history
    if b.single_high_spike and not b.mastery_consistent:
        reasons.append(
            "Latest score is a spike (≥20 pts above average) without "
            "consistent prior performance — insufficient evidence of mastery."
        )

    # Declining + low engagement
    if (
        POLICY.ADVANCE_BLOCK_LOW_ENGAGEMENT_DECLINING
        and b.trend_declining
        and b.engagement_low
    ):
        reasons.append(
            "Declining trend combined with low engagement contradicts "
            "the mastery evidence — advance is blocked pending investigation."
        )

    # No sufficient history
    if not b.sufficient_history:
        reasons.append(
            f"Insufficient assessment history "
            f"({b.attempt_count} attempt(s), minimum {POLICY.MIN_CONSISTENT_ATTEMPTS} required)."
        )

    return AdvanceBlockResult(blocked=bool(reasons), reasons=reasons)
