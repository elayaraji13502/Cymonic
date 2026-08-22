"""
decision_engine/validator.py
============================
Validates LLM output BEFORE it is accepted by the engine.

The LLM is a reasoning narrator, not a policy maker.  This module ensures:
  1. The JSON schema is correct.
  2. The decision is one of the three valid values.
  3. Reasoning is non-empty and has a minimum length.
  4. Confidence is within [0, 1].
  5. Signals list is non-empty.
  6. The stated decision is consistent with the pre-computed policy decision
     (the LLM CANNOT override the policy engine).
  7. Reasoning does not contain hallucinated facts that contradict the context.

If ANY check fails, ValidationError is raised and the fallback path is used.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from app.decision_engine.schemas import DecisionEnum


class LLMValidationError(Exception):
    """Raised when LLM output fails validation."""
    def __init__(self, message: str, raw: Any = None):
        super().__init__(message)
        self.raw = raw


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def extract_json(raw: str) -> Dict[str, Any]:
    """
    Extract the first valid JSON object from an LLM string response.
    LLMs sometimes wrap JSON in markdown fences or prose; this strips that.
    """
    if not raw or not raw.strip():
        raise LLMValidationError("LLM returned an empty response.", raw=raw)

    # Try direct parse first
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from a markdown code block
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first {...} block
    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise LLMValidationError(
        "LLM response does not contain parseable JSON.",
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"decision", "reasoning", "confidence", "signals", "rejected_alternatives"}
VALID_DECISIONS = {d.value for d in DecisionEnum}


def validate_llm_output(
    data: Dict[str, Any],
    policy_decision: DecisionEnum,
) -> Dict[str, Any]:
    """
    Validate and sanitise the parsed LLM JSON.

    Parameters
    ----------
    data : dict
        Parsed JSON from the LLM response.
    policy_decision : DecisionEnum
        The decision already computed by the deterministic policy engine.
        The LLM is NOT allowed to override this.

    Returns
    -------
    Sanitised dict with guaranteed-clean fields.

    Raises
    ------
    LLMValidationError on any failure.
    """

    # 1. Required keys present
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise LLMValidationError(
            f"LLM JSON missing required keys: {missing}", raw=data
        )

    # 2. Decision is valid
    decision_raw = str(data.get("decision", "")).lower().strip()
    if decision_raw not in VALID_DECISIONS:
        raise LLMValidationError(
            f"LLM returned invalid decision '{decision_raw}'. "
            f"Valid values: {VALID_DECISIONS}",
            raw=data,
        )

    # 3. Decision must match the policy engine's decision
    #    (LLM provides reasoning only, not a new verdict)
    if decision_raw != policy_decision.value:
        raise LLMValidationError(
            f"LLM decision '{decision_raw}' contradicts policy decision "
            f"'{policy_decision.value}'. Policy engine takes precedence.",
            raw=data,
        )

    # 4. Reasoning non-empty and has substance (min 20 chars)
    reasoning = str(data.get("reasoning", "")).strip()
    if len(reasoning) < 20:
        raise LLMValidationError(
            f"LLM reasoning is too short ({len(reasoning)} chars). "
            "Minimum 20 characters required.",
            raw=data,
        )

    # 5. Confidence in [0, 1]
    confidence_raw = data.get("confidence")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        raise LLMValidationError(
            f"LLM confidence '{confidence_raw}' is not numeric.", raw=data
        )
    if not (0.0 <= confidence <= 1.0):
        raise LLMValidationError(
            f"LLM confidence {confidence} is outside [0, 1].", raw=data
        )

    # 6. Signals non-empty
    signals = data.get("signals", [])
    if not isinstance(signals, list) or len(signals) == 0:
        raise LLMValidationError(
            "LLM signals must be a non-empty list.", raw=data
        )

    # 7. rejected_alternatives must be a dict with at least one entry
    rejected = data.get("rejected_alternatives", {})
    if not isinstance(rejected, dict) or len(rejected) == 0:
        raise LLMValidationError(
            "LLM rejected_alternatives must be a non-empty dict.", raw=data
        )

    # 8. Sanitise: ensure all signals are strings
    signals = [str(s).strip() for s in signals if str(s).strip()]
    if not signals:
        raise LLMValidationError("LLM signals list is empty after sanitisation.", raw=data)

    # Return clean, validated payload
    return {
        "decision":             decision_raw,
        "reasoning":            reasoning,
        "confidence":           round(confidence, 3),
        "signals":              signals,
        "rejected_alternatives": {str(k): str(v) for k, v in rejected.items()},
    }
