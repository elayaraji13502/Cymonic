import json
from typing import Any

from app.services import llm_service
from app.workflows.decision.fallback import generate_fallback_decision
from app.workflows.decision.prompt_builder import build_reasoning_prompt
from app.workflows.decision.schemas import normalize_decision, validate_context
from app.workflows.decision.validator import (
    check_reasoning_is_grounded,
    validate_business_constraints,
    validate_structured_output,
)


def _safe_llm_call(context):
    raw = llm_service.call_llm(context)
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed JSON") from exc
    elif isinstance(raw, dict):
        payload = raw
    else:
        raise ValueError("Unsupported LLM output")
    return payload


def _llm_attempt(context):
    raw_prompt = build_reasoning_prompt(context)
    try:
        payload = _safe_llm_call(context)
        validated = validate_structured_output(payload)
        decision = validated["decision"]
        reasoning = validated["reasoning"]
        if not check_reasoning_is_grounded(context, reasoning):
            raise ValueError("Reasoning is not grounded in context")
        validate_business_constraints(context, decision, reasoning)
        if "reasoning_source" not in validated:
            validated["reasoning_source"] = "llm"
        return validated
    except (TimeoutError, RuntimeError, ValueError, TypeError):
        fallback = generate_fallback_decision(context)
        fallback["reasoning_source"] = "fallback"
        return fallback


def evaluate_decision(learner_id: int, lesson_id: int, learner_context: dict[str, Any] | None = None):
    """Evaluate a learner and return a validated decision payload for Workflow 4."""
    if learner_context is None:
        raise ValueError("Missing learner context.")
    context = validate_context(learner_context)

    if not isinstance(learner_id, int) or not isinstance(lesson_id, int):
        raise ValueError("learner_id and lesson_id must be integers")

    try:
        llm_payload = _llm_attempt(context)
    except Exception:
        llm_payload = generate_fallback_decision(context)
        llm_payload["reasoning_source"] = "fallback"

    decision = normalize_decision(llm_payload.get("decision"))
    if decision is None:
        fallback = generate_fallback_decision(context)
        fallback["reasoning_source"] = "fallback"
        return fallback

    validated = {
        "decision": decision,
        "reasoning": str(llm_payload.get("reasoning", "")).strip(),
        "confidence": float(llm_payload.get("confidence", 0.0)),
        "signals": llm_payload.get("signals", []) or [],
        "rejected_alternatives": llm_payload.get("rejected_alternatives", {"reinforce": "", "advance": "", "mentor": ""}),
        "reasoning_source": str(llm_payload.get("reasoning_source", "fallback")).strip().lower() if llm_payload.get("reasoning_source") else "fallback",
    }

    if not validated["reasoning"]:
        fallback = generate_fallback_decision(context)
        fallback["reasoning_source"] = "fallback"
        return fallback

    if not isinstance(validated["signals"], list) or not validated["signals"]:
        validated["signals"] = ["context_assessed"]

    if not isinstance(validated["rejected_alternatives"], dict):
        validated["rejected_alternatives"] = {"reinforce": "", "advance": "", "mentor": ""}

    for key in ["reinforce", "advance", "mentor"]:
        validated["rejected_alternatives"].setdefault(key, "")

    if not 0.0 <= validated["confidence"] <= 1.0:
        validated["confidence"] = min(max(float(validated["confidence"]), 0.0), 1.0)

    try:
        validate_business_constraints(context, validated["decision"], validated["reasoning"])
    except ValueError:
        fallback = generate_fallback_decision(context)
        fallback["reasoning_source"] = "fallback"
        return fallback

    return validated
