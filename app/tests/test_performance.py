import pytest

from app.routers.performance import analyze_performance, get_performance_context
from app.workflows.performance.context_builder import build_context_package
from app.workflows.performance.mastery import evaluate_mastery
from app.workflows.performance.trend import calculate_trend


def test_trend_improving():
    assert calculate_trend([58, 62, 68]) == "improving"

def test_trend_declining():
    assert calculate_trend([90, 84, 76]) == "declining"

def test_trend_stable():
    assert calculate_trend([80, 81, 79]) == "stable"

def test_trend_insufficient_data():
    assert calculate_trend([]) == "insufficient_data"
    assert calculate_trend([80]) == "insufficient_data"

def test_trend_corrupted_scores():
    assert calculate_trend([50, 150, 60, -10, 70]) == "improving" # valid: 50, 60, 70

def test_mastery_achieved():
    result = evaluate_mastery([70, 75, 80], 75)
    assert result["status"] == "mastered"

def test_mastery_approaching():
    result = evaluate_mastery([50, 60, 70], 75)
    assert result["status"] == "approaching"

def test_mastery_not_reached():
    result = evaluate_mastery([40, 45, 50], 75)
    assert result["status"] == "not_mastered"

def test_mastery_missing_threshold():
    with pytest.raises(ValueError):
        evaluate_mastery([80], None)

def test_context_builder_missing_engagement():
    raw_data = {"scores": [80, 85], "threshold": 70}
    context = build_context_package(1, 1, raw_data)
    assert context["engagement"]["status"] == "unknown"

def test_context_builder_missing_intervention():
    raw_data = {"scores": [80, 85], "threshold": 70}
    context = build_context_package(1, 1, raw_data)
    assert context["intervention"]["effectiveness"] == "insufficient_data"

def test_context_builder_conflicting_signals():
    raw_data = {"scores": [90, 85, 80], "threshold": 70, "engagement": "low"}
    context = build_context_package(1, 1, raw_data)
    assert "high_score_but_declining" in context["risk_flags"]

def test_context_builder_large_history():
    raw_data = {"scores": [50] * 100 + [90, 95], "threshold": 70}
    context = build_context_package(1, 1, raw_data)
    assert context["performance"]["attempt_count"] == 102
    assert context["performance"]["latest_score"] == 95

def test_router_get_context_not_found():
    response = get_performance_context(999, 999)
    assert "error" in response
    assert response["error"]["code"] == "NOT_FOUND"

def test_router_analyze_performance():
    response = analyze_performance({"learner_id": 1, "lesson_id": 3})
    assert response["analysis_status"] == "complete"
    assert response["learner_context"]["performance"]["trend"] == "improving"
