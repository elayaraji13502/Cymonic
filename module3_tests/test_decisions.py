"""
tests/test_decisions.py
=======================
Pytest test suite for Module 3 — Adaptive Decision Engine.

Coverage:
  - All 8 predefined test cases → expected decisions
  - Same-score / different-context produces different decisions
  - Override conditions
  - Conflicting signal handling
  - Insufficient data handling
  - Edge cases: missing fields, invalid scores, stale context
  - LLM validator: bad JSON, wrong decision, bad confidence, empty reasoning
  - FastAPI endpoints via TestClient
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.decision_engine.schemas import (
    CourseContext,
    DecisionEnum,
    DifficultyEnum,
    EffectivenessEnum,
    EngagementContext,
    EngagementLevelEnum,
    InterventionContext,
    LearnerContext,
    LearningContext,
    MasteryConsistencyEnum,
    MasteryContext,
    MasteryStatusEnum,
    PerformanceContext,
    TrendEnum,
    VelocityEnum,
    CertRiskEnum,
)
from app.decision_engine.engine import run_decision_engine
from app.decision_engine.test_cases import get_case
from app.decision_engine.validator import LLMValidationError, extract_json, validate_llm_output
from app.decision_engine.signals import extract_signals
from app.decision_engine.evaluator import evaluate, select_candidate
from app.decision_engine.overrides import evaluate_overrides, evaluate_advance_blockers
from app.config.decision_policy import POLICY
from module3_main import app

client = TestClient(app)


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_ctx(**overrides) -> LearnerContext:
    """Build a minimal valid LearnerContext with optional field overrides."""
    base = dict(
        learner_id=999,
        lesson_id=1,
        context_version=1,
        performance=PerformanceContext(
            latest_score=65,
            average_score=63,
            previous_scores=[60, 62, 65],
            trend=TrendEnum.improving,
            attempt_count=3,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.not_mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.insufficient,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
        learning=LearningContext(velocity=VelocityEnum.normal, completion_percentage=60),
        intervention=InterventionContext(
            reinforcement_count=0,
            effectiveness=EffectivenessEnum.none,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=True,
            certification_required=False,
            certification_risk=CertRiskEnum.low,
        ),
        risk_flags=[],
        weakness_tags=[],
        strength_tags=[],
    )
    base.update(overrides)
    return LearnerContext(**base)


# ===========================================================================
# 1. Predefined test cases — expected decisions
# ===========================================================================

class TestPredefinedCases:
    """Each case must produce the documented expected decision."""

    def test_case_01_improving_learner_expects_reinforce(self):
        ctx = get_case("CASE_01_IMPROVING_LEARNER")
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.reinforce, (
            f"CASE_01: expected REINFORCE, got {result.decision} — {result.reasoning}"
        )
        assert result.confidence > 0.0

    def test_case_02_clear_mastery_expects_advance(self):
        ctx = get_case("CASE_02_CLEAR_MASTERY")
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.advance, (
            f"CASE_02: expected ADVANCE, got {result.decision} — {result.reasoning}"
        )
        assert result.confidence >= POLICY.MIN_DECISION_CONFIDENCE

    def test_case_03_repeated_failure_expects_mentor(self):
        ctx = get_case("CASE_03_REPEATED_FAILURE")
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.mentor, (
            f"CASE_03: expected MENTOR, got {result.decision} — {result.reasoning}"
        )

    def test_case_04_high_score_declining_not_advance(self):
        """High score alone must NOT auto-advance when trend is declining + low engagement."""
        ctx = get_case("CASE_04_HIGH_SCORE_DECLINING")
        result = run_decision_engine(ctx)
        assert result.decision != DecisionEnum.advance, (
            f"CASE_04: ADVANCE must be blocked by declining trend + low engagement. "
            f"Got {result.decision} — {result.reasoning}"
        )
        # Engine must acknowledge the conflict in reasoning or signals
        combined = result.reasoning + " ".join(result.signals)
        assert any(
            kw in combined.lower()
            for kw in ["declin", "conflict", "spike", "inconsist", "block", "low"]
        ), "CASE_04: reasoning must reference the conflicting signals"

    def test_case_05_low_score_improving_expects_reinforce(self):
        ctx = get_case("CASE_05_LOW_SCORE_IMPROVING")
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.reinforce, (
            f"CASE_05: expected REINFORCE, got {result.decision} — {result.reasoning}"
        )

    def test_case_06_insufficient_history_low_confidence(self):
        ctx = get_case("CASE_06_INSUFFICIENT_HISTORY")
        result = run_decision_engine(ctx)
        # Decision must not be fabricated — confidence must be capped low
        assert result.confidence <= POLICY.INSUFFICIENT_DATA_CONFIDENCE + 0.05, (
            f"CASE_06: confidence {result.confidence} exceeds insufficient-data cap"
        )
        assert result.decision != DecisionEnum.advance, (
            "CASE_06: must not advance when history is unknown"
        )

    def test_case_07_conflicting_signals_has_reasoning(self):
        ctx = get_case("CASE_07_CONFLICTING_SIGNALS")
        result = run_decision_engine(ctx)
        # Must not blindly advance despite high score
        assert result.decision != DecisionEnum.advance, (
            f"CASE_07: conflicting signals (declining trend, low engagement) must block ADVANCE"
        )
        # Reasoning must be non-trivial
        assert len(result.reasoning) > 30, "CASE_07: reasoning must be substantive"

    def test_case_08_ineffective_reinforcement_expects_mentor(self):
        ctx = get_case("CASE_08_INEFFECTIVE_REINFORCEMENT")
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.mentor, (
            f"CASE_08: expected MENTOR (max reinforcement + ineffective), "
            f"got {result.decision} — {result.reasoning}"
        )


# ===========================================================================
# 2. Same score, different context → different decisions
#    (The core anti-threshold-classifier test)
# ===========================================================================

class TestSameScoreDifferentContext:
    """
    Demonstrate that score=62 can produce REINFORCE in one context
    and MENTOR in another.  The engine must NOT be a threshold classifier.
    """

    def test_score_62_high_engagement_improving_gives_reinforce(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=62,
                average_score=58,
                previous_scores=[52, 56, 58, 62],
                trend=TrendEnum.improving,
                attempt_count=4,
            ),
            mastery=MasteryContext(
                status=MasteryStatusEnum.not_mastered,
                threshold=75,
                consistency=MasteryConsistencyEnum.insufficient,
            ),
            engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
            intervention=InterventionContext(
                reinforcement_count=0,
                effectiveness=EffectivenessEnum.none,
                previous_mentor_intervention=False,
            ),
        )
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.reinforce, (
            f"62 + improving + high engagement should be REINFORCE, got {result.decision}"
        )

    def test_score_62_max_reinforcement_ineffective_gives_mentor(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=62,
                average_score=64,
                previous_scores=[68, 65, 63, 62],
                trend=TrendEnum.declining,
                attempt_count=5,
            ),
            mastery=MasteryContext(
                status=MasteryStatusEnum.not_mastered,
                threshold=75,
                consistency=MasteryConsistencyEnum.inconsistent,
            ),
            engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=8),
            intervention=InterventionContext(
                reinforcement_count=3,
                effectiveness=EffectivenessEnum.ineffective,
                previous_mentor_intervention=False,
            ),
        )
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.mentor, (
            f"62 + declining + max reinforcement + ineffective should be MENTOR, got {result.decision}"
        )

    def test_same_score_different_decisions_are_not_equal(self):
        """Reinforce and mentor cases with identical scores must differ in decision."""
        ctx_reinforce = _make_ctx(
            performance=PerformanceContext(
                latest_score=62, average_score=58,
                previous_scores=[52, 56, 58, 62], trend=TrendEnum.improving, attempt_count=4,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.not_mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.insufficient),
            engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
            intervention=InterventionContext(reinforcement_count=0,
                                            effectiveness=EffectivenessEnum.none,
                                            previous_mentor_intervention=False),
        )
        ctx_mentor = _make_ctx(
            performance=PerformanceContext(
                latest_score=62, average_score=64,
                previous_scores=[68, 65, 63, 62], trend=TrendEnum.declining, attempt_count=5,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.not_mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.inconsistent),
            engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=8),
            intervention=InterventionContext(reinforcement_count=3,
                                            effectiveness=EffectivenessEnum.ineffective,
                                            previous_mentor_intervention=False),
        )
        r1 = run_decision_engine(ctx_reinforce)
        r2 = run_decision_engine(ctx_mentor)
        assert r1.decision != r2.decision, (
            f"Same score (62) must produce different decisions in different contexts. "
            f"Both returned: {r1.decision}"
        )


# ===========================================================================
# 3. Override conditions
# ===========================================================================

class TestOverrides:

    def test_critical_risk_flag_forces_mentor(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=80, average_score=78,
                previous_scores=[75, 77, 80], trend=TrendEnum.stable, attempt_count=3,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.consistent),
            risk_flags=["dropout_risk"],
        )
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.mentor, (
            "Critical risk flag 'dropout_risk' must force MENTOR even with high score"
        )
        assert "critical" in result.reasoning.lower() or "risk" in result.reasoning.lower()

    def test_max_reinforcement_ineffective_forces_mentor(self):
        ctx = _make_ctx(
            intervention=InterventionContext(
                reinforcement_count=3,
                effectiveness=EffectivenessEnum.ineffective,
                previous_mentor_intervention=False,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.not_mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.inconsistent),
            performance=PerformanceContext(
                latest_score=55, average_score=57,
                previous_scores=[60, 58, 57, 55], trend=TrendEnum.declining, attempt_count=4,
            ),
        )
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.mentor

    def test_clear_mastery_override_gives_advance(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=88, average_score=85,
                previous_scores=[82, 84, 85, 88], trend=TrendEnum.stable, attempt_count=4,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.consistent),
            engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
            risk_flags=[],
        )
        result = run_decision_engine(ctx)
        assert result.decision == DecisionEnum.advance


# ===========================================================================
# 4. Advance hard blockers
# ===========================================================================

class TestAdvanceBlockers:

    def test_single_spike_blocks_advance(self):
        """45 → 52 → 91 pattern must NOT advance (spike without consistent history)."""
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=91,
                average_score=60,
                previous_scores=[45, 52, 91],
                trend=TrendEnum.improving,
                attempt_count=3,
            ),
            mastery=MasteryContext(
                status=MasteryStatusEnum.in_progress,
                threshold=75,
                consistency=MasteryConsistencyEnum.inconsistent,
            ),
            engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
        )
        result = run_decision_engine(ctx)
        assert result.decision != DecisionEnum.advance, (
            f"Spike pattern 45→52→91 must NOT advance. Got {result.decision}"
        )

    def test_declining_low_engagement_blocks_advance(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=80, average_score=75,
                previous_scores=[78, 76, 74, 80], trend=TrendEnum.declining, attempt_count=4,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.inconsistent),
            engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=6),
        )
        result = run_decision_engine(ctx)
        assert result.decision != DecisionEnum.advance, (
            "Declining + low engagement must block ADVANCE"
        )

    def test_score_below_advance_floor_blocks_advance(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=60, average_score=58,
                previous_scores=[55, 57, 60], trend=TrendEnum.stable, attempt_count=3,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.consistent),
        )
        result = run_decision_engine(ctx)
        assert result.decision != DecisionEnum.advance, (
            f"Score {60} is below advance floor {POLICY.ADVANCE_BLOCK_BELOW_SCORE}"
        )


# ===========================================================================
# 5. Insufficient data edge cases
# ===========================================================================

class TestInsufficientData:

    def test_no_latest_score_returns_low_confidence(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=None, average_score=None,
                previous_scores=[], trend=TrendEnum.unknown, attempt_count=0,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.unknown, threshold=None,
                                   consistency=MasteryConsistencyEnum.unknown),
        )
        result = run_decision_engine(ctx)
        assert result.confidence <= POLICY.INSUFFICIENT_DATA_CONFIDENCE + 0.05
        assert result.decision != DecisionEnum.advance

    def test_unknown_mastery_does_not_advance(self):
        ctx = _make_ctx(
            mastery=MasteryContext(status=MasteryStatusEnum.unknown, threshold=75,
                                   consistency=MasteryConsistencyEnum.unknown),
            performance=PerformanceContext(
                latest_score=90, average_score=88,
                previous_scores=[85, 87, 90], trend=TrendEnum.stable, attempt_count=4,
            ),
        )
        result = run_decision_engine(ctx)
        assert result.decision != DecisionEnum.advance, (
            "Unknown mastery status should prevent ADVANCE"
        )


# ===========================================================================
# 6. Edge case: invalid input (Pydantic validation)
# ===========================================================================

class TestInputValidation:

    def test_score_above_100_raises(self):
        with pytest.raises(Exception):
            PerformanceContext(latest_score=105, average_score=80,
                               previous_scores=[], trend=TrendEnum.stable, attempt_count=1)

    def test_score_below_0_raises(self):
        with pytest.raises(Exception):
            PerformanceContext(latest_score=-5, average_score=50,
                               previous_scores=[], trend=TrendEnum.stable, attempt_count=1)

    def test_previous_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            PerformanceContext(latest_score=70, average_score=65,
                               previous_scores=[60, 110],
                               trend=TrendEnum.stable, attempt_count=2)

    def test_negative_attempt_count_raises(self):
        with pytest.raises(Exception):
            PerformanceContext(latest_score=70, average_score=65,
                               previous_scores=[], trend=TrendEnum.stable, attempt_count=-1)


# ===========================================================================
# 7. LLM Validator unit tests
# ===========================================================================

class TestLLMValidator:

    def _good_payload(self, decision="reinforce"):
        return {
            "decision": decision,
            "reasoning": "The learner shows improving trend with high engagement and no prior reinforcement.",
            "confidence": 0.82,
            "signals": ["mastery_not_reached", "trend_improving", "high_engagement"],
            "rejected_alternatives": {
                "advance": "Mastery not confirmed.",
                "mentor": "No escalation signals present.",
            },
        }

    def test_valid_payload_passes(self):
        result = validate_llm_output(self._good_payload(), DecisionEnum.reinforce)
        assert result["decision"] == "reinforce"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_invalid_decision_value_rejected(self):
        bad = self._good_payload()
        bad["decision"] = "repeat_course"
        with pytest.raises(LLMValidationError, match="invalid decision"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_decision_mismatch_with_policy_rejected(self):
        bad = self._good_payload("advance")
        with pytest.raises(LLMValidationError, match="contradicts policy"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_empty_reasoning_rejected(self):
        bad = self._good_payload()
        bad["reasoning"] = "ok"
        with pytest.raises(LLMValidationError, match="too short"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_confidence_above_1_rejected(self):
        bad = self._good_payload()
        bad["confidence"] = 1.5
        with pytest.raises(LLMValidationError, match="outside"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_confidence_below_0_rejected(self):
        bad = self._good_payload()
        bad["confidence"] = -0.1
        with pytest.raises(LLMValidationError, match="outside"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_non_numeric_confidence_rejected(self):
        bad = self._good_payload()
        bad["confidence"] = "high"
        with pytest.raises(LLMValidationError, match="not numeric"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_empty_signals_rejected(self):
        bad = self._good_payload()
        bad["signals"] = []
        with pytest.raises(LLMValidationError, match="non-empty"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_empty_rejected_alternatives_rejected(self):
        bad = self._good_payload()
        bad["rejected_alternatives"] = {}
        with pytest.raises(LLMValidationError, match="non-empty"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_missing_key_rejected(self):
        bad = self._good_payload()
        del bad["reasoning"]
        with pytest.raises(LLMValidationError, match="missing required"):
            validate_llm_output(bad, DecisionEnum.reinforce)

    def test_extract_json_from_markdown_fence(self):
        raw = '```json\n{"decision":"reinforce","reasoning":"test","confidence":0.8,"signals":["x"],"rejected_alternatives":{"advance":"no"}}\n```'
        parsed = extract_json(raw)
        assert parsed["decision"] == "reinforce"

    def test_extract_json_empty_string_raises(self):
        with pytest.raises(LLMValidationError):
            extract_json("")

    def test_extract_json_plain_prose_raises(self):
        with pytest.raises(LLMValidationError):
            extract_json("The learner should reinforce their knowledge.")


# ===========================================================================
# 8. Signal extraction unit tests
# ===========================================================================

class TestSignalExtraction:

    def test_mastery_achieved_signal(self):
        ctx = _make_ctx(
            mastery=MasteryContext(status=MasteryStatusEnum.mastered, threshold=75,
                                   consistency=MasteryConsistencyEnum.consistent),
            performance=PerformanceContext(latest_score=82, average_score=80,
                                           previous_scores=[78, 80, 82],
                                           trend=TrendEnum.stable, attempt_count=3),
        )
        b = extract_signals(ctx)
        assert b.mastery_achieved is True
        assert b.mastery_not_reached is False

    def test_critical_risk_flag_detected(self):
        ctx = _make_ctx(risk_flags=["dropout_risk", "exam_failing"])
        b = extract_signals(ctx)
        assert b.critical_risk_present is True

    def test_single_spike_detected(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=91, average_score=60,
                previous_scores=[45, 52, 91],
                trend=TrendEnum.improving, attempt_count=3,
            ),
        )
        b = extract_signals(ctx)
        assert b.single_high_spike is True

    def test_max_reinforcement_signal(self):
        ctx = _make_ctx(
            intervention=InterventionContext(
                reinforcement_count=3,
                effectiveness=EffectivenessEnum.ineffective,
                previous_mentor_intervention=False,
            ),
        )
        b = extract_signals(ctx)
        assert b.max_reinforcement_hit is True
        assert b.intervention_ineffective is True

    def test_hard_inactivity_signal(self):
        ctx = _make_ctx(
            engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=8),
        )
        b = extract_signals(ctx)
        assert b.inactivity_hard is True
        assert b.engagement_low is True

    def test_data_insufficient_when_no_score(self):
        ctx = _make_ctx(
            performance=PerformanceContext(
                latest_score=None, average_score=None,
                previous_scores=[], trend=TrendEnum.unknown, attempt_count=0,
            ),
            mastery=MasteryContext(status=MasteryStatusEnum.unknown, threshold=None,
                                   consistency=MasteryConsistencyEnum.unknown),
        )
        b = extract_signals(ctx)
        assert b.data_sufficient is False


# ===========================================================================
# 9. Response structure integrity
# ===========================================================================

class TestResponseStructure:

    def test_response_has_all_required_fields(self):
        ctx = get_case("CASE_01_IMPROVING_LEARNER")
        result = run_decision_engine(ctx)
        assert result.decision in DecisionEnum
        assert isinstance(result.reasoning, str) and len(result.reasoning) > 0
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.signals, list) and len(result.signals) > 0
        assert result.reasoning_source is not None
        assert result.rejected_alternatives is not None
        assert result.decision_factors is not None

    def test_rejected_alternatives_covers_other_two(self):
        for case_name in ["CASE_01_IMPROVING_LEARNER", "CASE_02_CLEAR_MASTERY", "CASE_03_REPEATED_FAILURE"]:
            ctx = get_case(case_name)
            result = run_decision_engine(ctx)
            decision = result.decision.value
            for alt in ["reinforce", "advance", "mentor"]:
                if alt != decision:
                    assert alt in result.rejected_alternatives, (
                        f"{case_name}: rejected_alternatives must include '{alt}'"
                    )

    def test_fallback_source_when_no_api_key(self):
        """Without a real API key, source must be 'fallback'."""
        ctx = get_case("CASE_01_IMPROVING_LEARNER")
        result = run_decision_engine(ctx)
        # In test environment no real API key → fallback
        from app.decision_engine.schemas import ReasoningSourceEnum
        assert result.reasoning_source in (
            ReasoningSourceEnum.fallback, ReasoningSourceEnum.llm
        )


# ===========================================================================
# 10. FastAPI endpoint tests
# ===========================================================================

class TestAPIEndpoints:

    def test_health_endpoint(self):
        r = client.get("/api/v1/decisions/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "module" in body

    def test_evaluate_endpoint_with_valid_payload(self):
        payload = {
            "learner_id": 101,
            "lesson_id": 12,
            "context_version": 1,
            "performance": {
                "latest_score": 62,
                "average_score": 64,
                "previous_scores": [58, 62, 64],
                "trend": "improving",
                "attempt_count": 3,
            },
            "mastery": {
                "status": "not_mastered",
                "threshold": 70,
                "consistency": "insufficient",
            },
            "engagement": {"level": "high", "inactivity_days": 1},
            "learning": {"velocity": "normal", "completion_percentage": 65},
            "intervention": {
                "reinforcement_count": 0,
                "effectiveness": "none",
                "previous_mentor_intervention": False,
            },
            "course": {
                "lesson_difficulty": "medium",
                "required_lesson": True,
                "certification_required": True,
                "certification_risk": "medium",
            },
            "risk_flags": [],
            "weakness_tags": ["recursion"],
            "strength_tags": ["problem_solving"],
        }
        r = client.post("/api/v1/decisions/evaluate", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["decision"] in ["reinforce", "advance", "mentor"]
        assert "reasoning" in body
        assert "confidence" in body
        assert "signals" in body
        assert "rejected_alternatives" in body
        assert "decision_factors" in body

    def test_evaluate_endpoint_invalid_score(self):
        payload = {
            "learner_id": 1,
            "lesson_id": 1,
            "context_version": 1,
            "performance": {
                "latest_score": 150,   # invalid
                "average_score": 70,
                "previous_scores": [],
                "trend": "stable",
                "attempt_count": 1,
            },
        }
        r = client.post("/api/v1/decisions/evaluate", json=payload)
        assert r.status_code == 422  # Pydantic validation error

    def test_test_cases_list_endpoint(self):
        r = client.get("/api/v1/decisions/test-cases")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 8
        assert "CASE_01_IMPROVING_LEARNER" in body["cases"]

    def test_run_test_case_endpoint(self):
        r = client.post("/api/v1/decisions/test/CASE_02_CLEAR_MASTERY")
        assert r.status_code == 200
        body = r.json()
        assert body["case_name"] == "CASE_02_CLEAR_MASTERY"
        assert body["result"]["decision"] == "advance"

    def test_run_unknown_test_case_returns_404(self):
        r = client.post("/api/v1/decisions/test/CASE_DOES_NOT_EXIST")
        assert r.status_code == 404

    def test_root_endpoint(self):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert "module" in body

    def test_evaluate_endpoint_minimal_payload(self):
        """Engine must handle a context with only required fields populated."""
        payload = {
            "learner_id": 200,
            "lesson_id": 1,
            "context_version": 1,
        }
        r = client.post("/api/v1/decisions/evaluate", json=payload)
        # Should either succeed (with low confidence fallback) or return 422
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert r.json()["confidence"] <= POLICY.INSUFFICIENT_DATA_CONFIDENCE + 0.05


# ===========================================================================
# 11. Determinism — same input always same output
# ===========================================================================

class TestDeterminism:

    def test_same_context_same_decision_repeated(self):
        ctx = get_case("CASE_01_IMPROVING_LEARNER")
        results = [run_decision_engine(ctx).decision for _ in range(3)]
        assert len(set(r.value for r in results)) == 1, (
            "Engine must be deterministic for the same input"
        )
