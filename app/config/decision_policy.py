"""
config/decision_policy.py
=========================
Single source of truth for ALL numeric thresholds and categorical constants
used by the Adaptive Decision Engine.

Rules:
- Do NOT embed raw numbers anywhere else in the codebase.
- Import from this module whenever a threshold comparison is needed.
- Changing a value here propagates everywhere automatically.
"""

from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class PolicyConfig:
    # ------------------------------------------------------------------
    # MASTERY
    # ------------------------------------------------------------------

    # Minimum score (0-100) to be considered "passing" a lesson
    MIN_MASTERY_SCORE: float = 75.0

    # Minimum number of scored attempts before mastery can be confirmed
    MIN_CONSISTENT_ATTEMPTS: int = 3

    # Number of recent attempts that must all be >= MIN_MASTERY_SCORE
    # to count as "consistent mastery"
    MASTERY_CONSISTENCY_WINDOW: int = 3

    # ------------------------------------------------------------------
    # REINFORCEMENT LIMITS
    # ------------------------------------------------------------------

    # Maximum reinforcement cycles before the engine must escalate
    MAX_REINFORCEMENT_ATTEMPTS: int = 3

    # Above this count, even a successful reinforcement is weighted lower
    HIGH_REINFORCEMENT_COUNT: int = 2

    # ------------------------------------------------------------------
    # ENGAGEMENT
    # ------------------------------------------------------------------

    # "low" engagement is defined as a level at or below this label
    # Ordered scale: unknown < low < medium < high
    LOW_ENGAGEMENT_THRESHOLD: str = "low"

    # Days of inactivity that signal disengagement risk
    INACTIVITY_DAYS_SOFT: int = 3    # mild concern
    INACTIVITY_DAYS_HARD: int = 7    # strong mentor signal

    # ------------------------------------------------------------------
    # RISK
    # ------------------------------------------------------------------

    # Number of risk_flags that constitutes a "high-risk" learner
    MENTOR_RISK_FLAG_COUNT: int = 2

    # Risk flags that immediately elevate mentor signal regardless of count
    CRITICAL_RISK_FLAGS: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "dropout_risk",
            "exam_failing",
            "mental_health_concern",
            "repeated_no_show",
        })
    )

    # ------------------------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------------------------

    # Any result below this confidence is flagged as low-confidence
    MIN_DECISION_CONFIDENCE: float = 0.55

    # Confidence returned when data is insufficient to decide
    INSUFFICIENT_DATA_CONFIDENCE: float = 0.30

    # ------------------------------------------------------------------
    # SCORING WEIGHTS  (used by the evidence evaluator)
    # Each weight is a positive float; they are normalised internally.
    # ------------------------------------------------------------------

    # --- ADVANCE weights ---
    W_ADVANCE_MASTERY_ACHIEVED: float = 3.0
    W_ADVANCE_CONSISTENT_SCORES: float = 2.0
    W_ADVANCE_SUFFICIENT_HISTORY: float = 1.5
    W_ADVANCE_STABLE_TREND: float = 1.0
    W_ADVANCE_HIGH_ENGAGEMENT: float = 0.5
    W_ADVANCE_VELOCITY_FAST: float = 0.5

    # --- REINFORCE weights ---
    W_REINFORCE_MASTERY_NOT_REACHED: float = 2.5
    W_REINFORCE_IMPROVING_TREND: float = 2.0
    W_REINFORCE_HIGH_ENGAGEMENT: float = 1.5
    W_REINFORCE_LOW_ATTEMPT_COUNT: float = 1.0
    W_REINFORCE_NO_PRIOR_REINFORCEMENT: float = 1.0
    W_REINFORCE_EFFECTIVE_PAST: float = 1.5
    W_REINFORCE_RECOVERABLE_GAP: float = 1.0

    # --- MENTOR weights ---
    W_MENTOR_REPEATED_FAILURE: float = 3.0
    W_MENTOR_DECLINING_TREND: float = 2.5
    W_MENTOR_INEFFECTIVE_REINFORCEMENT: float = 3.0
    W_MENTOR_MAX_REINFORCEMENT_HIT: float = 2.5
    W_MENTOR_LOW_ENGAGEMENT: float = 1.5
    W_MENTOR_HIGH_INACTIVITY: float = 2.0
    W_MENTOR_RISK_FLAGS: float = 2.0
    W_MENTOR_CRITICAL_RISK: float = 4.0
    W_MENTOR_PRIOR_MENTOR_INTERVENTION: float = 1.5
    W_MENTOR_PERSISTENT_WEAKNESS: float = 1.0

    # ------------------------------------------------------------------
    # ADVANCE BLOCKING thresholds
    # ------------------------------------------------------------------

    # Below this score, ADVANCE is always blocked even if mastery_status
    # says "mastered" (guards against stale mastery flags)
    ADVANCE_BLOCK_BELOW_SCORE: float = 65.0

    # If engagement is low AND trend is declining, block advance
    ADVANCE_BLOCK_LOW_ENGAGEMENT_DECLINING: bool = True

    # ------------------------------------------------------------------
    # TREND DEFINITIONS  (string values coming from Module 2)
    # ------------------------------------------------------------------
    TREND_IMPROVING: str = "improving"
    TREND_STABLE: str = "stable"
    TREND_DECLINING: str = "declining"
    TREND_UNKNOWN: str = "unknown"

    # ------------------------------------------------------------------
    # ENGAGEMENT LEVELS  (ordered lowest → highest)
    # ------------------------------------------------------------------
    ENGAGEMENT_LEVELS: tuple = ("unknown", "low", "medium", "high")

    # ------------------------------------------------------------------
    # MASTERY STATUS VALUES
    # ------------------------------------------------------------------
    MASTERY_MASTERED: str = "mastered"
    MASTERY_NOT_MASTERED: str = "not_mastered"
    MASTERY_IN_PROGRESS: str = "in_progress"
    MASTERY_UNKNOWN: str = "unknown"

    # ------------------------------------------------------------------
    # INTERVENTION EFFECTIVENESS VALUES
    # ------------------------------------------------------------------
    EFFECTIVENESS_EFFECTIVE: str = "effective"
    EFFECTIVENESS_PARTIALLY: str = "partially_effective"
    EFFECTIVENESS_INEFFECTIVE: str = "ineffective"
    EFFECTIVENESS_NONE: str = "none"


# Module-level singleton — import this everywhere
POLICY = PolicyConfig()
