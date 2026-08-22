from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LearnerContext(BaseModel):
    latest_score: Optional[int] = None
    average_score: Optional[float] = None
    trend: str
    attempts: int
    mastery: str
    threshold: Optional[int] = None
    engagement: str
    learning_velocity: Optional[str] = None
    previous_reinforcement: int = 0
    reinforcement_effectiveness: str = "none"
    risk_flags: List[str] = Field(default_factory=list)
    certification_risk: str = "low"
    lesson_difficulty: Optional[str] = None
    required_lesson: bool = False
    previous_decisions: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluateDecisionRequest(BaseModel):
    learner_id: int
    lesson_id: int
    learner_context: LearnerContext


class ApplyDecisionRequest(BaseModel):
    learner_id: int
    lesson_id: int
    decision: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_source: str = "fallback"
    signals: List[str] = Field(default_factory=list)


class AnalyzePerformanceRequest(BaseModel):
    learner_id: int
    lesson_id: int
