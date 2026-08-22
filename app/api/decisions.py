"""
api/decisions.py
================
FastAPI router for Module 3 — Adaptive Decision Engine.

Endpoints
---------
POST /api/v1/decisions/evaluate
    Main production endpoint.  Accepts a full LearnerContext, returns DecisionResponse.

GET  /api/v1/decisions/test-cases
    List all predefined test case names (dev/test only).

POST /api/v1/decisions/test/{case_name}
    Run a named test case and return the decision (dev/test only).

GET  /api/v1/decisions/health
    Lightweight health probe.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.decision_engine.engine import run_decision_engine
from app.decision_engine.schemas import DecisionResponse, LearnerContext
from app.decision_engine.test_cases import TEST_CASES, get_case, list_cases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    module: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Health probe")
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        module="Adaptive Decision Engine",
        version="1.0.0",
    )


# ---------------------------------------------------------------------------
# Main evaluation endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/evaluate",
    response_model=DecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a learner context and return an adaptive decision",
    description=(
        "Accepts a full LearnerContext from Module 2 and returns a single "
        "adaptive decision (reinforce / advance / mentor) with reasoning, "
        "confidence, supporting signals, and rejected alternatives.\n\n"
        "**This endpoint does NOT modify any learner data.**\n"
        "Module 4 is responsible for acting on the returned decision."
    ),
)
def evaluate_decision(ctx: LearnerContext) -> DecisionResponse:
    logger.info(
        "Evaluation request: learner_id=%d lesson_id=%d context_version=%d",
        ctx.learner_id, ctx.lesson_id, ctx.context_version,
    )
    try:
        result = run_decision_engine(ctx)
        logger.info(
            "Decision: %s confidence=%.2f source=%s",
            result.decision.value, result.confidence, result.reasoning_source.value,
        )
        return result
    except Exception as exc:
        logger.exception("Unhandled error during decision evaluation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision engine error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Test-case endpoints (development / testing only)
# ---------------------------------------------------------------------------

class TestCaseListResponse(BaseModel):
    count: int
    cases: List[str]


@router.get(
    "/test-cases",
    response_model=TestCaseListResponse,
    summary="[DEV] List all predefined test cases",
    description="Returns the names of all predefined learner contexts for testing. "
                "**Does not modify any data.**",
)
def list_test_cases() -> TestCaseListResponse:
    cases = list_cases()
    return TestCaseListResponse(count=len(cases), cases=cases)


class TestCaseDetailResponse(BaseModel):
    case_name: str
    context: Dict[str, Any]
    result: DecisionResponse


@router.post(
    "/test/{case_name}",
    response_model=TestCaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="[DEV] Run a named predefined test case",
    description=(
        "Runs the decision engine against a predefined learner context by name. "
        "Useful for verifying engine behaviour without building a full integration.\n\n"
        "Available cases: CASE_01_IMPROVING_LEARNER, CASE_02_CLEAR_MASTERY, "
        "CASE_03_REPEATED_FAILURE, CASE_04_HIGH_SCORE_DECLINING, "
        "CASE_05_LOW_SCORE_IMPROVING, CASE_06_INSUFFICIENT_HISTORY, "
        "CASE_07_CONFLICTING_SIGNALS, CASE_08_INEFFECTIVE_REINFORCEMENT\n\n"
        "**Does not modify any data.**"
    ),
)
def run_test_case(case_name: str) -> TestCaseDetailResponse:
    try:
        ctx = get_case(case_name)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        result = run_decision_engine(ctx)
    except Exception as exc:
        logger.exception("Error running test case '%s'", case_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Engine error on test case '{case_name}': {exc}",
        ) from exc

    return TestCaseDetailResponse(
        case_name=case_name,
        context=ctx.model_dump(),
        result=result,
    )
