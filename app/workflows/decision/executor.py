from app.workflows.decision.schemas import VALID_DECISIONS, normalize_decision


def execute_decision(payload: dict):
    """Workflow 4 handoff: accept a validated decision payload and produce a safe execution summary.

    This intentionally does not perform learner actions or strategy execution. It only
    validates the execution boundary and returns a structured execution record.
    """
    if not isinstance(payload, dict):
        raise ValueError("Decision payload must be a JSON object")

    decision = normalize_decision(payload.get("decision"))
    if decision is None or decision not in VALID_DECISIONS:
        raise ValueError("Decision cannot be executed: invalid decision value")

    reasoning = str(payload.get("reasoning", "")).strip()
    confidence = float(payload.get("confidence", 0.0))
    signals = payload.get("signals") or []
    reasoning_source = str(payload.get("reasoning_source", "fallback")).strip().lower()

    if not reasoning:
        raise ValueError("Decision cannot be executed: reasoning is empty")
    if not isinstance(signals, list):
        raise ValueError("Decision cannot be executed: signals must be a list")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Decision cannot be executed: confidence must be between 0 and 1")

    return {
        "status": "accepted",
        "decision": decision,
        "reasoning": reasoning,
        "confidence": float(confidence),
        "signals": signals,
        "reasoning_source": reasoning_source,
        "executed_by": "workflow_4",
        "execution_note": "Validated decision received; no strategy execution performed.",
    }
