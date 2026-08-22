"""
decision_engine/agent.py
========================
LLM reasoning agent.

Responsibilities
----------------
1. Build a structured prompt from the pre-computed policy evidence.
2. Call the LLM with a strict JSON response contract.
3. Return parsed + validated JSON, or raise an exception so the caller
   falls back to the deterministic path.

Key design decisions
--------------------
- The prompt GIVES the LLM the policy decision — it cannot override it.
- The prompt GIVES the LLM the evidence scores so it cannot invent signals.
- The LLM's only job: explain the evidence in natural language and articulate
  why competing candidates were weaker.
- JSON schema is embedded in the system prompt, enforcing structure.
- Timeout and unavailability are handled here so the caller always gets
  a clean success / exception boundary.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from app.config.decision_policy import POLICY
from app.decision_engine.policy import label
from app.decision_engine.schemas import DecisionEnum, EvidenceScore, LearnerContext
from app.decision_engine.signals import SignalBundle
from app.decision_engine.validator import LLMValidationError, extract_json, validate_llm_output


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Groq default model — fast and free-tier friendly
LLM_MODEL   = os.getenv("LLM_MODEL", "llama3-8b-8192")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
FORCE_FALLBACK = os.getenv("FORCE_FALLBACK", "false").lower() == "true"

# Groq's API is OpenAI-compatible; we just point the base_url at Groq
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the reasoning narrator for an Adaptive Learning Coach decision engine.

Your role is ONLY to explain a decision that has already been made by the policy engine.
You do NOT make decisions. You do NOT modify the decision. You explain it.

You will be given:
- The pre-computed decision (reinforce / advance / mentor)
- Evidence scores for each candidate
- Signals that fired for each candidate
- The learner's context summary

You must return ONLY valid JSON matching this exact schema:
{
  "decision": "<same as the pre-computed decision>",
  "reasoning": "<2-4 sentence explanation of WHY this decision is correct given the evidence>",
  "confidence": <float between 0.0 and 1.0>,
  "signals": ["signal_id_1", "signal_id_2", ...],
  "rejected_alternatives": {
    "advance": "<1 sentence explaining why ADVANCE was not selected>",
    "mentor": "<1 sentence explaining why MENTOR was not selected>"
  }
}

Rules:
- decision MUST match the pre-computed decision exactly.
- reasoning MUST reference the actual signals provided. Do not invent facts.
- confidence must reflect the strength of the evidence (not your opinion of the learner).
- signals must be a subset of the signals listed in the evidence block.
- rejected_alternatives must explain the competing candidates using the supplied evidence.
- Return ONLY the JSON object. No markdown. No prose outside the JSON.
"""


def _build_user_prompt(
    ctx: LearnerContext,
    decision: DecisionEnum,
    confidence: float,
    ev: EvidenceScore,
    b: SignalBundle,
) -> str:
    """Build the user-turn prompt with all pre-computed evidence."""

    winning_signals = {
        DecisionEnum.advance:   ev.advance_signals,
        DecisionEnum.reinforce: ev.reinforce_signals,
        DecisionEnum.mentor:    ev.mentor_signals,
    }[decision]

    signal_descriptions = [f"  - {s}: {label(s)}" for s in winning_signals]

    conflict_note = ""
    if b.trend_declining and b.score_above_mastery:
        conflict_note = (
            "\nCONFLICT DETECTED: Latest score is above mastery threshold but "
            "trend is declining. The decision accounts for this — explain both signals.\n"
        )
    if b.single_high_spike:
        conflict_note += (
            "\nCONFLICT DETECTED: Latest score is a spike (≥20pts above average). "
            "This is NOT treated as confirmed mastery.\n"
        )

    prompt = f"""
PRE-COMPUTED DECISION: {decision.value.upper()}
PRE-COMPUTED CONFIDENCE: {confidence}

LEARNER CONTEXT:
  Learner ID: {ctx.learner_id}  |  Lesson ID: {ctx.lesson_id}
  Latest score: {ctx.performance.latest_score}
  Average score: {ctx.performance.average_score}
  Previous scores: {ctx.performance.previous_scores}
  Trend: {ctx.performance.trend.value}
  Attempt count: {ctx.performance.attempt_count}
  Mastery status: {ctx.mastery.status.value}  |  Threshold: {ctx.mastery.threshold}
  Engagement: {ctx.engagement.level.value}  |  Inactivity days: {ctx.engagement.inactivity_days}
  Reinforcement count: {ctx.intervention.reinforcement_count}
  Intervention effectiveness: {ctx.intervention.effectiveness.value}
  Previous mentor intervention: {ctx.intervention.previous_mentor_intervention}
  Risk flags: {ctx.risk_flags or 'none'}
  Weakness tags: {ctx.weakness_tags or 'none'}
  Certification required: {ctx.course.certification_required}
  Certification risk: {ctx.course.certification_risk.value}
{conflict_note}
EVIDENCE SCORES (raw):
  REINFORCE: {ev.reinforce:.3f}   ADVANCE: {ev.advance:.3f}   MENTOR: {ev.mentor:.3f}

SIGNALS SUPPORTING {decision.value.upper()}:
{chr(10).join(signal_descriptions) if signal_descriptions else "  (none specific)"}

SIGNALS OPPOSING:
  REINFORCE blockers: {ev.reinforce_blockers}
  ADVANCE blockers:   {ev.advance_blockers}
  MENTOR blockers:    {ev.mentor_blockers}

Generate the JSON explanation now.
"""
    return prompt.strip()


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached at all."""


def call_llm(
    ctx: LearnerContext,
    decision: DecisionEnum,
    confidence: float,
    ev: EvidenceScore,
    b: SignalBundle,
) -> Dict[str, Any]:
    """
    Call the LLM and return validated JSON.

    Raises
    ------
    LLMUnavailableError   — no API key / client import failure
    LLMValidationError    — LLM returned bad output
    TimeoutError          — LLM call timed out
    """
    if FORCE_FALLBACK:
        raise LLMUnavailableError("FORCE_FALLBACK is enabled; skipping LLM.")

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key.startswith("gsk_...") or len(api_key) < 20:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not configured. Running in fallback mode."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMUnavailableError(f"openai package not installed: {exc}") from exc

    # Groq uses OpenAI-compatible API — just point base_url at Groq
    client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL, timeout=LLM_TIMEOUT)
    user_prompt = _build_user_prompt(ctx, decision, confidence, ev, b)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,   # low temperature for deterministic reasoning
            max_tokens=600,
        )
    except Exception as exc:
        # Covers network errors, auth errors, timeout
        err_str = str(exc).lower()
        if "timeout" in err_str or "timed out" in err_str:
            raise TimeoutError(f"LLM call timed out: {exc}") from exc
        raise LLMUnavailableError(f"LLM call failed: {exc}") from exc

    raw = response.choices[0].message.content or ""
    parsed = extract_json(raw)
    validated = validate_llm_output(parsed, policy_decision=decision)
    return validated
