"""
Test suite — Workflow 1: Learner State & Dataset Management
===========================================================

Coverage matrix
---------------
 TC-01  Valid activity submission (first attempt)           → 201, status="created"
 TC-02  Valid activity submission (second attempt)          → 200, status="updated"
 TC-03  Invalid score: -1                                   → 422
 TC-04  Invalid score: 101                                  → 422
 TC-05  Invalid time: -5                                    → 422
 TC-06  Unknown learner                                     → 404 LEARNER_NOT_FOUND
 TC-07  Unknown course                                      → 404 COURSE_NOT_FOUND
 TC-08  Unknown lesson                                      → 404 LESSON_NOT_FOUND
 TC-09  Lesson belongs to a different course                → 409 LESSON_COURSE_MISMATCH
 TC-10  Duplicate submission (same idempotency_key)         → 200, status="duplicate"
 TC-11  Progress retrieval (GET endpoint)                   → 200 with full shape
 TC-12  Progress retrieval — unknown learner                → 404
 TC-13  Progress retrieval — unknown course                 → 404
 TC-14  Missing required field (learner_id)                 → 422
 TC-15  Wrong type for score (string)                       → 422
 TC-16  completed sent as string "true" (not JSON bool)     → 422
 TC-17  Boundary score = 0                                  → 201
 TC-18  Boundary score = 100                                → 201, mastery achieved
 TC-19  Attempt count increments correctly on second submit
 TC-20  Learning velocity computed correctly
 TC-21  Transaction rollback: service raises after flush    (unit test)
 TC-22  Service get_lesson_progress returns not_started     when no progress exists
 TC-23  Service get_assessment_history returns all attempts
 TC-24  Service get_learner_signals returns None signal     when none exists
 TC-25  Extra unknown fields in request body                → 422
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_attempt import AssessmentAttempt
from app.models.learner_progress import LearnerProgress
from app.models.learner_signal import LearnerSignal
from app.tests.conftest import make_course, make_learner, make_lesson
from app.workflows.progress.exceptions import (
    CourseNotFoundError,
    DatabaseError,
    LearnerNotFoundError,
    LessonCourseMismatchError,
    LessonNotFoundError,
)
from app.workflows.progress.service import (
    get_assessment_history,
    get_learner_signals,
    get_lesson_progress,
    record_activity,
)
from app.schemas.progress import ActivityRequest


# ============================================================================
# Helpers
# ============================================================================

def _activity_payload(**overrides) -> dict:
    base = {
        "learner_id": 1,
        "course_id": 1,
        "lesson_id": 1,
        "score": 72.0,
        "time_spent_minutes": 25.0,
        "completed": True,
    }
    base.update(overrides)
    return base


async def _seed_basic(session: AsyncSession) -> None:
    """Insert one learner, one course, one lesson."""
    await make_learner(session)
    await make_course(session)
    await make_lesson(session)


# ============================================================================
# TC-01  Valid first attempt → 201 created
# ============================================================================

@pytest.mark.asyncio
async def test_tc01_valid_first_attempt(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post("/api/v1/progress/activities", json=_activity_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "created"
    assert body["learner_id"] == 1
    assert body["lesson_id"] == 1
    assert body["score"] == 72.0
    assert body["attempt_number"] == 1
    assert "progress_id" in body


# ============================================================================
# TC-02  Valid second attempt → 200 updated
# ============================================================================

@pytest.mark.asyncio
async def test_tc02_valid_second_attempt(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)

    # First attempt
    r1 = await client.post("/api/v1/progress/activities", json=_activity_payload(score=60.0))
    assert r1.status_code == 201

    # Second attempt (no idempotency key, different score)
    r2 = await client.post("/api/v1/progress/activities", json=_activity_payload(score=78.0))
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "updated"
    assert body["attempt_number"] == 2
    assert body["score"] == 78.0


# ============================================================================
# TC-03  Score = -1 → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc03_invalid_score_negative(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post("/api/v1/progress/activities", json=_activity_payload(score=-1))
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-04  Score = 101 → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc04_invalid_score_above_100(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post("/api/v1/progress/activities", json=_activity_payload(score=101))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-05  Negative time → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc05_negative_time(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(time_spent_minutes=-5),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-06  Unknown learner → 404 LEARNER_NOT_FOUND
# ============================================================================

@pytest.mark.asyncio
async def test_tc06_unknown_learner(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(learner_id=9999),
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "LEARNER_NOT_FOUND"
    assert "9999" in body["error"]["message"]


# ============================================================================
# TC-07  Unknown course → 404 COURSE_NOT_FOUND
# ============================================================================

@pytest.mark.asyncio
async def test_tc07_unknown_course(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(course_id=9999),
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "COURSE_NOT_FOUND"


# ============================================================================
# TC-08  Unknown lesson → 404 LESSON_NOT_FOUND
# ============================================================================

@pytest.mark.asyncio
async def test_tc08_unknown_lesson(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(lesson_id=9999),
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "LESSON_NOT_FOUND"


# ============================================================================
# TC-09  Lesson belongs to a different course → 409 LESSON_COURSE_MISMATCH
# ============================================================================

@pytest.mark.asyncio
async def test_tc09_lesson_course_mismatch(client: AsyncClient, db_session: AsyncSession):
    await make_learner(db_session)
    # Two separate courses
    await make_course(db_session, id=1, title="Course A")
    await make_course(db_session, id=2, title="Course B")
    # Lesson belongs to course 2
    await make_lesson(db_session, id=1, course_id=2)

    # But we tell the API it belongs to course 1
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(course_id=1, lesson_id=1),
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "LESSON_COURSE_MISMATCH"
    assert body["error"]["details"]["supplied_course_id"] == 1
    assert body["error"]["details"]["actual_course_id"] == 2


# ============================================================================
# TC-10  Duplicate idempotency key → 200 duplicate
# ============================================================================

@pytest.mark.asyncio
async def test_tc10_duplicate_idempotency_key(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    key = str(uuid.uuid4())
    payload = _activity_payload(idempotency_key=key)

    r1 = await client.post("/api/v1/progress/activities", json=payload)
    assert r1.status_code == 201

    # Same key again — must not create a second attempt
    r2 = await client.post("/api/v1/progress/activities", json=payload)
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "duplicate"

    # Flush and expire to ensure the identity map is synced with the connection.
    await db_session.flush()
    db_session.expire_all()
    result = await db_session.execute(
        select(AssessmentAttempt).where(AssessmentAttempt.idempotency_key == key)
    )
    attempts = result.scalars().all()
    assert len(attempts) == 1


# ============================================================================
# TC-11  GET progress endpoint returns full shape
# ============================================================================

@pytest.mark.asyncio
async def test_tc11_get_progress(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    # Create some progress first
    await client.post("/api/v1/progress/activities", json=_activity_payload(score=80.0))

    resp = await client.get("/api/v1/progress/1/1")
    assert resp.status_code == 200
    body = resp.json()

    assert body["learner_id"] == 1
    assert body["course_id"] == 1
    assert "learner_name" in body
    assert "course_title" in body
    assert "overall_completion_percentage" in body
    assert "total_lessons" in body
    assert "lessons" in body
    assert len(body["lessons"]) == 1
    lesson = body["lessons"][0]
    assert lesson["lesson_id"] == 1
    assert lesson["current_score"] == 80.0
    assert lesson["attempt_count"] == 1
    assert "signals" in body
    assert "recent_attempts" in body
    assert len(body["recent_attempts"]) == 1


# ============================================================================
# TC-12  GET progress — unknown learner → 404
# ============================================================================

@pytest.mark.asyncio
async def test_tc12_get_progress_unknown_learner(client: AsyncClient, db_session: AsyncSession):
    await make_course(db_session)
    resp = await client.get("/api/v1/progress/9999/1")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEARNER_NOT_FOUND"


# ============================================================================
# TC-13  GET progress — unknown course → 404
# ============================================================================

@pytest.mark.asyncio
async def test_tc13_get_progress_unknown_course(client: AsyncClient, db_session: AsyncSession):
    await make_learner(db_session)
    resp = await client.get("/api/v1/progress/1/9999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COURSE_NOT_FOUND"


# ============================================================================
# TC-14  Missing required field (learner_id) → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc14_missing_required_field(client: AsyncClient, db_session: AsyncSession):
    payload = _activity_payload()
    del payload["learner_id"]
    resp = await client.post("/api/v1/progress/activities", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-15  Score sent as string → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc15_score_as_string(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        "/api/v1/progress/activities",
        json=_activity_payload(score="seventy-two"),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-16  completed sent as string "true" → 422
# ============================================================================

@pytest.mark.asyncio
async def test_tc16_completed_as_string(client: AsyncClient, db_session: AsyncSession):
    # Send raw JSON where completed is the string "true"
    import json
    raw = json.dumps(_activity_payload(completed="true"))
    resp = await client.post(
        "/api/v1/progress/activities",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-17  Boundary score = 0 → 201
# ============================================================================

@pytest.mark.asyncio
async def test_tc17_boundary_score_zero(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post("/api/v1/progress/activities", json=_activity_payload(score=0))
    assert resp.status_code == 201
    assert resp.json()["score"] == 0.0


# ============================================================================
# TC-18  Boundary score = 100 → 201, mastery achieved
# ============================================================================

@pytest.mark.asyncio
async def test_tc18_boundary_score_100_mastery(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post("/api/v1/progress/activities", json=_activity_payload(score=100))
    assert resp.status_code == 201

    # Confirm mastery_status = mastered in progress row
    result = await db_session.execute(
        select(LearnerProgress).where(
            LearnerProgress.learner_id == 1,
            LearnerProgress.lesson_id == 1,
        )
    )
    prog = result.scalars().first()
    assert prog is not None
    assert prog.mastery_status.value == "mastered"


# ============================================================================
# TC-19  Attempt count increments correctly
# ============================================================================

@pytest.mark.asyncio
async def test_tc19_attempt_count_increments(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    for i, score in enumerate([55.0, 65.0, 72.0], start=1):
        r = await client.post("/api/v1/progress/activities", json=_activity_payload(score=score))
        # 1st → 201, rest → 200
        assert r.status_code in (200, 201)
        assert r.json()["attempt_number"] == i

    result = await db_session.execute(
        select(LearnerProgress).where(LearnerProgress.learner_id == 1)
    )
    prog = result.scalars().first()
    assert prog.attempt_count == 3


# ============================================================================
# TC-20  Learning velocity reflects score improvement
# ============================================================================

@pytest.mark.asyncio
async def test_tc20_learning_velocity(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    await client.post("/api/v1/progress/activities", json=_activity_payload(score=50.0))
    await client.post("/api/v1/progress/activities", json=_activity_payload(score=70.0))
    await client.post("/api/v1/progress/activities", json=_activity_payload(score=90.0))

    result = await db_session.execute(
        select(LearnerProgress).where(LearnerProgress.learner_id == 1)
    )
    prog = result.scalars().first()
    # velocity = (90 - 50) / (3 - 1) = 20
    assert prog.learning_velocity == 20.0


# ============================================================================
# TC-21  Transaction rollback — DB error mid-transaction (unit test)
#
# We simulate a SQLAlchemy failure on the *second* flush call (which occurs
# after the AssessmentAttempt is inserted but before LearnerProgress is
# written).  The service must catch this, rollback, and raise DatabaseError.
# After the rollback no LearnerProgress row should exist.
# ============================================================================

@pytest.mark.asyncio
async def test_tc21_transaction_rollback_on_db_error(db_session: AsyncSession):
    await _seed_basic(db_session)
    request = ActivityRequest(
        learner_id=1,
        course_id=1,
        lesson_id=1,
        score=75.0,
        time_spent_minutes=20.0,
        completed=True,
    )

    original_flush = db_session.flush
    flush_call_count = 0

    async def _failing_flush(*args, **kwargs):
        nonlocal flush_call_count
        flush_call_count += 1
        if flush_call_count == 2:
            # Second flush = after progress object added → simulate DB error
            raise SQLAlchemyError("simulated flush failure")
        return await original_flush(*args, **kwargs)

    db_session.flush = _failing_flush  # type: ignore[method-assign]

    with pytest.raises(DatabaseError):
        await record_activity(db_session, request)

    # Restore
    db_session.flush = original_flush  # type: ignore[method-assign]

    # After rollback no progress row should persist
    result = await db_session.execute(
        select(LearnerProgress).where(LearnerProgress.learner_id == 1)
    )
    assert result.scalars().first() is None


# ============================================================================
# TC-22  Service get_lesson_progress returns not_started context
# ============================================================================

@pytest.mark.asyncio
async def test_tc22_lesson_progress_not_started(db_session: AsyncSession):
    await _seed_basic(db_session)
    ctx = await get_lesson_progress(db_session, learner_id=1, lesson_id=1)
    assert ctx.status == "not_started"
    assert ctx.attempt_count == 0
    assert ctx.current_score is None
    assert ctx.mastery_status == "not_attempted"


# ============================================================================
# TC-23  Service get_assessment_history returns all attempts
# ============================================================================

@pytest.mark.asyncio
async def test_tc23_assessment_history(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    for score in [50.0, 65.0, 80.0]:
        await client.post("/api/v1/progress/activities", json=_activity_payload(score=score))

    ctx = await get_assessment_history(db_session, learner_id=1, lesson_id=1)
    assert len(ctx.attempts) == 3
    scores = [a.score for a in ctx.attempts]
    assert 50.0 in scores
    assert 80.0 in scores


# ============================================================================
# TC-24  Service get_learner_signals returns None when no signal exists
# ============================================================================

@pytest.mark.asyncio
async def test_tc24_signals_none_when_missing(db_session: AsyncSession):
    await _seed_basic(db_session)
    ctx = await get_learner_signals(db_session, learner_id=1, lesson_id=1)
    assert ctx.signal is None


# ============================================================================
# TC-25  Extra unknown fields in request body → 422 (extra=forbid)
# ============================================================================

@pytest.mark.asyncio
async def test_tc25_extra_fields_rejected(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.post(
        "/api/v1/progress/activities",
        json={**_activity_payload(), "unexpected_field": "should_fail"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================================================
# TC-26  Signal is created and populated after first attempt
# ============================================================================

@pytest.mark.asyncio
async def test_tc26_signal_created_after_attempt(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    await client.post("/api/v1/progress/activities", json=_activity_payload(score=45.0))

    ctx = await get_learner_signals(db_session, learner_id=1, lesson_id=1)
    assert ctx.signal is not None
    # Score 45 is below mastery threshold 70 → should flag low_score
    assert "low_score" in ctx.signal.risk_flags


# ============================================================================
# TC-27  GET progress returns not_started lesson when no activity recorded
# ============================================================================

@pytest.mark.asyncio
async def test_tc27_get_progress_no_activity(client: AsyncClient, db_session: AsyncSession):
    await _seed_basic(db_session)
    resp = await client.get("/api/v1/progress/1/1")
    assert resp.status_code == 200
    body = resp.json()
    lesson = body["lessons"][0]
    assert lesson["status"] == "not_started"
    assert lesson["attempt_count"] == 0
    assert lesson["current_score"] is None


# ============================================================================
# TC-28  LessonNotFoundError raised for unknown lesson in service
# ============================================================================

@pytest.mark.asyncio
async def test_tc28_service_raises_lesson_not_found(db_session: AsyncSession):
    await make_learner(db_session)
    await make_course(db_session)
    # No lesson added
    request = ActivityRequest(
        learner_id=1,
        course_id=1,
        lesson_id=999,
        score=70.0,
        time_spent_minutes=20.0,
        completed=True,
    )
    with pytest.raises(LessonNotFoundError):
        await record_activity(db_session, request)
