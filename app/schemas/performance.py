"""
Pydantic schemas for Workflow 2 — Context & Performance Analysis.

These types define the stable API contract consumed by Workflow 3.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enum-like literals for contextual signal values
# ---------------------------------------------------------------------------

ScoreTrend = Literal["improving", "stable", "declining", "insufficient_data"]
MasteryStatus = Literal["mastered", "approaching", "not_mastered", "insufficient_data"]
EngagementStatus = Literal["high", "medium", "low", "unknown"]
InterventionEffectiveness = Literal["none", "effective", "ineffective", "insufficient_data"]
CertificationRisk = Literal["low", "medium", "high"]
AttemptPressure = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Sub-objects within the learner context package
# ---------------------------------------------------------------------------


class PerformanceContext(BaseModel):
    latest_score: Optional[float] = Field(None, description="Most recent valid assessment score (0–100)")
    average_score: Optional[float] = Field(None, description="Mean of all valid historical scores")
    trend: ScoreTrend = Field(..., description="Direction of score movement over time")
    attempt_count: int = Field(..., description="Total number of assessment attempts (including duplicates removed)")
    attempt_pressure: AttemptPressure = Field(..., description="Qualitative pressure level based on attempt count")
    time_spent_seconds: int = Field(0, description="Cumulative time spent on this lesson in seconds")
    completion_percentage: float = Field(0.0, description="Lesson completion percentage (0–100)")
    learning_velocity: Optional[float] = Field(None, description="Rate of improvement from Workflow 1")
    corrupted_score_count: int = Field(0, description="Number of assessment records with out-of-range scores")


class MasteryContext(BaseModel):
    status: MasteryStatus = Field(..., description="Mastery determination based on multi-signal evidence")
    threshold: float = Field(..., description="Lesson mastery threshold (0–100)")
    evidence: str = Field(..., description="Human-readable explanation of the mastery determination")


class EngagementContext(BaseModel):
    status: EngagementStatus = Field(..., description="Learner engagement level")
    raw_level: Optional[str] = Field(None, description="Raw engagement_level string from Workflow 1")


class InterventionContext(BaseModel):
    history_count: int = Field(0, description="Number of past interventions for this learner/lesson pair")
    effectiveness: InterventionEffectiveness = Field(
        ..., description="Whether past interventions have been effective"
    )
    last_intervention_type: Optional[str] = Field(None, description="Most recent intervention type applied")


class CertificationContext(BaseModel):
    required: bool = Field(..., description="Whether this lesson's course requires certification")
    risk: CertificationRisk = Field(..., description="Certification risk signal based on performance evidence")


# ---------------------------------------------------------------------------
# Top-level learner context package (primary output of Workflow 2)
# ---------------------------------------------------------------------------


class LearnerContextPackage(BaseModel):
    """
    Structured evidence package produced by Workflow 2.

    Workflow 3 uses this object to make the final reinforce/advance/mentor decision.
    This object intentionally contains NO final decision.
    """

    learner_id: int
    lesson_id: int
    performance: PerformanceContext
    mastery: MasteryContext
    engagement: EngagementContext
    intervention: InterventionContext
    certification: CertificationContext
    risk_flags: List[str] = Field(default_factory=list)
    strength_tags: List[str] = Field(default_factory=list)
    weakness_tags: List[str] = Field(default_factory=list)
    # Preserved conflicting signals so Workflow 3 can reason over them
    conflicting_signals: List[str] = Field(
        default_factory=list,
        description="Signals that contradict each other; preserved rather than silently resolved",
    )


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    learner_id: int = Field(..., gt=0)
    lesson_id: int = Field(..., gt=0)


class AnalyzeResponse(BaseModel):
    learner_context: LearnerContextPackage
    analysis_status: Literal["complete", "partial"] = "complete"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
