"""
decision_engine/engine.py
=========================
Top-level entry point for Module 3.

Previously this file contained the inline orchestration pipeline.
It now delegates to the LangGraph decision graph (graph.py), which
runs the same pipeline as a stateful graph of named nodes.

What changed
------------
- The 7-step inline pipeline (extract → check → override → score →
  select → LLM → fallback) is now executed by LangGraph.
- Every existing function (signals, evaluator, overrides, fallback,
  agent, validator) is UNCHANGED — they are called from graph nodes.
- The public API of this module is UNCHANGED:
    run_decision_engine(ctx: LearnerContext) → DecisionResponse

What did NOT change
-------------------
- schemas.py         — untouched
- signals.py         — untouched
- evaluator.py       — untouched
- overrides.py       — untouched
- fallback.py        — untouched
- agent.py           — untouched
- validator.py       — untouched
- policy.py          — untouched
- config/            — untouched
- api/decisions.py   — untouched (still calls run_decision_engine)
- all tests          — untouched
"""

from __future__ import annotations

import logging

from app.decision_engine.graph import decision_graph
from app.decision_engine.schemas import DecisionResponse, LearnerContext

logger = logging.getLogger(__name__)


def run_decision_engine(ctx: LearnerContext) -> DecisionResponse:
    """
    Execute the adaptive decision pipeline via the LangGraph graph.

    The graph runs these nodes in order (with conditional routing):
      1. node_extract_signals       — LearnerContext → SignalBundle
      2. node_check_data_sufficiency— sets data_sufficient routing flag
         ├─ [insufficient] → node_insufficient_data → DecisionResponse (REINFORCE, low conf)
         └─ [sufficient]   ↓
      3. node_evaluate_overrides    — SignalBundle → Optional[OverrideResult]
         ├─ [override fired] → node_override_path → (sets decision + confidence)
         └─ [no override]    ↓
      4. node_score_evidence        — SignalBundle → EvidenceScore
      5. node_select_candidate      — EvidenceScore → (DecisionEnum, confidence, note)
         (both override_path and select_candidate converge here)
      6. node_llm_reasoning         — calls Groq LLM; sets llm_succeeded flag
         ├─ [llm_success] → node_build_llm_response → DecisionResponse (source=llm)
         └─ [llm_failed]  → node_fallback_response  → DecisionResponse (source=fallback)

    Parameters
    ----------
    ctx : LearnerContext
        Complete learner context from Module 2 (or a test mock).

    Returns
    -------
    DecisionResponse
        Complete decision with reasoning, confidence, and all supporting data.
    """
    logger.info(
        "LangGraph pipeline start: learner=%d lesson=%d context_v=%d",
        ctx.learner_id, ctx.lesson_id, ctx.context_version,
    )

    # Invoke the compiled LangGraph with the initial state
    result_state = decision_graph.invoke({"ctx": ctx})

    response: DecisionResponse = result_state["final_response"]

    logger.info(
        "LangGraph pipeline end: learner=%d → %s (conf=%.2f, source=%s)",
        ctx.learner_id,
        response.decision.value,
        response.confidence,
        response.reasoning_source.value,
    )

    return response
