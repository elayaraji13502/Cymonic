import pytest

from app.routers.decisions import evaluate_decision_endpoint
from app.routers.learning_path import apply_decision_endpoint, get_certification_status, get_learning_path
from app.workflows.decision.agent import evaluate_decision
from app.workflows.decision.fallback import generate_fallback_decision
from app.workflows.decision.validator import check_reasoning_is_grounded, validate_business_constraints
from app.workflows.learning_path.executor import DATASTORE, apply_decision


# --- Decision Workflow Edge Cases ---

def test_evaluate_decision_endpoint_invalid_payload():
    with pytest.raises(ValueError, match="Request body must be a JSON object"):
        evaluate_decision_endpoint([])

def test_evaluate_decision_endpoint_missing_ids():
    with pytest.raises(ValueError, match="Request requires learner_id and lesson_id"):
        evaluate_decision_endpoint({"learner_context": {}})

def test_evaluate_decision_invalid_id_types():
    with pytest.raises(ValueError, match="learner_id and lesson_id must be integers"):
        evaluate_decision(learner_id="1", lesson_id="2", learner_context={"latest_score": 100, "average_score": 100, "trend": "stable", "attempts": 1, "mastery": "mastered", "threshold": 80, "engagement": "high", "learning_velocity": "steady", "previous_reinforcement": 0, "reinforcement_effectiveness": "none", "risk_flags": [], "certification_risk": "low", "lesson_difficulty": "easy", "required_lesson": False, "previous_decisions": []})

def test_fallback_missing_scores():
    with pytest.raises(ValueError, match="Missing learner scores for fallback evaluation"):
        generate_fallback_decision({"trend": "stable"})

def test_fallback_low_engagement_reinforce():
    context = {
        "latest_score": 60, "average_score": 60, "trend": "declining", "mastery": "not_mastered",
        "engagement": "low", "attempts": 2, "previous_reinforcement": 0, "risk_flags": [],
        "certification_risk": "low", "threshold": 75
    }
    result = generate_fallback_decision(context)
    assert result["decision"] == "reinforce"
    assert "low_engagement" in result["signals"]

def test_fallback_risk_flags_reinforce():
    context = {
        "latest_score": 60, "average_score": 60, "trend": "stable", "mastery": "not_mastered",
        "engagement": "high", "attempts": 2, "previous_reinforcement": 0, "risk_flags": ["distracted"],
        "certification_risk": "low", "threshold": 75
    }
    result = generate_fallback_decision(context)
    assert result["decision"] == "reinforce"
    assert "conflicting_signals" in result["signals"]

def test_fallback_persistent_failure_after_intervention():
    context = {
        "latest_score": 60, "average_score": 60, "trend": "declining", "mastery": "not_mastered",
        "engagement": "low", "attempts": 2, "previous_reinforcement": 1, "risk_flags": [],
        "certification_risk": "low", "threshold": 75
    }
    result = generate_fallback_decision(context)
    assert result["decision"] == "mentor"
    assert "persistent_failure_after_intervention" in result["signals"]

def test_validator_ungrounded_reasoning():
    assert not check_reasoning_is_grounded({}, "I think the learner should advance")
    assert not check_reasoning_is_grounded({}, "As an AI, I recommend mentor")
    assert not check_reasoning_is_grounded({}, "")
    assert check_reasoning_is_grounded({}, "The learner has reached mastery.")

def test_validator_business_constraints_advance_high_risk():
    with pytest.raises(ValueError, match="Invalid advance decision: certification risk is too high"):
        validate_business_constraints({"certification_risk": "high", "mastery": "mastered", "latest_score": 100, "threshold": 80}, "advance", "Good")

def test_validator_business_constraints_advance_hard_lesson_not_mastered():
    # This was redundant with the primary mastery check, so we just verify the primary check works
    with pytest.raises(ValueError, match="Invalid advance decision: mastery and performance evidence are insufficient"):
        validate_business_constraints({"required_lesson": True, "lesson_difficulty": "hard", "mastery": "not_mastered", "latest_score": 80, "threshold": 70}, "advance", "Good")

