import json

from .schemas import VALID_DECISIONS, build_empty_rejected_alternatives, normalize_decision


def validate_structured_output(payload):
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object")
    if "decision" not in payload:
        raise ValueError("Missing decision")
    decision = normalize_decision(payload["decision"])
    if decision is None:
        raise ValueError("Unsupported decision value")
    if "reasoning" not in payload or not str(payload["reasoning"]).strip():
        raise ValueError("Reasoning must be non-empty")
    if "confidence" not in payload:
        raise ValueError("Missing confidence")
    confidence = float(payload["confidence"])
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1")
    if "signals" not in payload or not isinstance(payload["signals"], list) or not payload["signals"]:
        raise ValueError("Signals must be a non-empty list")
    rejected = payload.get("rejected_alternatives")
    if not isinstance(rejected, dict):
        rejected = build_empty_rejected_alternatives()
    for key in ["reinforce", "advance", "mentor"]:
        if key not in rejected:
            rejected[key] = ""
    payload["decision"] = decision
    payload["reasoning"] = str(payload["reasoning"]).strip()
    payload["confidence"] = float(confidence)
    payload["signals"] = list(payload["signals"])
    payload["rejected_alternatives"] = rejected
    return payload


def validate_business_constraints(context, decision, reasoning):
    mastery = str(context.get("mastery", "")).lower()
    threshold = context.get("threshold")
    latest_score = context.get("latest_score")
    certification_risk = str(context.get("certification_risk", "")).lower()
    previous_reinforcement = context.get("previous_reinforcement", 0)
    risk_flags = context.get("risk_flags") or []

    if decision == "advance" and (mastery != "mastered" or (threshold is not None and latest_score is not None and latest_score < threshold)):
        raise ValueError("Invalid advance decision: mastery and performance evidence are insufficient")
    if decision == "mentor" and previous_reinforcement < 2 and not risk_flags and certification_risk not in {"high", "critical", "medium"}:
        pass
    if decision == "advance" and certification_risk in {"high", "critical"}:
        raise ValueError("Invalid advance decision: certification risk is too high")
    if decision == "mentor" and "repeated failure" in reasoning.lower() and previous_reinforcement < 2:
        pass
    if "certification" in reasoning.lower() and certification_risk in {"high", "critical"} and decision != "mentor":
        raise ValueError("Unsupported certification claim")
    return True


def check_reasoning_is_grounded(context, reasoning):
    if not reasoning or not str(reasoning).strip():
        return False
    if any(token in reasoning.lower() for token in ["i think", "maybe", "probably", "as an ai"]):
        return False
    return True
