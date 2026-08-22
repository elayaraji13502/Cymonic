"""
API router for Workflow 2 — Context & Performance Analysis.

Endpoints
---------
GET  /api/v1/performance/{learner_id}/{lesson_id}
    Returns the structured learner context package.

POST /api/v1/performance/analyze
    Accepts { learner_id, lesson_id } and returns the context package
    together with an analysis_status field.

Error format
------------
All errors follow the standard envelope:
    { "error": { "code": "...", "message": "...", "details": {} } }
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.performance import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorDetail,
    ErrorResponse,
    LearnerContextPackage,
)
from app.workflows.performance.context_builder import build_learner_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


def _make_error(code: str, message: str, http_status: int, details: dict | None = None) -> HTTPException:
    """Construct a standardised HTTPException with the project error envelope."""
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or {})
    )
    return HTTPException(status_code=http_status, detail=body.model_dump())


@router.get(
    "/{learner_id}/{lesson_id}",
    response_model=LearnerContextPackage,
    summary="Get learner context package",
    responses={
        404: {"model": ErrorResponse, "description": "Learner or lesson not found"},
        422: {"model": ErrorResponse, "description": "Configuration error (e.g. missing mastery threshold)"},
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
def get_learner_context(
    learner_id: int,
    lesson_id: int,
    db: Session = Depends(get_db),
) -> LearnerContextPackage:
    """
    Return the structured learner context package for a given learner and lesson.

    This endpoint is the primary data source for Workflow 3.
    It does NOT return a final adaptive decision.
    """
    try:
        return build_learner_context(db=db, learner_id=learner_id, lesson_id=lesson_id)
    except LookupError as exc:
        raise _make_error(
            code="NOT_FOUND",
            message=str(exc),
            http_status=status.HTTP_404_NOT_FOUND,
        ) from exc
    except ValueError as exc:
        raise _make_error(
            code="CONFIGURATION_ERROR",
            message=str(exc),
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Database error while building learner context.")
        raise _make_error(
            code="DATABASE_ERROR",
            message="The database is currently unavailable. Please try again later.",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze learner performance",
    responses={
        404: {"model": ErrorResponse, "description": "Learner or lesson not found"},
        422: {"model": ErrorResponse, "description": "Configuration error"},
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
def analyze_performance(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """
    Analyse learner performance and return the context package with a status field.

    The response structure is stable and intended for consumption by Workflow 3.
    """
    try:
        context = build_learner_context(
            db=db,
            learner_id=request.learner_id,
            lesson_id=request.lesson_id,
        )
        return AnalyzeResponse(learner_context=context, analysis_status="complete")
    except LookupError as exc:
        raise _make_error(
            code="NOT_FOUND",
            message=str(exc),
            http_status=status.HTTP_404_NOT_FOUND,
        ) from exc
    except ValueError as exc:
        raise _make_error(
            code="CONFIGURATION_ERROR",
            message=str(exc),
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Database error during performance analysis.")
        raise _make_error(
            code="DATABASE_ERROR",
            message="The database is currently unavailable. Please try again later.",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
