"""
decision_engine/signals.py
==========================
Extracts and normalises all learner signals from a LearnerContext.

The output is a flat SignalBundle — a single object that every downstream
component (evaluator, overrides, fallback) reads from.  Nothing downstream
touches the raw LearnerContext directly; all interpretation happens here.

Design rationale
----------------
Centralising signal extraction here means:
1. Thresholds are read from POLICY once, not scattered.
2. Tests can inject a SignalBundle without needing a full LearnerContext.
3. The LLM prompt builder just formats this bundle — no re-interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.config.decision_policy import POLICY
from app.decision_engine.schemas import (
    EngagementLevelEnum,
    LearnerContext,
    MasteryStatusEnum,
    TrendEnum,
    VelocityEnum,
    EffectivenessEnum,
)


# ---------------------------------------------------------------------------
# Signal bundle — all boolean/numeric signals in one place
# ---------------------------------------------------------------------------

@dataclass
class SignalBundle:
    # ---- Mastery ----
    mastery_achieved: bool = False
    mastery_not_reached: bool = False
    mastery_unknown: bool = False
    mastery_consistent: bool = False   # recent scores all >= threshold

    # ---- Performance ----
    latest_score: Optional[float] = None
    average_score: Optional[float] = None
    score_above_mastery: bool = False
    score_near_mastery: bool = False     # within 10 pts
    score_far_below_mastery: bool = False  # > 20 pts below
    recoverable_gap: bool = False        # gap is ≤ 20 pts
    single_high_spike: bool = False      # last score >> avg by ≥ 20 pts

    # ---- Trend ----
    trend_improving: bool = False
    trend_stable: bool = False
    trend_declining: bool = False
    trend_unknown: bool = False

    # ---- Attempt history ----
    attempt_count: int = 0
    sufficient_history: bool = False     # >= MIN_CONSISTENT_ATTEMPTS
    low_attempt_count: bool = False      # < MIN_CONSISTENT_ATTEMPTS

    # ---- Engagement ----
    engagement_high: bool = False
    engagement_medium: bool = False
    engagement_low: bool = False
    engagement_unknown: bool = False
    inactivity_soft: bool = False        # >= INACTIVITY_DAYS_SOFT
    inactivity_hard: bool = False        # >= INACTIVITY_DAYS_HARD

    # ---- Velocity ----
    velocity_fast: bool = False
    velocity_normal: bool = False
    velocity_slow: bool = False
    velocity_stalled: bool = False

    # ---- Intervention ----
    reinforcement_count: int = 0
    no_prior_reinforcement: bool = False
    low_reinforcement: bool = False      # count < HIGH_REINFORCEMENT_COUNT
    high_reinforcement: bool = False     # count >= HIGH_REINFORCEMENT_COUNT
    max_reinforcement_hit: bool = False  # count >= MAX_REINFORCEMENT_ATTEMPTS
    intervention_effective: bool = False
    intervention_partial: bool = False
    intervention_ineffective: bool = False
    intervention_none: bool = False
    previous_mentor_intervention: bool = False

    # ---- Course / cert ----
    required_lesson: bool = False
    certification_required: bool = False
    certification_risk_high: bool = False
    lesson_difficulty_hard: bool = False

    # ---- Risk ----
    has_risk_flags: bool = False
    critical_risk_present: bool = False
    risk_flag_count: int = 0

    # ---- Weakness ----
    has_persistent_weaknesses: bool = False
    weakness_tags: List[str] = field(default_factory=list)
    strength_tags: List[str] = field(default_factory=list)

    # ---- Data quality ----
    data_sufficient: bool = True         # False when key fields are missing
    missing_fields: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

def extract_signals(ctx: LearnerContext) -> SignalBundle:
    """Translate a raw LearnerContext into a normalised SignalBundle."""

    b = SignalBundle()

    # --- Risk flags ---------------------------------------------------
    b.risk_flag_count = len(ctx.risk_flags)
    b.has_risk_flags = b.risk_flag_count >= POLICY.MENTOR_RISK_FLAG_COUNT
    b.critical_risk_present = bool(
        set(ctx.risk_flags) & POLICY.CRITICAL_RISK_FLAGS
    )

    # --- Weakness / strength tags ------------------------------------
    b.weakness_tags = list(ctx.weakness_tags)
    b.strength_tags = list(ctx.strength_tags)
    b.has_persistent_weaknesses = len(ctx.weakness_tags) > 0

    # --- Mastery ------------------------------------------------------
    status = ctx.mastery.status
    threshold = ctx.mastery.threshold or POLICY.MIN_MASTERY_SCORE

    b.mastery_achieved    = status == MasteryStatusEnum.mastered
    b.mastery_not_reached = status in (
        MasteryStatusEnum.not_mastered, MasteryStatusEnum.in_progress
    )
    b.mastery_unknown     = status == MasteryStatusEnum.unknown

    # Consistency from Module 2 label
    from app.decision_engine.schemas import MasteryConsistencyEnum
    b.mastery_consistent = (
        ctx.mastery.consistency == MasteryConsistencyEnum.consistent
    )

    # --- Performance --------------------------------------------------
    ls = ctx.performance.latest_score
    av = ctx.performance.average_score

    b.latest_score  = ls
    b.average_score = av

    if ls is None:
        b.missing_fields.append("latest_score")
    else:
        b.score_above_mastery   = ls >= threshold
        b.score_near_mastery    = threshold - 10 <= ls < threshold
        b.score_far_below_mastery = ls < threshold - 20
        b.recoverable_gap       = ls < threshold and (threshold - ls) <= 20

    # Detect a single-attempt spike: last score is ≥20 pts above average
    if ls is not None and av is not None:
        b.single_high_spike = (ls - av) >= 20

    if av is None:
        b.missing_fields.append("average_score")

    # --- Trend -------------------------------------------------------
    trend = ctx.performance.trend
    b.trend_improving = trend == TrendEnum.improving
    b.trend_stable    = trend == TrendEnum.stable
    b.trend_declining = trend == TrendEnum.declining
    b.trend_unknown   = trend == TrendEnum.unknown

    # --- Attempt count -----------------------------------------------
    b.attempt_count      = ctx.performance.attempt_count
    b.sufficient_history = b.attempt_count >= POLICY.MIN_CONSISTENT_ATTEMPTS
    b.low_attempt_count  = b.attempt_count < POLICY.MIN_CONSISTENT_ATTEMPTS

    # --- Engagement --------------------------------------------------
    level = ctx.engagement.level
    b.engagement_high    = level == EngagementLevelEnum.high
    b.engagement_medium  = level == EngagementLevelEnum.medium
    b.engagement_low     = level == EngagementLevelEnum.low
    b.engagement_unknown = level == EngagementLevelEnum.unknown

    inact = ctx.engagement.inactivity_days
    b.inactivity_soft = inact >= POLICY.INACTIVITY_DAYS_SOFT
    b.inactivity_hard = inact >= POLICY.INACTIVITY_DAYS_HARD

    # --- Velocity ----------------------------------------------------
    vel = ctx.learning.velocity
    b.velocity_fast    = vel == VelocityEnum.fast
    b.velocity_normal  = vel == VelocityEnum.normal
    b.velocity_slow    = vel == VelocityEnum.slow
    b.velocity_stalled = vel == VelocityEnum.stalled

    # --- Intervention ------------------------------------------------
    b.reinforcement_count     = ctx.intervention.reinforcement_count
    b.no_prior_reinforcement  = b.reinforcement_count == 0
    b.low_reinforcement       = b.reinforcement_count < POLICY.HIGH_REINFORCEMENT_COUNT
    b.high_reinforcement      = b.reinforcement_count >= POLICY.HIGH_REINFORCEMENT_COUNT
    b.max_reinforcement_hit   = b.reinforcement_count >= POLICY.MAX_REINFORCEMENT_ATTEMPTS
    b.previous_mentor_intervention = ctx.intervention.previous_mentor_intervention

    eff = ctx.intervention.effectiveness
    b.intervention_effective   = eff == EffectivenessEnum.effective
    b.intervention_partial     = eff == EffectivenessEnum.partially_effective
    b.intervention_ineffective = eff == EffectivenessEnum.ineffective
    b.intervention_none        = eff in (EffectivenessEnum.none, EffectivenessEnum.unknown)

    # --- Course / cert -----------------------------------------------
    b.required_lesson         = ctx.course.required_lesson
    b.certification_required  = ctx.course.certification_required
    b.certification_risk_high = ctx.course.certification_risk.value == "high"
    b.lesson_difficulty_hard  = ctx.course.lesson_difficulty.value == "hard"

    # --- Data sufficiency check ---------------------------------------
    # We consider data sufficient when we have at least a latest_score
    # and mastery status is not unknown.
    if ls is None or status == MasteryStatusEnum.unknown:
        b.data_sufficient = False
        if ls is None and "latest_score" not in b.missing_fields:
            b.missing_fields.append("latest_score")
        if status == MasteryStatusEnum.unknown:
            b.missing_fields.append("mastery_status")

    return b


def engagement_rank(b: SignalBundle) -> int:
    """0=unknown, 1=low, 2=medium, 3=high"""
    if b.engagement_high:    return 3
    if b.engagement_medium:  return 2
    if b.engagement_low:     return 1
    return 0