def test_validator_business_constraints_unsupported_certification_claim():
    with pytest.raises(ValueError, match="Unsupported certification claim"):
        validate_business_constraints({"certification_risk": "high"}, "reinforce", "The learner will get certification soon.")


# --- Learning Path Workflow Edge Cases ---

@pytest.fixture
def clean_datastore():
    DATASTORE.clear()
    DATASTORE.update({
        "learners": {
            1: {
                "id": 1, "name": "Test", "current_lesson_id": 1, "completed_lessons": [],
                "course_id": 10, "course_progress": 0, "next_lesson_id": 2,
                "execution_keys": set()
            }
        },
        "lessons": {
            1: {"id": 1, "course_id": 10, "title": "L1", "next_lesson_id": 2},
            2: {"id": 2, "course_id": 10, "title": "L2", "next_lesson_id": None},
            3: {"id": 3, "course_id": 20, "title": "L3", "next_lesson_id": None} # Different course
        },
        "courses": {
            10: {"id": 10, "required_lessons": [1, 2], "required_assessments_total": 1}
        },
        "decision_history": []
    })
    return DATASTORE

def test_apply_decision_endpoint_invalid_payload():
    with pytest.raises(ValueError, match="Decision payload must be a dictionary"):
        apply_decision_endpoint([])

def test_apply_decision_missing_ids(clean_datastore):
    with pytest.raises(ValueError, match="Learner and lesson identifiers are required"):
        apply_decision({"decision": "reinforce", "reasoning": "test", "confidence": 1.0})

def test_apply_decision_invalid_decision(clean_datastore):
    with pytest.raises(ValueError, match="Invalid decision"):
        apply_decision({"learner_id": 1, "lesson_id": 1, "decision": "skip", "reasoning": "test", "confidence": 1.0})

def test_apply_decision_missing_reasoning(clean_datastore):
    with pytest.raises(ValueError, match="Missing reasoning"):
        apply_decision({"learner_id": 1, "lesson_id": 1, "decision": "reinforce", "reasoning": "", "confidence": 1.0})

def test_apply_decision_invalid_confidence(clean_datastore):
    with pytest.raises(ValueError, match="Invalid confidence"):
        apply_decision({"learner_id": 1, "lesson_id": 1, "decision": "reinforce", "reasoning": "test", "confidence": 1.5})

def test_apply_decision_wrong_course(clean_datastore):
    with pytest.raises(ValueError, match="Lesson does not belong to the learner course"):
        apply_decision({"learner_id": 1, "lesson_id": 3, "decision": "reinforce", "reasoning": "test", "confidence": 1.0})

def test_apply_decision_advance_not_in_required_path(clean_datastore):
    clean_datastore["courses"][10]["required_lessons"] = [2]
    with pytest.raises(ValueError, match="Lesson is not part of the required course path"):
        apply_decision({"learner_id": 1, "lesson_id": 1, "decision": "advance", "reasoning": "test", "confidence": 1.0})

def test_get_learning_path_unknown_learner(clean_datastore):
    with pytest.raises(ValueError, match="Unknown learner"):
        get_learning_path(999)

def test_get_certification_status_unknown_learner(clean_datastore):
    with pytest.raises(ValueError, match="Unknown learner"):
        get_certification_status(999, 10)

def test_get_certification_status_unknown_course(clean_datastore):
    with pytest.raises(ValueError, match="Unknown course"):
        get_certification_status(1, 999)

def test_idempotent_advance(clean_datastore):
    clean_datastore["learners"][1]["completed_lessons"] = [1]
    payload = {"learner_id": 1, "lesson_id": 1, "decision": "advance", "reasoning": "test", "confidence": 1.0}
    first = apply_decision(payload)
    second = apply_decision(payload)
    assert first["action"] == "lesson_advanced"
    assert second["action"] == "lesson_advanced"
    assert second["state_updated"] is False

def test_idempotent_mentor(clean_datastore):
    payload = {"learner_id": 1, "lesson_id": 1, "decision": "mentor", "reasoning": "test", "confidence": 1.0}
    first = apply_decision(payload)
    second = apply_decision(payload)
    assert first["action"] == "mentor_intervention_created"
    assert second["action"] == "mentor_intervention_created"
    assert second["state_updated"] is False
