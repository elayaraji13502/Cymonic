"""
decision_engine/evaluator.py
============================
Core evidence evaluation engine.

Architecture
------------
We use a transparent WEIGHTED EVIDENCE MODEL rather than a pure rule chain.
Each candidate decision (reinforce / advance / mentor) accumulates a score
from named, weighted signals.  The candidate with the highest normalised
score wins, subject to:

  1. Data validation   — insufficient data → low-confidence reinforce default
  2. Hard constraints  — overrides (see overrides.py) that can force a decision
  3. Evidence scoring  — accumulate signal weights per candidate
  4. Candidate selection — highest score wins
  5. Advance blockers  — applied after selection if winner is ADVANCE
  6. Confidence calc   — based on score margin and signal count

Why weighted evidence over pure rules?
  • Rules produce brittle cliffs (score 79 vs 80 → completely different path).
  • Weighted evidence reflects the multi-signal nature of learning assessment.
  • The same score produces different decisions under different contexts
    because different signals fire at different weights.
  • Fully transparent: every factor that contributed is logged.

All weights come from POLICY — nothing is hard-coded here.
"""

from __future__ import annotations

from typing import List, Tuple

from app.config.decision_policy import POLICY
from app.decision_engine.schemas import DecisionEnum, EvidenceScore
from app.decision_engine.signals import SignalBundle, engagement_rank
from app.decision_engine.overrides import evaluate_advance_blockers, evaluate_overrides


# ---------------------------------------------------------------------------
# Evidence accumulation helpers
# ---------------------------------------------------------------------------

def _add(score: float, weight: float, signals: List[str], label: str) -> float:
    """Add weight to score and record the signal label."""
    signals.append(label)
    return score + weight


# ---------------------------------------------------------------------------
# Per-candidate evidence functions
# ---------------------------------------------------------------------------

def _score_advance(b: SignalBundle) -> Tuple[float, List[str], List[str]]:
    """Return (raw_score, supporting_signals, blocking_signals) for ADVANCE."""
    score = 0.0
    supporting: List[str] = []
    blocking: List[str] = []

    if b.mastery_achieved:
        score = _add(score, POLICY.W_ADVANCE_MASTERY_ACHIEVED, supporting, "mastery_achieved")
    else:
        blocking.append("mastery_not_reached")

    if b.mastery_consistent:
        score = _add(score, POLICY.W_ADVANCE_CONSISTENT_SCORES, supporting, "mastery_consistent")
    else:
        blocking.append("mastery_not_consistent")

    if b.sufficient_history:
        score = _add(score, POLICY.W_ADVANCE_SUFFICIENT_HISTORY, supporting, "sufficient_history")
    else:
        blocking.append("insufficient_history")

    if b.trend_stable or b.trend_improving:
        score = _add(score, POLICY.W_ADVANCE_STABLE_TREND, supporting,
                     "trend_stable" if b.trend_stable else "trend_improving")

    if b.engagement_high or b.engagement_medium:
        score = _add(score, POLICY.W_ADVANCE_HIGH_ENGAGEMENT, supporting,
                     "high_engagement" if b.engagement_high else "medium_engagement")

    if b.velocity_fast:
        score = _add(score, POLICY.W_ADVANCE_VELOCITY_FAST, supporting, "velocity_fast")

    # Penalties (subtract, not block)
    if b.trend_declining:
        score -= POLICY.W_ADVANCE_STABLE_TREND * 1.5
        blocking.append("trend_declining")

    if b.single_high_spike and not b.mastery_consistent:
        score -= POLICY.W_ADVANCE_CONSISTENT_SCORES
        blocking.append("single_high_spike")

    if b.engagement_low:
        score -= POLICY.W_ADVANCE_HIGH_ENGAGEMENT
        blocking.append("low_engagement")

    return max(score, 0.0), supporting, blocking


