import pytest

from app.workflows.learning_path.executor import apply_decision


@pytest.fixture
def base_state():
    from app.workflows.learning_path import executor as ex

    ex.DATASTORE.clear()
    ex.DATASTORE.update({
        "learners": {
            1: {
                "id": 1,
                "name": "Arun",
                "current_lesson_id": 1,
                "completed_lessons": [1],
                "course_id": 10,
                "course_progress": 50,
                "next_lesson_id": 2,
                "required_lessons_completed": 1,
                "required_assessments_passed": 1,
                "reinforcement_count": 0,
                "reinforcement_state": "none",
                "mentor_state": "none",
                "certification_state": {"eligible": False, "course_completion": 50},
                "completed_courses": [],
                "decision_history": [],
                "execution_keys": set(),
                "active_reinforcement": None,
                "active_mentor": None,
            }
        },
        "lessons": {
            1: {"id": 1, "course_id": 10, "title": "Intro", "required": True, "next_lesson_id": 2, "prerequisites": []},
            2: {"id": 2, "course_id": 10, "title": "Recursion", "required": True, "next_lesson_id": 3, "prerequisites": [1]},
            3: {"id": 3, "course_id": 10, "title": "Trees", "required": True, "next_lesson_id": None, "prerequisites": [2]},
        },
        "courses": {
            10: {"id": 10, "name": "Foundations", "required_lessons": [1, 2, 3], "required_assessments_total": 2}
        },
        "decision_history": [],
    })
    return ex.DATASTORE


def test_reinforce_assigns_reinforcement_and_updates_state(base_state):
    result = apply_decision({
        "learner_id": 1,
        "lesson_id": 1,
        "decision": "reinforce",
        "reasoning": "Needs additional practice before advancing.",
        "confidence": 0.86,
        "reasoning_source": "llm",
    })
    assert result["decision"] == "reinforce"
    assert result["action"] == "reinforcement_assigned"
    assert result["state_updated"] is True
    assert base_state["learners"][1]["reinforcement_count"] >= 1


def test_reinforce_duplicate_request_is_idempotent(base_state):
    first = apply_decision({
        "learner_id": 1,
        "lesson_id": 1,
        "decision": "reinforce",
        "reasoning": "Needs additional practice before advancing.",
        "confidence": 0.86,
        "reasoning_source": "llm",
    })
    second = apply_decision({
        "learner_id": 1,
        "lesson_id": 1,
        "decision": "reinforce",
        "reasoning": "Needs additional practice before advancing.",
        "confidence": 0.86,
        "reasoning_source": "llm",
    })
    assert first["decision"] == second["decision"]
    assert base_state["learners"][1]["reinforcement_count"] == 1


def test_advance_success_unlocks_next_lesson(base_state):
    base_state["learners"][1]["completed_lessons"] = [1, 2]
    base_state["learners"][1]["current_lesson_id"] = 2
    result = apply_decision({
        "learner_id": 1,
        "lesson_id": 2,
        "decision": "advance",
        "reasoning": "The learner has met the prerequisite conditions.",
        "confidence": 0.9,
        "reasoning_source": "llm",
    })
    assert result["decision"] == "advance"
    assert result["action"] == "lesson_advanced"
    assert result["updated_progress"]["next_lesson_id"] == 3


def test_advance_rejects_incomplete_requirements(base_state):
    base_state["learners"][1]["completed_lessons"] = []
    base_state["learners"][1]["current_lesson_id"] = 1
    with pytest.raises(ValueError):
        apply_decision({
            "learner_id": 1,
            "lesson_id": 2,  # Trying to advance lesson 2 while still on lesson 1
            "decision": "advance",
            "reasoning": "Not enough evidence.",
            "confidence": 0.5,
            "reasoning_source": "llm",
        })


def test_mentor_creates_pending_intervention(base_state):
    result = apply_decision({
        "learner_id": 1,
        "lesson_id": 2,
        "decision": "mentor",
        "reasoning": "Repeated failure despite reinforcement.",
        "confidence": 0.8,
        "reasoning_source": "llm",
    })
    assert result["decision"] == "mentor"
    assert result["mentor_payload"]["status"] == "pending"
    assert base_state["learners"][1]["mentor_state"] == "pending"


def test_duplicate_mentor_request_does_not_create_second(base_state):
    first = apply_decision({
        "learner_id": 1,
        "lesson_id": 2,
        "decision": "mentor",
        "reasoning": "Repeated failure despite reinforcement.",
        "confidence": 0.8,
        "reasoning_source": "llm",
    })
    second = apply_decision({
        "learner_id": 1,
        "lesson_id": 2,
        "decision": "mentor",
        "reasoning": "Repeated failure despite reinforcement.",
        "confidence": 0.8,
        "reasoning_source": "llm",
    })
    assert first["mentor_payload"]["status"] == second["mentor_payload"]["status"] == "pending"


def test_unknown_learner_returns_404_error(base_state):
    with pytest.raises(ValueError):
        apply_decision({
            "learner_id": 999,
            "lesson_id": 1,
            "decision": "reinforce",
            "reasoning": "Unknown learner.",
            "confidence": 0.7,
            "reasoning_source": "llm",
        })


def test_unknown_lesson_returns_404_error(base_state):
    with pytest.raises(ValueError):
        apply_decision({
            "learner_id": 1,
            "lesson_id": 999,
            "decision": "advance",
            "reasoning": "Unknown lesson.",
            "confidence": 0.7,
            "reasoning_source": "llm",
        })


def test_missing_reasoning_is_rejected(base_state):
    with pytest.raises(ValueError):
        apply_decision({
            "learner_id": 1,
            "lesson_id": 1,
            "decision": "reinforce",
            "confidence": 0.8,
            "reasoning_source": "llm",
        })


def test_invalid_decision_is_rejected(base_state):
    with pytest.raises(ValueError):
        apply_decision({
            "learner_id": 1,
            "lesson_id": 1,
            "decision": "escalate",
            "reasoning": "bad",
            "confidence": 0.8,
            "reasoning_source": "llm",
        })


@pytest.mark.asyncio
async def test_certification_status_is_computed(base_state):
    base_state["learners"][1]["completed_lessons"] = [1, 2, 3]
    base_state["learners"][1]["required_lessons_completed"] = 3
    base_state["learners"][1]["required_assessments_passed"] = 2
    base_state["learners"][1]["certification_state"] = {"eligible": True, "course_completion": 100}
    from app.routers.learning_path import get_certification_status

    status = await get_certification_status(1, 10)
    assert status["certification_eligible"] is True
    assert status["course_completion"] >= 80


def test_repeated_apply_request_is_idempotent(base_state):
    payload = {
        "learner_id": 1,
        "lesson_id": 1,
        "decision": "reinforce",
        "reasoning": "Needs more practice.",
        "confidence": 0.8,
        "reasoning_source": "llm",
    }
    first = apply_decision(payload)
    second = apply_decision(payload)
    assert first["action"] == second["action"]
    assert len(base_state["decision_history"]) == 1
