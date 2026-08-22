"""
decision_engine/graph_state.py
==============================
LangGraph state definition for the Module 3 decision workflow.

The GraphState TypedDict is the single object that flows through every
node in the graph.  Each node reads what it needs and writes its outputs
back into the same dict.

Design rules
------------
- All fields are Optional so an empty state can be passed at the start.
- No business logic lives here — this is purely a data carrier.
- Every field maps directly to an intermediate or final product of the
  existing engine pipeline, so no new concepts are introduced.

Field groups
------------
  INPUT        : ctx                      — the incoming LearnerContext
  SIGNALS      : signals                  — output of extract_signals()
  OVERRIDES    : override_result          — output of evaluate_overrides()
  EVIDENCE     : evidence_score           — output of evaluate()
  DECISION     : decision, confidence,    — output of select_candidate()
                 selection_note
  LLM          : llm_output               — validated dict from call_llm()
                 llm_failed               — True if LLM path failed
  ADVANCE_BLOCK: advance_block_reasons    — reasons ADVANCE was blocked
  RESPONSE     : final_response           — the completed DecisionResponse
  ROUTING      : routing flags for conditional edges
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

# We use string-quoted forward refs for the engine types to avoid
# circular imports.  At runtime these are resolved lazily.


class GraphState(TypedDict, total=False):
    # ------------------------------------------------------------------ #
    # INPUT                                                                #
    # ------------------------------------------------------------------ #
    ctx: Any                        # LearnerContext (from schemas.py)

    # ------------------------------------------------------------------ #
    # SIGNALS  (output of node_extract_signals)                           #
    # ------------------------------------------------------------------ #
    signals: Any                    # SignalBundle (from signals.py)

    # ------------------------------------------------------------------ #
    # ROUTING flags set by conditional nodes                              #
    # ------------------------------------------------------------------ #
    data_sufficient: bool           # False → route to insufficient-data exit
    override_fired: bool            # True  → skip evidence scoring
    llm_succeeded: bool             # True  → use LLM response; False → fallback

    # ------------------------------------------------------------------ #
    # OVERRIDE  (output of node_evaluate_overrides)                       #
    # ------------------------------------------------------------------ #
    override_result: Optional[Any]  # OverrideResult | None

    # ------------------------------------------------------------------ #
    # EVIDENCE  (output of node_score_evidence)                           #
    # ------------------------------------------------------------------ #
    evidence_score: Optional[Any]   # EvidenceScore

    # ------------------------------------------------------------------ #
    # CANDIDATE SELECTION  (output of node_select_candidate)              #
    # ------------------------------------------------------------------ #
    decision: Optional[Any]         # DecisionEnum
    confidence: Optional[float]
    selection_note: Optional[str]
    advance_block_reasons: List[str]

    # ------------------------------------------------------------------ #
    # LLM REASONING  (output of node_llm_reasoning)                       #
    # ------------------------------------------------------------------ #
    llm_output: Optional[Dict[str, Any]]   # validated dict from call_llm()

    # ------------------------------------------------------------------ #
    # FINAL RESPONSE  (output of node_build_response)                     #
    # ------------------------------------------------------------------ #
    final_response: Optional[Any]   # DecisionResponse