def _score_reinforce(b: SignalBundle) -> Tuple[float, List[str], List[str]]:
    """Return (raw_score, supporting_signals, blocking_signals) for REINFORCE."""
    score = 0.0
    supporting: List[str] = []
    blocking: List[str] = []

    if b.mastery_not_reached:
        score = _add(score, POLICY.W_REINFORCE_MASTERY_NOT_REACHED, supporting, "mastery_not_reached")
    else:
        blocking.append("mastery_already_achieved")

    if b.trend_improving:
        score = _add(score, POLICY.W_REINFORCE_IMPROVING_TREND, supporting, "trend_improving")

    if b.engagement_high:
        score = _add(score, POLICY.W_REINFORCE_HIGH_ENGAGEMENT, supporting, "high_engagement")
    elif b.engagement_medium:
        score = _add(score, POLICY.W_REINFORCE_HIGH_ENGAGEMENT * 0.6, supporting, "medium_engagement")

    if b.low_attempt_count:
        score = _add(score, POLICY.W_REINFORCE_LOW_ATTEMPT_COUNT, supporting, "low_attempt_count")

    if b.no_prior_reinforcement:
        score = _add(score, POLICY.W_REINFORCE_NO_PRIOR_REINFORCEMENT, supporting, "no_prior_reinforcement")
    elif b.intervention_effective:
        score = _add(score, POLICY.W_REINFORCE_EFFECTIVE_PAST, supporting, "intervention_effective")
    elif b.intervention_partial:
        score = _add(score, POLICY.W_REINFORCE_EFFECTIVE_PAST * 0.5, supporting, "intervention_partial")

    if b.recoverable_gap:
        score = _add(score, POLICY.W_REINFORCE_RECOVERABLE_GAP, supporting, "recoverable_gap")

    # Penalties
    if b.max_reinforcement_hit:
        score -= POLICY.W_REINFORCE_NO_PRIOR_REINFORCEMENT * 2
        blocking.append("max_reinforcement_hit")

    if b.intervention_ineffective:
        score -= POLICY.W_REINFORCE_EFFECTIVE_PAST
        blocking.append("intervention_ineffective")

    if b.engagement_low and b.trend_declining:
        score -= POLICY.W_REINFORCE_HIGH_ENGAGEMENT
        blocking.append("low_engagement_declining")

    return max(score, 0.0), supporting, blocking


def _score_mentor(b: SignalBundle) -> Tuple[float, List[str], List[str]]:
    """Return (raw_score, supporting_signals, blocking_signals) for MENTOR."""
    score = 0.0
    supporting: List[str] = []
    blocking: List[str] = []

    # Strong signals
    if b.max_reinforcement_hit and b.intervention_ineffective:
        score = _add(score,
                     POLICY.W_MENTOR_MAX_REINFORCEMENT_HIT + POLICY.W_MENTOR_INEFFECTIVE_REINFORCEMENT,
                     supporting, "max_reinforcement_hit")
        supporting.append("intervention_ineffective")

    elif b.max_reinforcement_hit:
        score = _add(score, POLICY.W_MENTOR_MAX_REINFORCEMENT_HIT, supporting, "max_reinforcement_hit")

    elif b.intervention_ineffective and b.high_reinforcement:
        score = _add(score, POLICY.W_MENTOR_INEFFECTIVE_REINFORCEMENT, supporting, "intervention_ineffective")

    if b.trend_declining and b.sufficient_history:
        score = _add(score, POLICY.W_MENTOR_DECLINING_TREND, supporting, "trend_declining")

    if b.engagement_low:
        score = _add(score, POLICY.W_MENTOR_LOW_ENGAGEMENT, supporting, "low_engagement")

    if b.inactivity_hard:
        score = _add(score, POLICY.W_MENTOR_HIGH_INACTIVITY, supporting, "hard_inactivity")
    elif b.inactivity_soft:
        score = _add(score, POLICY.W_MENTOR_HIGH_INACTIVITY * 0.4, supporting, "soft_inactivity")

    if b.has_risk_flags:
        score = _add(score, POLICY.W_MENTOR_RISK_FLAGS, supporting, "has_risk_flags")

    if b.previous_mentor_intervention and b.mastery_not_reached:
        score = _add(score, POLICY.W_MENTOR_PRIOR_MENTOR_INTERVENTION, supporting, "prior_mentor_intervention")

    if b.has_persistent_weaknesses and b.high_reinforcement:
        score = _add(score, POLICY.W_MENTOR_PERSISTENT_WEAKNESS, supporting, "persistent_weakness")

    if b.score_far_below_mastery and b.trend_declining:
        score = _add(score, POLICY.W_MENTOR_REPEATED_FAILURE, supporting, "score_far_below_mastery")

    # Mild inhibitors
    if b.trend_improving:
        score -= POLICY.W_MENTOR_DECLINING_TREND * 0.5
        blocking.append("trend_improving_reduces_mentor")

    if b.engagement_high:
        score -= POLICY.W_MENTOR_LOW_ENGAGEMENT * 0.5
        blocking.append("high_engagement_reduces_mentor")

    return max(score, 0.0), supporting, blocking


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

