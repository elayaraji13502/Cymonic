"""
Domain exceptions for the progress workflow.

Each exception maps to a specific HTTP status code and structured error body.
The router translates these into HTTP responses — no business logic leaks
into the HTTP layer, and no raw DB exceptions escape to the client.
"""
from __future__ import annotations


class ProgressServiceError(Exception):
    """Base class for all progress-workflow errors."""

    http_status: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict = details or {}


# ── 404 errors ──────────────────────────────────────────────────────────────

class LearnerNotFoundError(ProgressServiceError):
    http_status = 404
    code = "LEARNER_NOT_FOUND"

    def __init__(self, learner_id: int) -> None:
        super().__init__(
            f"Learner with id={learner_id} does not exist.",
            {"learner_id": learner_id},
        )


class CourseNotFoundError(ProgressServiceError):
    http_status = 404
    code = "COURSE_NOT_FOUND"

    def __init__(self, course_id: int) -> None:
        super().__init__(
            f"Course with id={course_id} does not exist.",
            {"course_id": course_id},
        )


class LessonNotFoundError(ProgressServiceError):
    http_status = 404
    code = "LESSON_NOT_FOUND"

    def __init__(self, lesson_id: int) -> None:
        super().__init__(
            f"Lesson with id={lesson_id} does not exist.",
            {"lesson_id": lesson_id},
        )


# ── 400 / 409 errors ────────────────────────────────────────────────────────

class LessonCourseMismatchError(ProgressServiceError):
    """Lesson exists but does not belong to the supplied course."""
    http_status = 409
    code = "LESSON_COURSE_MISMATCH"

    def __init__(self, lesson_id: int, course_id: int, actual_course_id: int) -> None:
        super().__init__(
            f"Lesson id={lesson_id} belongs to course id={actual_course_id}, "
            f"not course id={course_id}.",
            {
                "lesson_id": lesson_id,
                "supplied_course_id": course_id,
                "actual_course_id": actual_course_id,
            },
        )


class DuplicateActivityError(ProgressServiceError):
    """Idempotency key already used — return the existing result."""
    http_status = 200          # caller gets 200 with duplicate payload
    code = "DUPLICATE_ACTIVITY"

    def __init__(self, idempotency_key: str, existing_attempt_id: int) -> None:
        super().__init__(
            f"Activity with idempotency_key={idempotency_key!r} was already recorded.",
            {"idempotency_key": idempotency_key, "existing_attempt_id": existing_attempt_id},
        )
        self.existing_attempt_id = existing_attempt_id


# ── 500 errors ───────────────────────────────────────────────────────────────

class DatabaseError(ProgressServiceError):
    """Wraps unexpected database failures — no raw SQL exposed to callers."""
    http_status = 503
    code = "DATABASE_UNAVAILABLE"

    def __init__(self, context: str = "") -> None:
        msg = "A database error occurred. Please try again later."
        if context:
            msg = f"{msg} (context: {context})"
        super().__init__(msg)
