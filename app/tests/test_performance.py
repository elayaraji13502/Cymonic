"""
Comprehensive test suite for Workflow 2 — Context & Performance Analysis.

Tests use an in-memory SQLite database so no PostgreSQL instance is required.

Coverage
--------
* Trend calculation (unit)
* Mastery evaluation (unit)
* Full analyzer integration (via build_learner_context)
* API endpoints (via FastAPI TestClient)

All tests verify that the workflow produces CONTEXT, not a final decision.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.shared import (
    AssessmentRecord,
    Course,
    InterventionHistory,
    Learner,
    Lesson,
    LearnerProgress,
)
from app.workflows.performance.context_builder import build_learner_context
from app.workflows.performance.mastery import evaluate_mastery
from app.workflows.performance.trend import calculate_trend

# ---------------------------------------------------------------------------
# Test database setup (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

# StaticPool ensures all connections share the same in-memory database,
# which is required for SQLite in-memory databases used across multiple
# connections (e.g. the test session and the TestClient ASGI app).
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db() -> Session:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    """FastAPI test client with the test DB injected."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_learner(db: Session, learner_id: int = 1) -> Learner:
    learner = Learner(id=learner_id, name="Test Learner", email=f"learner{learner_id}@test.com")
    db.add(learner)
    db.flush()
    return learner


def make_course(db: Session, course_id: int = 1, certification_required: bool = False) -> Course:
    course = Course(id=course_id, title="Test Course", certification_required=certification_required)
    db.add(course)
    db.flush()
    return course


def make_lesson(
    db: Session,
    lesson_id: int = 1,
    course_id: int = 1,
    mastery_threshold: float = 70.0,
    difficulty: int = 3,
) -> Lesson:
    lesson = Lesson(
        id=lesson_id,
        course_id=course_id,
        title="Test Lesson",
        difficulty=difficulty,
        mastery_threshold=mastery_threshold,
        sequence_order=1,
        is_required=True,
    )
    db.add(lesson)
    db.flush()
    return lesson


def make_progress(
    db: Session,
    learner_id: int = 1,
    lesson_id: int = 1,
    latest_score: Optional[float] = None,
    average_score: Optional[float] = None,
    attempt_count: int = 0,
    engagement_level: Optional[str] = None,
    risk_flags: Optional[List[str]] = None,
    strength_tags: Optional[List[str]] = None,
    weakness_tags: Optional[List[str]] = None,
    learning_velocity: Optional[float] = None,
    completion_percentage: float = 0.0,
    time_spent_seconds: int = 0,
) -> LearnerProgress:
    progress = LearnerProgress(
        learner_id=learner_id,
        lesson_id=lesson_id,
        latest_score=latest_score,
        average_score=average_score,
        attempt_count=attempt_count,
        engagement_level=engagement_level,
        risk_flags=json.dumps(risk_flags) if risk_flags else None,
        strength_tags=json.dumps(strength_tags) if strength_tags else None,
        weakness_tags=json.dumps(weakness_tags) if weakness_tags else None,
        learning_velocity=learning_velocity,
        completion_percentage=completion_percentage,
        time_spent_seconds=time_spent_seconds,
    )
    db.add(progress)
    db.flush()
    return progress


