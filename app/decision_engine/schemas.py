"""
decision_engine/schemas.py
==========================
Pydantic v2 models for the complete learner context (input)
and the decision response (output).

These are the contract between Module 3 and both:
  - Module 2 (upstream context provider)
  - Module 4 (downstream strategy executor)

No thresholds live here — see config/decision_policy.py.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DecisionEnum(str, Enum):
    reinforce = "reinforce"
    advance   = "advance"
    mentor    = "mentor"


class TrendEnum(str, Enum):
    improving = "improving"
    stable    = "stable"
    declining = "declining"
    unknown   = "unknown"


class MasteryStatusEnum(str, Enum):
    mastered      = "mastered"
    not_mastered  = "not_mastered"
    in_progress   = "in_progress"
    unknown       = "unknown"


class MasteryConsistencyEnum(str, Enum):
    consistent   = "consistent"
    inconsistent = "inconsistent"
    insufficient = "insufficient"
    unknown      = "unknown"


class EngagementLevelEnum(str, Enum):
    high    = "high"
    medium  = "medium"
    low     = "low"
    unknown = "unknown"


class VelocityEnum(str, Enum):
    fast    = "fast"
    normal  = "normal"
    slow    = "slow"
    stalled = "stalled"
    unknown = "unknown"


class EffectivenessEnum(str, Enum):
    effective            = "effective"
    partially_effective  = "partially_effective"
    ineffective          = "ineffective"
    none                 = "none"
    unknown              = "unknown"


class DifficultyEnum(str, Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"


class CertRiskEnum(str, Enum):
    low     = "low"
    medium  = "medium"
    high    = "high"
    unknown = "unknown"


class ReasoningSourceEnum(str, Enum):
    llm      = "llm"
    fallback = "fallback"


# ---------------------------------------------------------------------------
# Input sub-models
# ---------------------------------------------------------------------------

class PerformanceContext(BaseModel):
    latest_score: Optional[float] = Field(None, ge=0, le=100)
    average_score: Optional[float] = Field(None, ge=0, le=100)
    previous_scores: List[float] = Field(default_factory=list)
    trend: TrendEnum = TrendEnum.unknown
    attempt_count: int = Field(0, ge=0)

    @field_validator("previous_scores", mode="before")
    @classmethod
    def validate_scores_range(cls, v: list) -> list:
        for s in v:
            if not (0 <= s <= 100):
                raise ValueError(f"Score {s} is outside valid range [0, 100]")
        return v


class MasteryContext(BaseModel):
    status: MasteryStatusEnum = MasteryStatusEnum.unknown
    threshold: Optional[float] = Field(None, ge=0, le=100)
    consistency: MasteryConsistencyEnum = MasteryConsistencyEnum.unknown


class EngagementContext(BaseModel):
    level: EngagementLevelEnum = EngagementLevelEnum.unknown
    inactivity_days: int = Field(0, ge=0)


class LearningContext(BaseModel):
    velocity: VelocityEnum = VelocityEnum.unknown
    completion_percentage: Optional[float] = Field(None, ge=0, le=100)


class InterventionContext(BaseModel):
    reinforcement_count: int = Field(0, ge=0)
    effectiveness: EffectivenessEnum = EffectivenessEnum.none
    previous_mentor_intervention: bool = False


class CourseContext(BaseModel):
    lesson_difficulty: DifficultyEnum = DifficultyEnum.medium
    required_lesson: bool = False
    certification_required: bool = False
    certification_risk: CertRiskEnum = CertRiskEnum.unknown


# ---------------------------------------------------------------------------
# Top-level input model
# ---------------------------------------------------------------------------

class LearnerContext(BaseModel):
    learner_id: int = Field(..., description="Unique identifier for the learner")
    lesson_id: int  = Field(..., description="Lesson being evaluated")
    context_version: int = Field(1, ge=1, description="Version stamp from Module 2")

    performance: PerformanceContext  = Field(default_factory=PerformanceContext)
    mastery:     MasteryContext      = Field(default_factory=MasteryContext)
    engagement:  EngagementContext   = Field(default_factory=EngagementContext)
    learning:    LearningContext     = Field(default_factory=LearningContext)
    intervention: InterventionContext = Field(default_factory=InterventionContext)
    course:      CourseContext       = Field(default_factory=CourseContext)

    risk_flags:    List[str] = Field(default_factory=list)
    weakness_tags: List[str] = Field(default_factory=list)
    strength_tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_score_consistency(self) -> "LearnerContext":
        """latest_score should not contradict average_score wildly without previous_scores."""
        ls = self.performance.latest_score
        av = self.performance.average_score
        if ls is not None and av is not None:
            if abs(ls - av) > 40 and not self.performance.previous_scores:
                # Not a hard error — just ensure previous_scores are supplied
                # when there's a large gap so the engine has full history
                pass  # warn via signal layer, not here
        return self


# ---------------------------------------------------------------------------
# Evidence model (internal — not exposed in API response directly)
# ---------------------------------------------------------------------------

class EvidenceScore(BaseModel):
    """Raw evidence scores for each candidate decision (before normalisation)."""
    reinforce: float = 0.0
    advance:   float = 0.0
    mentor:    float = 0.0

    # Named signals that fired
    reinforce_signals: List[str] = Field(default_factory=list)
    advance_signals:   List[str] = Field(default_factory=list)
    mentor_signals:    List[str] = Field(default_factory=list)

    # Named blockers that fired
    reinforce_blockers: List[str] = Field(default_factory=list)
    advance_blockers:   List[str] = Field(default_factory=list)
    mentor_blockers:    List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Decision factors sub-model (used in API response)
# ---------------------------------------------------------------------------

class DecisionFactors(BaseModel):
    supporting: List[str] = Field(default_factory=list)
    blocking:   List[str] = Field(default_factory=list)


class AllDecisionFactors(BaseModel):
    reinforce: DecisionFactors = Field(default_factory=DecisionFactors)
    advance:   DecisionFactors = Field(default_factory=DecisionFactors)
    mentor:    DecisionFactors = Field(default_factory=DecisionFactors)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

class DecisionResponse(BaseModel):
    learner_id:      int
    lesson_id:       int
    context_version: int

    decision:   DecisionEnum
    reasoning:  str
    confidence: float = Field(..., ge=0.0, le=1.0)
    signals:    List[str]

    decision_factors: AllDecisionFactors

    rejected_alternatives: Dict[str, str]

    reasoning_source: ReasoningSourceEnum

    # Optional metadata field — not part of Module 4 contract
    metadata: Optional[Dict[str, Any]] = None
