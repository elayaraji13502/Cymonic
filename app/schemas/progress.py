"""
Pydantic schemas for the Progress API.

Covers:
  - POST /api/v1/progress/activities  (request + response)
  - GET  /api/v1/progress/{learner_id}/{course_id}  (response)
  - Shared error envelope
  - Integration-contract read models consumed by Workflow 2
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared error envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# POST /api/v1/progress/activities — Request
# ---------------------------------------------------------------------------

class ActivityRequest(BaseModel):
    """
    Body for recording a learner activity / assessment attempt.

    All validation is strict: missing required fields or wrong types are
    rejected immediately — no silent coercion of bad data.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",          # reject unexpected fields
    )

    learner_id: Annotated[int, Field(gt=0, description="Existing learner ID")]
    course_id: Annotated[int, Field(gt=0, description="Existing course ID")]
    lesson_id: Annotated[int, Field(gt=0, description="Existing lesson ID")]

    score: Annotated[
        float,
        Field(ge=0, le=100, description="Assessment score between 0 and 100 inclusive"),
    ]

    time_spent_minutes: Annotated[
        float,
        Field(ge=0, description="Time spent on the lesson; must be >= 0"),
    ]

    completed: Annotated[bool, Field(description="Whether the learner marked the lesson complete")]

    # Optional idempotency key supplied by the client (e.g. a UUID).
    # When provided the server stores it and rejects duplicate submissions
    # with the same key.
    idempotency_key: Annotated[
        str | None,
        Field(
            default=None,
            max_length=128,
            description="Optional client-generated idempotency key (UUID recommended)",
        ),
    ] = None

    @field_validator("score", mode="before")
    @classmethod
    def score_must_be_numeric(cls, v: Any) -> float:
        """Reject non-numeric types that Pydantic would silently coerce."""
        if isinstance(v, bool):
            raise ValueError("score must be a number, not a boolean")
        if not isinstance(v, int | float):
            raise ValueError("score must be a numeric value")
        return float(v)

    @field_validator("time_spent_minutes", mode="before")
    @classmethod
    def time_must_be_numeric(cls, v: Any) -> float:
        if isinstance(v, bool):
            raise ValueError("time_spent_minutes must be a number, not a boolean")
        if not isinstance(v, int | float):
            raise ValueError("time_spent_minutes must be a numeric value")
        return float(v)

    @field_validator("completed", mode="before")
    @classmethod
    def completed_must_be_bool(cls, v: Any) -> bool:
        """Explicitly reject string 'true'/'false' — caller must send JSON bool."""
        if isinstance(v, bool):
            return v
        raise ValueError("completed must be a JSON boolean (true or false), not a string or number")


# ---------------------------------------------------------------------------
# POST /api/v1/progress/activities — Response
# ---------------------------------------------------------------------------

class ActivityResponse(BaseModel):
    """
    Returned after a successful activity submission (new or idempotent replay).
    """

    model_config = ConfigDict(from_attributes=True)

    progress_id: int
    learner_id: int
    lesson_id: int
    score: float
    attempt_number: int
    status: str  # "created" | "updated" | "duplicate"


# ---------------------------------------------------------------------------
# GET /api/v1/progress/{learner_id}/{course_id} — nested pieces
# ---------------------------------------------------------------------------

class LessonProgressDetail(BaseModel):
    """State of one lesson within a course for a given learner."""

    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    lesson_title: str
    sequence_number: int
    difficulty: int
    mastery_threshold: float

    status: str
    completion_percentage: float
    current_score: float | None
    attempt_count: int
    time_spent_minutes: float
    engagement_level: str
    learning_velocity: float
    mastery_status: str
    last_activity_at: datetime | None
    updated_at: datetime


class AssessmentAttemptDetail(BaseModel):
    """A single past attempt at a lesson."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lesson_id: int
    score: float
    time_spent_minutes: float
    attempt_number: int
    submitted_at: datetime


class LearnerSignalDetail(BaseModel):
    """Aggregated qualitative signals for a lesson (for Workflow 2 consumption)."""

    model_config = ConfigDict(from_attributes=True)

    lesson_id: int
    performance_trend: str
    engagement_level: str
    risk_flags: list[str]
    strength_tags: list[str]
    weakness_tags: list[str]
    updated_at: datetime


class CourseProgressResponse(BaseModel):
    """
    Full course progress snapshot for a learner.
    Returned by GET /api/v1/progress/{learner_id}/{course_id}.
    """

    model_config = ConfigDict(from_attributes=True)

    learner_id: int
    learner_name: str
    course_id: int
    course_title: str

    overall_completion_percentage: float
    total_lessons: int
    completed_lessons: int
    failed_lessons: int

    lessons: list[LessonProgressDetail]
    recent_attempts: list[AssessmentAttemptDetail]   # last 10 across all lessons
    signals: list[LearnerSignalDetail]


# ---------------------------------------------------------------------------
# Integration-contract read models — consumed by Workflow 2
# ---------------------------------------------------------------------------

class LearnerProgressContext(BaseModel):
    """
    Complete learner context for one (learner, course) pair.
    Returned by the service's get_learner_progress() function.
    Workflow 2 should use this type and not query the DB directly.
    """

    model_config = ConfigDict(from_attributes=True)

    learner_id: int
    course_id: int

    # Per-lesson state list
    lessons: list[LessonProgressDetail]

    # Aggregated signals across all lessons in this course
    signals: list[LearnerSignalDetail]


class LessonProgressContext(BaseModel):
    """
    Progress state for a single lesson.
    Returned by get_lesson_progress().
    """

    model_config = ConfigDict(from_attributes=True)

    learner_id: int
    lesson_id: int
    status: str
    completion_percentage: float
    current_score: float | None
    attempt_count: int
    time_spent_minutes: float
    engagement_level: str
    learning_velocity: float
    mastery_status: str
    last_activity_at: datetime | None


class AssessmentHistoryContext(BaseModel):
    """
    All scored attempts for one learner on one lesson.
    Returned by get_assessment_history().
    """

    learner_id: int
    lesson_id: int
    attempts: list[AssessmentAttemptDetail]


class LearnerSignalContext(BaseModel):
    """
    Aggregated signals for one learner on one lesson.
    Returned by get_learner_signals().
    """

    learner_id: int
    lesson_id: int
    signal: LearnerSignalDetail | None  # None when no signal row exists yet