def make_assessment(
    db: Session,
    learner_id: int = 1,
    lesson_id: int = 1,
    score: float = 70.0,
    minutes_ago: int = 0,
) -> AssessmentRecord:
    rec = AssessmentRecord(
        learner_id=learner_id,
        lesson_id=lesson_id,
        score=score,
        attempted_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(rec)
    db.flush()
    return rec


def make_intervention(
    db: Session,
    learner_id: int = 1,
    lesson_id: int = 1,
    intervention_type: str = "reinforce",
    score_at: float = 60.0,
    score_after: Optional[float] = None,
    was_effective: Optional[bool] = None,
    minutes_ago: int = 0,
) -> InterventionHistory:
    rec = InterventionHistory(
        learner_id=learner_id,
        lesson_id=lesson_id,
        intervention_type=intervention_type,
        score_at_intervention=score_at,
        score_after_intervention=score_after,
        was_effective=was_effective,
        applied_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(rec)
    db.flush()
    return rec


# ===========================================================================
# UNIT TESTS — Trend Calculator
# ===========================================================================


class TestTrendCalculator:
    def test_no_scores_returns_insufficient_data(self):
        assert calculate_trend([]) == "insufficient_data"

    def test_one_score_returns_insufficient_data(self):
        assert calculate_trend([75.0]) == "insufficient_data"

    def test_two_improving_scores(self):
        assert calculate_trend([60.0, 75.0]) == "improving"

    def test_two_declining_scores(self):
        assert calculate_trend([80.0, 65.0]) == "declining"

    def test_two_stable_scores(self):
        assert calculate_trend([70.0, 71.0]) == "stable"

    def test_multiple_improving_scores(self):
        # 58 → 62 → 68 — clearly improving
        assert calculate_trend([58.0, 62.0, 68.0]) == "improving"

    def test_multiple_declining_scores(self):
        # 90 → 84 → 76 — clearly declining
        assert calculate_trend([90.0, 84.0, 76.0]) == "declining"

    def test_stable_scores(self):
        # 80 → 81 → 79 — within noise threshold
        assert calculate_trend([80.0, 81.0, 79.0]) == "stable"

    def test_longer_improving_sequence(self):
        assert calculate_trend([50.0, 55.0, 60.0, 65.0, 72.0]) == "improving"

    def test_longer_declining_sequence(self):
        assert calculate_trend([85.0, 80.0, 74.0, 68.0, 60.0]) == "declining"

    def test_trend_does_not_use_only_latest_score(self):
        # Latest score is high but overall trend is declining
        result = calculate_trend([90.0, 85.0, 78.0, 70.0, 95.0])
        # The single high latest score should not flip the trend to "improving"
        # Early mean ≈ 87.5, recent mean ≈ 81.0 → declining
        assert result == "declining"


# ===========================================================================
# UNIT TESTS — Mastery Evaluator
# ===========================================================================


class TestMasteryEvaluator:
    def test_no_scores_returns_insufficient_data(self):
        status, evidence = evaluate_mastery([], 70.0, None)
        assert status == "insufficient_data"
        assert "No valid" in evidence

    def test_one_score_above_threshold_returns_approaching(self):
        # Single score above threshold — cannot claim mastered
        status, evidence = evaluate_mastery([80.0], 70.0, 80.0)
        assert status == "approaching"
        assert "one attempt" in evidence.lower()

    def test_one_score_below_threshold_returns_not_mastered(self):
        status, evidence = evaluate_mastery([50.0], 70.0, 50.0)
        assert status == "not_mastered"

    def test_mastery_achieved_consistently(self):
        status, evidence = evaluate_mastery([75.0, 78.0, 80.0], 70.0, 80.0)
        assert status == "mastered"
        assert "mastery" in evidence.lower()

    def test_approaching_mastery(self):
        # Recent mean 74 >= approaching_floor (80*0.90=72) but below threshold 80
        status, evidence = evaluate_mastery([68.0, 74.0, 74.0], 80.0, 74.0)
        assert status == "approaching"

    def test_not_mastered_clearly_below(self):
        status, evidence = evaluate_mastery([40.0, 45.0, 50.0], 70.0, 50.0)
        assert status == "not_mastered"

    def test_single_high_score_does_not_claim_mastery(self):
        # One unusually high score amid low scores — should not claim mastered
        status, _ = evaluate_mastery([40.0, 45.0, 95.0], 70.0, 95.0)
        # Recent mean is (45+95)/2 = 70 but spread is 50 — inconsistent
        assert status in ("approaching", "not_mastered")

    def test_mastery_evidence_is_always_returned(self):
        _, evidence = evaluate_mastery([75.0, 80.0, 85.0], 70.0, 85.0)
        assert isinstance(evidence, str)
        assert len(evidence) > 0

    def test_inconsistent_scores_above_threshold_not_mastered(self):
        # High variance — mastery not confirmed
        status, evidence = evaluate_mastery([72.0, 40.0, 90.0], 70.0, 90.0)
        assert status in ("approaching", "not_mastered")
        assert "inconsistent" in evidence.lower() or "spread" in evidence.lower() or "not yet" in evidence.lower()


# ===========================================================================
# INTEGRATION TESTS — build_learner_context
# ===========================================================================


class TestBuildLearnerContext:
    def _setup_base(
        self,
        db: Session,
        scores: Optional[List[float]] = None,
        engagement_level: Optional[str] = "high",
        mastery_threshold: float = 70.0,
        certification_required: bool = False,
        risk_flags: Optional[List[str]] = None,
        strength_tags: Optional[List[str]] = None,
        weakness_tags: Optional[List[str]] = None,
    ):
        make_learner(db)
        make_course(db, certification_required=certification_required)
        make_lesson(db, mastery_threshold=mastery_threshold)
        make_progress(
            db,
            engagement_level=engagement_level,
            risk_flags=risk_flags,
            strength_tags=strength_tags,
            weakness_tags=weakness_tags,
        )
        if scores:
            for i, score in enumerate(scores):
                make_assessment(db, score=score, minutes_ago=len(scores) - i)
        db.commit()

    # --- No assessment history ---
    def test_no_scores_trend_insufficient_data(self, db: Session):
        self._setup_base(db, scores=[])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.trend == "insufficient_data"
        assert ctx.mastery.status == "insufficient_data"
        assert ctx.performance.latest_score is None

    # --- One score ---
    def test_one_score_trend_insufficient_data(self, db: Session):
        self._setup_base(db, scores=[65.0])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.trend == "insufficient_data"
        assert ctx.performance.latest_score == 65.0

    # --- Improving scores ---
    def test_improving_scores(self, db: Session):
        self._setup_base(db, scores=[55.0, 62.0, 70.0])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.trend == "improving"

    # --- Declining scores ---
    def test_declining_scores(self, db: Session):
        self._setup_base(db, scores=[85.0, 78.0, 68.0])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.trend == "declining"

    # --- Stable scores ---
    def test_stable_scores(self, db: Session):
        self._setup_base(db, scores=[72.0, 73.0, 71.0])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.trend == "stable"

    # --- Mastery achieved ---
    def test_mastery_achieved(self, db: Session):
        self._setup_base(db, scores=[75.0, 78.0, 82.0], mastery_threshold=70.0)
        ctx = build_learner_context(db, 1, 1)
        assert ctx.mastery.status == "mastered"
        assert ctx.mastery.threshold == 70.0

    # --- Mastery approaching ---
    def test_mastery_approaching(self, db: Session):
        # Recent mean 74 >= approaching_floor (80*0.90=72) but below threshold 80
        self._setup_base(db, scores=[68.0, 74.0, 74.0], mastery_threshold=80.0)
        ctx = build_learner_context(db, 1, 1)
        assert ctx.mastery.status == "approaching"

    # --- Mastery not reached ---
    def test_mastery_not_reached(self, db: Session):
        self._setup_base(db, scores=[40.0, 45.0, 50.0], mastery_threshold=70.0)
        ctx = build_learner_context(db, 1, 1)
        assert ctx.mastery.status == "not_mastered"

    # --- Missing engagement ---
    def test_missing_engagement_returns_unknown(self, db: Session):
        self._setup_base(db, scores=[65.0, 70.0], engagement_level=None)
        ctx = build_learner_context(db, 1, 1)
        assert ctx.engagement.status == "unknown"

    # --- No progress record ---
    def test_no_progress_record_raises_lookup_error(self, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        db.commit()
        with pytest.raises(LookupError):
            build_learner_context(db, 1, 1)

    # --- Missing mastery threshold ---
    def test_missing_mastery_threshold_raises_value_error(self, db: Session):
        make_learner(db)
        make_course(db)
        lesson = Lesson(
            id=1,
            course_id=1,
            title="No Threshold Lesson",
            difficulty=3,
            mastery_threshold=None,  # type: ignore[arg-type]
            sequence_order=1,
        )
        db.add(lesson)
        make_progress(db)
        db.commit()
        with pytest.raises(ValueError, match="mastery_threshold"):
            build_learner_context(db, 1, 1)

    # --- Previous reinforcement (intervention history) ---
    def test_previous_reinforcement_recorded(self, db: Session):
        self._setup_base(db, scores=[60.0, 65.0])
        make_intervention(db, intervention_type="reinforce", score_at=60.0, was_effective=True)
        db.commit()
        ctx = build_learner_context(db, 1, 1)
        assert ctx.intervention.history_count == 1
        assert ctx.intervention.last_intervention_type == "reinforce"
        assert ctx.intervention.effectiveness == "effective"

    # --- Failed reinforcement ---
    def test_failed_reinforcement(self, db: Session):
        self._setup_base(db, scores=[55.0, 52.0])
        make_intervention(db, intervention_type="reinforce", score_at=58.0, was_effective=False)
        db.commit()
        ctx = build_learner_context(db, 1, 1)
        assert ctx.intervention.effectiveness == "ineffective"

    # --- Missing intervention history ---
    def test_no_intervention_history(self, db: Session):
        self._setup_base(db, scores=[65.0, 70.0])
        ctx = build_learner_context(db, 1, 1)
        assert ctx.intervention.effectiveness == "none"
        assert ctx.intervention.history_count == 0

    # --- High certification risk ---
    def test_high_certification_risk(self, db: Session):
        self._setup_base(
            db,
            scores=[40.0, 42.0, 38.0],
            mastery_threshold=70.0,
            certification_required=True,
        )
        ctx = build_learner_context(db, 1, 1)
        assert ctx.certification.required is True
        assert ctx.certification.risk == "high"

    # --- Low certification risk when mastered ---
    def test_low_certification_risk_when_mastered(self, db: Session):
        self._setup_base(
            db,
            scores=[75.0, 80.0, 82.0],
            mastery_threshold=70.0,
            certification_required=True,
        )
        ctx = build_learner_context(db, 1, 1)
        assert ctx.certification.risk == "low"

    # --- Conflicting signals ---
    def test_conflicting_signals_preserved(self, db: Session):
        # Low engagement but improving scores — a genuine conflict
        self._setup_base(
            db,
            scores=[55.0, 62.0, 70.0],
            engagement_level="low",
        )
        ctx = build_learner_context(db, 1, 1)
        assert "low_engagement_with_improving_scores" in ctx.conflicting_signals

    # --- Corrupted / invalid historical records ---
    def test_corrupted_scores_excluded_and_flagged(self, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        make_progress(db)
        # Valid scores
        make_assessment(db, score=65.0, minutes_ago=3)
        make_assessment(db, score=70.0, minutes_ago=2)
        # Corrupted scores (outside 0–100)
        make_assessment(db, score=150.0, minutes_ago=1)
        make_assessment(db, score=-5.0, minutes_ago=0)
        db.commit()
        ctx = build_learner_context(db, 1, 1)
        assert ctx.performance.corrupted_score_count == 2
        assert ctx.performance.attempt_count == 4  # all deduped records counted
        # 2 valid scores [65, 70] → trend is computed (delta=5 ≥ threshold → improving)
        assert ctx.performance.trend == "improving"

    # --- Large attempt history (bounded query) ---
    def test_large_history_handled(self, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        make_progress(db)
        # Insert 250 records — only MAX_ASSESSMENT_RECORDS (200) should be loaded
        for i in range(250):
            make_assessment(db, score=float(50 + (i % 30)), minutes_ago=250 - i)
        db.commit()
        ctx = build_learner_context(db, 1, 1)
        # Should not crash and attempt_count should be bounded
        assert ctx.performance.attempt_count <= 200

    # --- Duplicate assessment records ---
    def test_duplicate_records_deduplicated(self, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        make_progress(db)
        ts = datetime(2024, 1, 1, 12, 0, 0)
        # Two identical records
        db.add(AssessmentRecord(learner_id=1, lesson_id=1, score=70.0, attempted_at=ts))
        db.add(AssessmentRecord(learner_id=1, lesson_id=1, score=70.0, attempted_at=ts))
        db.add(AssessmentRecord(learner_id=1, lesson_id=1, score=80.0, attempted_at=ts + timedelta(hours=1)))
        db.commit()
        ctx = build_learner_context(db, 1, 1)
        # Duplicate should be removed — only 2 unique records
        assert ctx.performance.attempt_count == 2

    # --- No final decision in output ---
    def test_no_final_decision_in_context(self, db: Session):
        self._setup_base(db, scores=[60.0, 65.0, 70.0])
        ctx = build_learner_context(db, 1, 1)
        ctx_dict = ctx.model_dump()
        # Ensure no decision field exists
        assert "decision" not in ctx_dict
        assert "recommendation" not in ctx_dict
        assert "action" not in ctx_dict

    # --- Output is deterministic ---
    def test_output_is_deterministic(self, db: Session):
        self._setup_base(db, scores=[60.0, 65.0, 70.0])
        ctx1 = build_learner_context(db, 1, 1)
        ctx2 = build_learner_context(db, 1, 1)
        assert ctx1.model_dump() == ctx2.model_dump()

    # --- Strength and weakness tags propagated ---
    def test_tags_propagated(self, db: Session):
        self._setup_base(
            db,
            scores=[70.0, 75.0],
            strength_tags=["problem_solving"],
            weakness_tags=["time_management"],
        )
        ctx = build_learner_context(db, 1, 1)
        assert "problem_solving" in ctx.strength_tags
        assert "time_management" in ctx.weakness_tags


# ===========================================================================
# API ENDPOINT TESTS
# ===========================================================================


class TestPerformanceAPI:
    def _seed(
        self,
        db: Session,
        scores: Optional[List[float]] = None,
        engagement_level: Optional[str] = "high",
        mastery_threshold: float = 70.0,
        certification_required: bool = False,
    ):
        make_learner(db)
        make_course(db, certification_required=certification_required)
        make_lesson(db, mastery_threshold=mastery_threshold)
        make_progress(db, engagement_level=engagement_level)
        if scores:
            for i, score in enumerate(scores):
                make_assessment(db, score=score, minutes_ago=len(scores) - i)
        db.commit()

    # --- GET endpoint happy path ---
    def test_get_returns_context_package(self, client: TestClient, db: Session):
        self._seed(db, scores=[60.0, 65.0, 70.0])
        resp = client.get("/api/v1/performance/1/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["learner_id"] == 1
        assert data["lesson_id"] == 1
        assert "performance" in data
        assert "mastery" in data
        assert "engagement" in data
        assert "intervention" in data
        assert "certification" in data

    # --- GET endpoint 404 ---
    def test_get_returns_404_for_missing_progress(self, client: TestClient, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        db.commit()
        resp = client.get("/api/v1/performance/1/1")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    # --- GET endpoint 422 for missing threshold ---
    def test_get_returns_422_for_missing_threshold(self, client: TestClient, db: Session):
        make_learner(db)
        make_course(db)
        lesson = Lesson(
            id=1, course_id=1, title="No Threshold", difficulty=3,
            mastery_threshold=None, sequence_order=1,  # type: ignore[arg-type]
        )
        db.add(lesson)
        make_progress(db)
        db.commit()
        resp = client.get("/api/v1/performance/1/1")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "CONFIGURATION_ERROR"

    # --- POST /analyze happy path ---
    def test_post_analyze_returns_complete_status(self, client: TestClient, db: Session):
        self._seed(db, scores=[65.0, 70.0, 75.0])
        resp = client.post("/api/v1/performance/analyze", json={"learner_id": 1, "lesson_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_status"] == "complete"
        assert "learner_context" in data

    # --- POST /analyze 404 ---
    def test_post_analyze_returns_404_for_missing_learner(self, client: TestClient, db: Session):
        make_course(db)
        make_lesson(db)
        db.commit()
        resp = client.post("/api/v1/performance/analyze", json={"learner_id": 99, "lesson_id": 1})
        assert resp.status_code == 404

    # --- Response contains no final decision ---
    def test_api_response_contains_no_decision(self, client: TestClient, db: Session):
        self._seed(db, scores=[60.0, 65.0, 70.0])
        resp = client.get("/api/v1/performance/1/1")
        data = resp.json()
        assert "decision" not in data
        assert "recommendation" not in data

    # --- Trend signal in API response ---
    def test_api_trend_signal_present(self, client: TestClient, db: Session):
        self._seed(db, scores=[55.0, 62.0, 70.0])
        resp = client.get("/api/v1/performance/1/1")
        assert resp.json()["performance"]["trend"] == "improving"

    # --- Mastery signal in API response ---
    def test_api_mastery_signal_present(self, client: TestClient, db: Session):
        self._seed(db, scores=[75.0, 80.0, 82.0], mastery_threshold=70.0)
        resp = client.get("/api/v1/performance/1/1")
        assert resp.json()["mastery"]["status"] == "mastered"

    # --- Engagement unknown when missing ---
    def test_api_engagement_unknown_when_missing(self, client: TestClient, db: Session):
        self._seed(db, scores=[65.0, 70.0], engagement_level=None)
        resp = client.get("/api/v1/performance/1/1")
        assert resp.json()["engagement"]["status"] == "unknown"

    # --- Certification risk in response ---
    def test_api_certification_risk_present(self, client: TestClient, db: Session):
        self._seed(db, scores=[40.0, 42.0], mastery_threshold=70.0, certification_required=True)
        resp = client.get("/api/v1/performance/1/1")
        data = resp.json()
        assert data["certification"]["required"] is True
        assert data["certification"]["risk"] in ("low", "medium", "high")

    # --- Error format is correct ---
    def test_error_format_matches_contract(self, client: TestClient, db: Session):
        make_learner(db)
        make_course(db)
        make_lesson(db)
        db.commit()
        resp = client.get("/api/v1/performance/1/1")
        assert resp.status_code == 404
        error = resp.json()["detail"]["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error
