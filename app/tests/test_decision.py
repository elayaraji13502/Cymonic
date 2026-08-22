import json

import pytest

from app.workflows.decision.agent import evaluate_decision


def base_context(**overrides):
    context = {
        "latest_score": 72,
        "average_score": 70,
        "trend": "stable",
        "attempts": 4,
        "mastery": "not_mastered",
        "threshold": 75,
        "engagement": "medium",
        "learning_velocity": "steady",
        "previous_reinforcement": 0,
        "reinforcement_effectiveness": "none",
        "risk_flags": [],
        "certification_risk": "low",
        "lesson_difficulty": "medium",
        "required_lesson": True,
        "previous_decisions": [],
    }
    context.update(overrides)
    return context


def test_high_performer_advances():
    result = evaluate_decision(
        learner_id=1,
        lesson_id=3,
        learner_context=base_context(latest_score=92, average_score=88, trend="improving", mastery="mastered", threshold=80),
    )
    assert result["decision"] == "advance"
    assert result["reasoning_source"] in {"llm", "fallback"}
    assert result["confidence"] >= 0.0


def test_struggling_learner_reinforces():
    result = evaluate_decision(
        learner_id=2,
        lesson_id=4,
        learner_context=base_context(latest_score=48, average_score=52, trend="declining", mastery="not_mastered", engagement="low"),
    )
    assert result["decision"] == "reinforce"
    assert "reinforce" in result["reasoning"].lower() or "improving" in result["reasoning"].lower() or "not_mastered" in result["reasoning"].lower()


def test_persistent_failure_escalates_to_mentor():
    result = evaluate_decision(
        learner_id=3,
        lesson_id=5,
        learner_context=base_context(latest_score=56, average_score=54, trend="declining", previous_reinforcement=3, reinforcement_effectiveness="low", engagement="low", risk_flags=["disengagement"], certification_risk="high"),
    )
    assert result["decision"] == "mentor"


def test_improving_learner_reinforces_or_advance_based_on_context():
    result = evaluate_decision(
        learner_id=4,
        lesson_id=6,
        learner_context=base_context(latest_score=74, average_score=68, trend="improving", mastery="not_mastered", threshold=75, learning_velocity="accelerating"),
    )
    assert result["decision"] in {"reinforce", "advance"}
    assert result["confidence"] > 0.0


def test_declining_high_score_is_not_advance():
    result = evaluate_decision(
        learner_id=5,
        lesson_id=7,
        learner_context=base_context(latest_score=90, average_score=84, trend="declining", engagement="low", previous_reinforcement=2, risk_flags=["disengagement"], mastery="not_mastered"),
    )
    assert result["decision"] != "advance"
    assert "declining" in result["reasoning"].lower() or "risk" in result["reasoning"].lower()


def test_conflicting_signals_are_explicit():
    result = evaluate_decision(
        learner_id=6,
        lesson_id=8,
        learner_context=base_context(latest_score=80, average_score=79, trend="stable", engagement="low", risk_flags=["conflict"], previous_reinforcement=1),
    )
    assert "conflict" in result["reasoning"].lower() or "contradict" in result["reasoning"].lower() or "risk" in result["reasoning"].lower()


def test_insufficient_history_low_confidence():
    result = evaluate_decision(
        learner_id=7,
        lesson_id=9,
        learner_context={"latest_score": 70, "average_score": 70, "trend": "unknown", "attempts": 1, "mastery": "unknown", "threshold": 75, "engagement": "unknown", "learning_velocity": "unknown", "previous_reinforcement": 0, "reinforcement_effectiveness": "none", "risk_flags": [], "certification_risk": "unknown", "lesson_difficulty": "medium", "required_lesson": True, "previous_decisions": []},
    )
    assert result["confidence"] < 0.8


def test_llm_success_uses_llm_result(monkeypatch):
    def fake_llm(context):
        return {
            "decision": "reinforce",
            "reasoning": "The learner is below mastery and has not yet been reinforced.",
            "confidence": 0.9,
            "signals": ["mastery_not_reached", "no_previous_reinforcement"],
            "rejected_alternatives": {"reinforce": "", "advance": "Mastery is not achieved.", "mentor": "No repeated failure evidence exists."},
        }

    monkeypatch.setattr("app.services.llm_service.call_llm", fake_llm)
    result = evaluate_decision(
        learner_id=8,
        lesson_id=10,
        learner_context=base_context(latest_score=63, average_score=60, trend="improving", mastery="not_mastered"),
    )
    assert result["reasoning_source"] == "llm"
    assert result["decision"] == "reinforce"


