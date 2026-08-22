"""
decision_engine/graph.py
========================
LangGraph orchestration layer for Module 3 — Adaptive Decision Engine.

This file is the ONLY new orchestration logic. Every node calls an
existing function from the existing codebase — nothing is rewritten.

Graph topology
--------------

  [START]
     │
     ▼
  node_extract_signals
     │
     ▼
  node_check_data_sufficiency ──── route_data ────► node_insufficient_data ──► [END]
     │ (sufficient)
     ▼
  node_evaluate_overrides
     │
     ▼
  route_override ──────────────────────────────────► node_override_path
     │ (no override)                                        │
     ▼                                                      │
  node_score_evidence                                       │
     │                                                      │
     ▼                                                      │
  node_select_candidate                                     │
     │                                                      │
     ▼                                                      ▼
  node_llm_reasoning ◄─────────────────────────────────────┘
     │
     ▼
  route_llm ──────────────────────────────────────► node_fallback_response ──► [END]
     │ (llm succeeded)
     ▼
  node_build_llm_response
     │
     ▼
  [END]

Conditional edge functions (pure):
  route_data       : "insufficient" | "continue"
  route_override   : "override_fired" | "continue"
  route_llm        : "llm_success" | "llm_failed"

All business logic remains in the existing modules.
This file only wires them into a graph and manages state transitions.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.config.decision_policy import POLICY
from app.decision_engine.agent import LLMUnavailableError, call_llm
from app.decision_engine.evaluator import evaluate, select_candidate
from app.decision_engine.fallback import build_fallback_response, _build_decision_factors
from app.decision_engine.graph_state import GraphState
from app.decision_engine.overrides import evaluate_advance_blockers, evaluate_overrides
from app.decision_engine.schemas import (
    DecisionEnum,
    DecisionResponse,
    ReasoningSourceEnum,
)
from app.decision_engine.signals import extract_signals
from app.decision_engine.validator import LLMValidationError

logger = logging.getLogger(__name__)


# ===========================================================================
# NODE DEFINITIONS
# Each node receives the full GraphState, reads what it needs,
# and returns a dict of fields to update in the state.
# ===========================================================================

def node_extract_signals(state: GraphState) -> dict:
    """
    Node 1 — Signal Extraction
    Wraps: signals.extract_signals()
    Input:  state["ctx"]
    Output: state["signals"]
    """
    ctx = state["ctx"]
    b = extract_signals(ctx)
    logger.debug("node_extract_signals: data_sufficient=%s", b.data_sufficient)
    return {"signals": b, "data_sufficient": b.data_sufficient}


def node_check_data_sufficiency(state: GraphState) -> dict:
    """
    Node 2 — Data sufficiency check (sets routing flag).
    The actual flag was already written by node_extract_signals;
    this node just makes the intent explicit as a named step.
    """
    return {}   # data_sufficient already set in state


def node_insufficient_data(state: GraphState) -> dict:
    """
    Node 3a — Insufficient data exit path.
    Wraps: evaluator.evaluate() + fallback.build_fallback_response()
    Returns a low-confidence REINFORCE DecisionResponse.
    """
    ctx = state["ctx"]
    b = state["signals"]
    ev = evaluate(b)
    response = build_fallback_response(
        ctx=ctx,
        decision=DecisionEnum.reinforce,
        confidence=POLICY.INSUFFICIENT_DATA_CONFIDENCE,
        ev=ev,
        b=b,
        selection_note="Insufficient data — safe default applied",
        override_reason=(
            f"Key data is missing ({', '.join(b.missing_fields)}). "
            "Cannot produce a high-confidence decision. "
            "Defaulting to REINFORCE as the safest option pending more data."
        ),
    )
    logger.info(
        "node_insufficient_data: learner=%d → REINFORCE (conf=%.2f)",
        ctx.learner_id, POLICY.INSUFFICIENT_DATA_CONFIDENCE,
    )
    return {"final_response": response, "evidence_score": ev}


def node_evaluate_overrides(state: GraphState) -> dict:
    """
    Node 3b — Hard override evaluation.
    Wraps: overrides.evaluate_overrides()
    Input:  state["signals"]
    Output: state["override_result"], state["override_fired"]
    """
    b = state["signals"]
    override = evaluate_overrides(b)
    fired = override is not None
    logger.debug("node_evaluate_overrides: fired=%s", fired)
    return {"override_result": override, "override_fired": fired}


def node_override_path(state: GraphState) -> dict:
    """
    Node 4a — Override decision path.
    When an override fired, build the decision from the override result
    and prepare for LLM narration.  Mirrors the override block in engine.py.
    """
    ctx = state["ctx"]
    b = state["signals"]
    override = state["override_result"]

    ev = evaluate(b)
    base_confidence = min(
        0.95,
        POLICY.MIN_DECISION_CONFIDENCE + 0.2 + override.confidence_modifier,
    )
    logger.info(
        "node_override_path: learner=%d override=%s → %s",
        ctx.learner_id, override.signals, override.decision.value,
    )
    return {
        "evidence_score": ev,
        "decision": override.decision,
        "confidence": base_confidence,
        "selection_note": f"Override: {override.reason}",
        "advance_block_reasons": [],
    }


def node_score_evidence(state: GraphState) -> dict:
    """
    Node 4b — Evidence scoring (no override fired).
    Wraps: evaluator.evaluate()
    Input:  state["signals"]
    Output: state["evidence_score"]
    """
    b = state["signals"]
    ev = evaluate(b)
    logger.debug(
        "node_score_evidence: R=%.2f A=%.2f M=%.2f",
        ev.reinforce, ev.advance, ev.mentor,
    )
    return {"evidence_score": ev}


def node_select_candidate(state: GraphState) -> dict:
    """
    Node 5 — Candidate selection + confidence calculation.
    Wraps: evaluator.select_candidate()
    Input:  state["evidence_score"], state["signals"]
    Output: state["decision"], state["confidence"], state["selection_note"],
            state["advance_block_reasons"]
    """
    ev = state["evidence_score"]
    b = state["signals"]
    decision, confidence, selection_note = select_candidate(ev, b)

    # Collect advance block reasons for use in fallback/LLM narration
    advance_blocks: list[str] = []
    if decision != DecisionEnum.advance:
        block = evaluate_advance_blockers(b)
        if block.blocked:
            advance_blocks = block.reasons

    logger.info(
        "node_select_candidate: learner=%d → %s (conf=%.2f)",
        state["ctx"].learner_id, decision.value, confidence,
    )
    return {
        "decision": decision,
        "confidence": confidence,
        "selection_note": selection_note,
        "advance_block_reasons": advance_blocks,
    }


def node_llm_reasoning(state: GraphState) -> dict:
    """
    Node 6 — LLM reasoning attempt (Groq via OpenAI-compatible client).
    Wraps: agent.call_llm()

    This is the ONLY node with a network side effect.
    On any failure, sets llm_succeeded=False so the router
    directs to the fallback node.
    """
    ctx = state["ctx"]
    decision = state["decision"]
    confidence = state["confidence"]
    ev = state["evidence_score"]
    b = state["signals"]

    try:
        llm_data = call_llm(ctx, decision, confidence, ev, b)
        logger.info(
            "node_llm_reasoning: LLM succeeded for learner=%d", ctx.learner_id
        )
        return {"llm_output": llm_data, "llm_succeeded": True}
    except (LLMUnavailableError, LLMValidationError, TimeoutError, Exception) as exc:
        logger.info(
            "node_llm_reasoning: LLM failed (%s: %s) → fallback",
            type(exc).__name__, exc,
        )
        return {"llm_output": None, "llm_succeeded": False}


def node_build_llm_response(state: GraphState) -> dict:
    """
    Node 7a — Build DecisionResponse from validated LLM output.
    Mirrors engine._llm_response() logic.
    """
    ctx = state["ctx"]
    llm_data = state["llm_output"]
    decision = state["decision"]
    confidence = state["confidence"]
    ev = state["evidence_score"]

    factors = _build_decision_factors(ev)

    response = DecisionResponse(
        learner_id=ctx.learner_id,
        lesson_id=ctx.lesson_id,
        context_version=ctx.context_version,
        decision=decision,
        reasoning=llm_data["reasoning"],
        confidence=llm_data["confidence"],
        signals=llm_data["signals"],
        decision_factors=factors,
        rejected_alternatives=llm_data["rejected_alternatives"],
        reasoning_source=ReasoningSourceEnum.llm,
        metadata={
            "evidence_scores": {
                "reinforce": round(ev.reinforce, 3),
                "advance":   round(ev.advance, 3),
                "mentor":    round(ev.mentor, 3),
            },
        },
    )
    return {"final_response": response}


def node_fallback_response(state: GraphState) -> dict:
    """
    Node 7b — Build DecisionResponse using deterministic fallback.
    Wraps: fallback.build_fallback_response()

    Used when:
    - LLM call failed / timed out / returned invalid output
    - FORCE_FALLBACK=true
    """
    ctx = state["ctx"]
    decision = state["decision"]
    confidence = state["confidence"]
    ev = state["evidence_score"]
    b = state["signals"]
    selection_note = state.get("selection_note", "")
    override = state.get("override_result")
    override_reason = override.reason if override else None
    advance_blocks = state.get("advance_block_reasons") or []

    response = build_fallback_response(
        ctx=ctx,
        decision=decision,
        confidence=confidence,
        ev=ev,
        b=b,
        selection_note=selection_note,
        override_reason=override_reason,
        advance_block_reasons=advance_blocks,
    )
    return {"final_response": response}


# ===========================================================================
# CONDITIONAL EDGE FUNCTIONS
# Each returns a string key used to select the next node.
# ===========================================================================

def route_data(state: GraphState) -> str:
    """After node_check_data_sufficiency: route based on data quality."""
    if not state.get("data_sufficient", True):
        return "insufficient"
    return "continue"


def route_override(state: GraphState) -> str:
    """After node_evaluate_overrides: route based on whether an override fired."""
    if state.get("override_fired", False):
        return "override_fired"
    return "continue"


def route_llm(state: GraphState) -> str:
    """After node_llm_reasoning: route based on LLM success."""
    if state.get("llm_succeeded", False):
        return "llm_success"
    return "llm_failed"


# ===========================================================================
# GRAPH CONSTRUCTION
# ===========================================================================

def build_decision_graph() -> Any:
    """
    Construct and compile the LangGraph StateGraph for the decision workflow.

    Returns a compiled graph whose .invoke(state) method runs the full pipeline.
    """
    builder = StateGraph(GraphState)

    # ---- Register nodes --------------------------------------------------
    builder.add_node("extract_signals",       node_extract_signals)
    builder.add_node("check_data",            node_check_data_sufficiency)
    builder.add_node("insufficient_data",     node_insufficient_data)
    builder.add_node("evaluate_overrides",    node_evaluate_overrides)
    builder.add_node("override_path",         node_override_path)
    builder.add_node("score_evidence",        node_score_evidence)
    builder.add_node("select_candidate",      node_select_candidate)
    builder.add_node("llm_reasoning",         node_llm_reasoning)
    builder.add_node("build_llm_response",    node_build_llm_response)
    builder.add_node("fallback_response",     node_fallback_response)

    # ---- Edges -----------------------------------------------------------

    # START → extract signals → check data
    builder.add_edge(START, "extract_signals")
    builder.add_edge("extract_signals", "check_data")

    # Conditional: data sufficient?
    builder.add_conditional_edges(
        "check_data",
        route_data,
        {
            "insufficient": "insufficient_data",
            "continue":     "evaluate_overrides",
        },
    )

    # Insufficient data exits immediately
    builder.add_edge("insufficient_data", END)

    # Conditional: override fired?
    builder.add_conditional_edges(
        "evaluate_overrides",
        route_override,
        {
            "override_fired": "override_path",
            "continue":       "score_evidence",
        },
    )

    # Override path → LLM reasoning (then same LLM routing)
    builder.add_edge("override_path", "llm_reasoning")

    # Normal path: score → select → LLM
    builder.add_edge("score_evidence", "select_candidate")
    builder.add_edge("select_candidate", "llm_reasoning")

    # Conditional: LLM succeeded?
    builder.add_conditional_edges(
        "llm_reasoning",
        route_llm,
        {
            "llm_success": "build_llm_response",
            "llm_failed":  "fallback_response",
        },
    )

    # Both response nodes → END
    builder.add_edge("build_llm_response", END)
    builder.add_edge("fallback_response",  END)

    return builder.compile()


# Module-level compiled graph instance — import and call .invoke()
decision_graph = build_decision_graph()