def evaluate(b: SignalBundle) -> EvidenceScore:
    """
    Full evidence evaluation pipeline.

    Steps:
      1. Score all three candidates.
      2. Normalise (scores / total, guarded against div-by-zero).
      3. Return EvidenceScore with raw scores + signals.

    Overrides and final candidate selection are handled by the caller
    (DecisionResult builder) so that the override layer can inspect raw
    scores if needed.
    """
    adv_score, adv_supp, adv_block = _score_advance(b)
    rei_score, rei_supp, rei_block = _score_reinforce(b)
    men_score, men_supp, men_block = _score_mentor(b)

    return EvidenceScore(
        advance=adv_score,
        reinforce=rei_score,
        mentor=men_score,
        advance_signals=adv_supp,
        reinforce_signals=rei_supp,
        mentor_signals=men_supp,
        advance_blockers=adv_block,
        reinforce_blockers=rei_block,
        mentor_blockers=men_block,
    )


def select_candidate(ev: EvidenceScore, b: SignalBundle) -> Tuple[DecisionEnum, float, str]:
    """
    Given evidence scores, select the winning decision and compute confidence.

    Returns:
        (decision, confidence, selection_note)

    This is called AFTER overrides have been checked (and returned None).
    """
    candidates = {
        DecisionEnum.advance:   ev.advance,
        DecisionEnum.reinforce: ev.reinforce,
        DecisionEnum.mentor:    ev.mentor,
    }

    # Sort by score descending
    ranked = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
    winner_decision, winner_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # --- Advance post-selection blocker check --------------------------
    if winner_decision == DecisionEnum.advance:
        block = evaluate_advance_blockers(b)
        if block.blocked:
            # ADVANCE is blocked; re-rank without it
            note = "; ".join(block.reasons)
            candidates[DecisionEnum.advance] = 0.0
            ranked = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
            winner_decision, winner_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            selection_note = f"ADVANCE blocked ({note}); fell back to {winner_decision.value}"
        else:
            selection_note = "ADVANCE selected with no blocking conditions"
    else:
        selection_note = f"{winner_decision.value} selected by evidence score"

    # --- Confidence ---------------------------------------------------
    # Confidence = winner_score / total * margin_factor
    total = sum(candidates.values())
    if total == 0:
        confidence = POLICY.INSUFFICIENT_DATA_CONFIDENCE
    else:
        # Base = winner share
        base_confidence = winner_score / total
        # Margin factor: higher if winner clearly dominates
        margin = (winner_score - second_score) / total if total > 0 else 0.0
        confidence = min(0.95, base_confidence * 0.6 + margin * 0.4)
        confidence = max(POLICY.MIN_DECISION_CONFIDENCE, confidence)

    # Data-insufficient penalty
    if not b.data_sufficient:
        confidence = min(confidence, POLICY.INSUFFICIENT_DATA_CONFIDENCE)
        selection_note += " [low confidence: insufficient data]"

    return winner_decision, round(confidence, 3), selection_note