def test_llm_timeout_uses_fallback(monkeypatch):
    def fake_timeout(context):
        raise TimeoutError("timed out")

    monkeypatch.setattr("app.services.llm_service.call_llm", fake_timeout)
    result = evaluate_decision(
        learner_id=9,
        lesson_id=11,
        learner_context=base_context(latest_score=58, average_score=60, trend="improving"),
    )
    assert result["reasoning_source"] == "fallback"


def test_llm_malformed_json_uses_fallback(monkeypatch):
    def fake_bad_json(context):
        return "not valid json"

    monkeypatch.setattr("app.services.llm_service.call_llm", fake_bad_json)
    result = evaluate_decision(
        learner_id=10,
        lesson_id=12,
        learner_context=base_context(latest_score=66, average_score=63, trend="stable"),
    )
    assert result["reasoning_source"] == "fallback"


def test_invalid_decision_rejected_and_fallback(monkeypatch):
    def fake_invalid(context):
        return {
            "decision": "escalate",
            "reasoning": "bad output",
            "confidence": 0.7,
            "signals": ["x"],
            "rejected_alternatives": {"reinforce": "", "advance": "", "mentor": ""},
        }

    monkeypatch.setattr("app.services.llm_service.call_llm", fake_invalid)
    result = evaluate_decision(
        learner_id=11,
        lesson_id=13,
        learner_context=base_context(latest_score=77, average_score=76, trend="improving"),
    )
    assert result["decision"] in {"reinforce", "advance", "mentor"}
    assert result["reasoning_source"] in {"llm", "fallback"}


def test_empty_reasoning_falls_back(monkeypatch):
    def fake_empty(context):
        return {
            "decision": "reinforce",
            "reasoning": "",
            "confidence": 0.8,
            "signals": ["x"],
            "rejected_alternatives": {"reinforce": "", "advance": "", "mentor": ""},
        }

    monkeypatch.setattr("app.services.llm_service.call_llm", fake_empty)
    result = evaluate_decision(
        learner_id=12,
        lesson_id=14,
        learner_context=base_context(latest_score=62, average_score=64, trend="improving"),
    )
    assert result["reasoning_source"] == "fallback"


def test_fallback_works_without_llm():
    result = evaluate_decision(
        learner_id=13,
        lesson_id=15,
        learner_context=base_context(latest_score=52, average_score=55, trend="stable", mastery="not_mastered"),
    )
    assert result["reasoning_source"] == "fallback"
    assert result["decision"] in {"reinforce", "advance", "mentor"}


def test_structured_output_validation():
    result = evaluate_decision(
        learner_id=14,
        lesson_id=16,
        learner_context=base_context(latest_score=71, average_score=72, trend="improving", mastery="not_mastered"),
    )
    assert set(result.keys()) >= {"decision", "reasoning", "confidence", "signals", "rejected_alternatives", "reasoning_source"}
    assert result["decision"] in {"reinforce", "advance", "mentor"}
    assert isinstance(result["signals"], list)
    assert isinstance(result["rejected_alternatives"], dict)
    assert 0.0 <= result["confidence"] <= 1.0


def test_missing_learner_context_raises_controlled_error():
    with pytest.raises(ValueError):
        evaluate_decision(learner_id=15, lesson_id=17, learner_context=None)


def test_incomplete_context_is_rejected():
    with pytest.raises(ValueError):
        evaluate_decision(learner_id=16, lesson_id=18, learner_context={"latest_score": 80})


def test_api_contract_shape():
    result = evaluate_decision(
        learner_id=17,
        lesson_id=19,
        learner_context=base_context(latest_score=81, average_score=77, trend="improving", mastery="mastered"),
    )
    assert sorted(result.keys()) == ["confidence", "decision", "reasoning", "reasoning_source", "rejected_alternatives", "signals"]
