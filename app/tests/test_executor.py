from app.workflows.decision.executor import execute_decision


def test_valid_execution_payload_is_accepted():
    result = execute_decision({
        "decision": "reinforce",
        "reasoning": "The learner is below mastery and needs more practice.",
        "confidence": 0.86,
        "signals": ["mastery_not_reached"],
        "reasoning_source": "llm",
    })
    assert result["status"] == "accepted"
    assert result["decision"] == "reinforce"


def test_invalid_decision_is_rejected():
    try:
        execute_decision({
            "decision": "escalate",
            "reasoning": "bad",
            "confidence": 0.5,
            "signals": ["x"],
            "reasoning_source": "fallback",
        })
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_empty_reasoning_is_rejected():
    try:
        execute_decision({
            "decision": "advance",
            "reasoning": "",
            "confidence": 0.7,
            "signals": ["mastery_reached"],
            "reasoning_source": "llm",
        })
        assert False, "Expected ValueError"
    except ValueError:
        pass
