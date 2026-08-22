"""
Progress router — Workflow 1: Learner State & Dataset Management

Endpoints
---------
POST /api/v1/progress/activities
    Record a learner activity / assessment attempt.

GET  /api/v1/progress/{learner_id}/{course_id}
    Retrieve a learner's current course progress and lesson states.

The router is purely HTTP glue.  All business logic lives in the service.
Domain exceptions raised by the service are translated to structured HTTP
responses here; nothing else leaks to the caller.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.progress import (
    ActivityRequest,
    ActivityResponse,
    CourseProgressResponse,
    ErrorDetail,
    ErrorResponse,
)
from app.workflows.progress.exceptions import (
    CourseNotFoundError,
    DatabaseError,
    DuplicateActivityError,
    LearnerNotFoundError,
    LessonCourseMismatchError,
    LessonNotFoundError,
    ProgressServiceError,
)
from app.workflows.progress.service import (
    get_course_progress,
    record_activity,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/progress",
    tags=["progress"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(exc: ProgressServiceError) -> JSONResponse:
    """Convert a domain exception to the standard error envelope."""
    return JSONResponse(
        status_code=exc.http_status,
        content=ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/progress/activities
# ---------------------------------------------------------------------------

@router.post(
    "/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a learner activity or assessment attempt",
    responses={
        201: {"description": "Activity recorded (first attempt)"},
        200: {"description": "Activity already recorded (idempotent replay)", "model": ActivityResponse},
        404: {"description": "Learner, course or lesson not found", "model": ErrorResponse},
        409: {"description": "Lesson does not belong to the supplied course", "model": ErrorResponse},
        422: {"description": "Validation error (Pydantic)"},
        503: {"description": "Database unavailable", "model": ErrorResponse},
    },
)
async def post_activity(
    request: ActivityRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | ActivityResponse:
    """
    Record an assessment attempt for a learner.

    - Validates learner, course and lesson existence.
    - Rejects if the lesson does not belong to the supplied course.
    - Detects duplicate submissions via the optional ``idempotency_key``.
    - Updates learner progress and qualitative signals atomically.
    - On any database failure the entire transaction is rolled back.
    """
    try:
        result = await record_activity(db, request)

        # First-time creation → 201; update → 200
        http_status = (
            status.HTTP_201_CREATED if result.status == "created"
            else status.HTTP_200_OK
        )
        return JSONResponse(
            status_code=http_status,
            content=result.model_dump(),
        )

    except DuplicateActivityError as exc:
        # Idempotent replay: look up and return the existing attempt's data.
        # We need the progress record — fetch it so we can build a valid response.
        log.info(
            "Duplicate activity detected for learner=%s lesson=%s key=%s",
            request.learner_id,
            request.lesson_id,
            request.idempotency_key,
        )
        # Return a 200 with a "duplicate" status so the caller knows
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=ActivityResponse(
                progress_id=exc.existing_attempt_id,   # attempt id as proxy
                learner_id=request.learner_id,
                lesson_id=request.lesson_id,
                score=request.score,
                attempt_number=0,   # indeterminate for duplicate; caller should not rely on this
                status="duplicate",
            ).model_dump(),
        )

    except (LearnerNotFoundError, CourseNotFoundError, LessonNotFoundError) as exc:
        return _error_response(exc)

    except LessonCourseMismatchError as exc:
        return _error_response(exc)

    except DatabaseError as exc:
        return _error_response(exc)

    except ProgressServiceError as exc:
        # Catch-all for any other domain error
        return _error_response(exc)


# ---------------------------------------------------------------------------
# GET /api/v1/progress/{learner_id}/{course_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{learner_id}/{course_id}",
    response_model=CourseProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve learner course progress",
    responses={
        200: {"description": "Progress snapshot returned"},
        404: {"description": "Learner or course not found", "model": ErrorResponse},
        503: {"description": "Database unavailable", "model": ErrorResponse},
    },
)
async def get_progress(
    learner_id: int,
    course_id: int,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | CourseProgressResponse:
    """
    Return a learner's current progress across all lessons in a course.

    Includes:
    - Per-lesson completion status, scores, attempt counts, engagement level,
      learning velocity and mastery status.
    - Last 10 assessment attempts across the course.
    - Aggregated qualitative signals (risk flags, strength/weakness tags).
    """
    try:
        result = await get_course_progress(db, learner_id, course_id)
        return result

    except (LearnerNotFoundError, CourseNotFoundError) as exc:
        return _error_response(exc)

    except DatabaseError as exc:
        return _error_response(exc)

    except ProgressServiceError as exc:
        return _error_response(exc)
