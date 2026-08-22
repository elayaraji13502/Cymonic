# Module 3 — Adaptive Decision Engine: Decision Policy

> **Owner:** Member 3  
> **Module role:** Receives structured learner context from Module 2. Produces exactly one decision — `reinforce`, `advance`, or `mentor` — with full reasoning.  
> **This module does NOT execute any Module 4 actions.**

---

## 1. Architecture Overview

```
LearnerContext (from Module 2)
        │
        ▼
  Signal Extraction        ← signals.py
        │
        ▼
  Data Validation          ← engine.py (insufficient-data guard)
        │
        ▼
  Hard Override Check      ← overrides.py
        │ (if override fires → skip to LLM/fallback)
        ▼
  Evidence Scoring         ← evaluator.py
  (weighted evidence model)
        │
        ▼
  Candidate Selection      ← evaluator.py
        │
        ▼
  Advance Blockers         ← overrides.py
  (post-selection check)
        │
        ▼
  LLM Reasoning Attempt    ← agent.py
        │ (on failure/unavailable)
        ▼
  Deterministic Fallback   ← fallback.py
        │
        ▼
  LLM Output Validation    ← validator.py
        │
        ▼
  DecisionResponse         ← schemas.py
```

---

## 2. Why a Weighted Evidence Model?

Pure rule chains (score > 80 → advance) create brittle decision cliffs where
a single point difference flips the entire outcome. Real learning adaptation
requires multiple signals to reinforce or contradict each other.

The weighted evidence model:
- Accumulates named, weighted signals per candidate.
- The winning candidate is the one with the most accumulated evidence.
- Blocking conditions subtract weight (soft) or hard-block (override layer).
- Every signal that contributed is logged in the response.

This means **the same score produces a different decision in a different context**,
because different signals fire at different weights.

---

## 3. Configurable Thresholds

All numeric thresholds live in `app/config/decision_policy.py` as a frozen `PolicyConfig` dataclass.

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `MIN_MASTERY_SCORE` | 75.0 | Minimum score to be considered "passing" |
| `MIN_CONSISTENT_ATTEMPTS` | 3 | Minimum attempts before mastery can be confirmed |
| `MASTERY_CONSISTENCY_WINDOW` | 3 | Recent attempts that must all be ≥ threshold |
| `MAX_REINFORCEMENT_ATTEMPTS` | 3 | Trigger escalation after this many cycles |
| `HIGH_REINFORCEMENT_COUNT` | 2 | Above this, reinforcement signals are down-weighted |
| `LOW_ENGAGEMENT_THRESHOLD` | "low" | Engagement level considered disengaged |
| `INACTIVITY_DAYS_SOFT` | 3 | Mild inactivity concern |
| `INACTIVITY_DAYS_HARD` | 7 | Strong mentor signal |
| `MENTOR_RISK_FLAG_COUNT` | 2 | Risk flag count that triggers mentor weight |
| `MIN_DECISION_CONFIDENCE` | 0.55 | Minimum confidence floor |
| `INSUFFICIENT_DATA_CONFIDENCE` | 0.30 | Confidence cap when data is missing |
| `ADVANCE_BLOCK_BELOW_SCORE` | 65.0 | Hard advance floor regardless of mastery flag |

---

## 4. REINFORCE Policy

**Intent:** Give the learner more opportunity to close a bridgeable gap through
continued self-directed practice.

**Required:** Mastery NOT achieved.

**Supporting signals (contribute positive weight):**
- `mastery_not_reached` — primary requirement
- `trend_improving` — learner is moving in the right direction
- `high_engagement` / `medium_engagement` — learner is still engaged
- `low_attempt_count` — limited practice history; more attempts warranted
- `no_prior_reinforcement` — first cycle; give it a chance
- `intervention_effective` / `intervention_partial` — prior reinforcement helped
- `recoverable_gap` — score is within 20 pts of threshold

**Blocking conditions (subtract weight / hard-block):**
- `max_reinforcement_hit` + `intervention_ineffective` → hard override to MENTOR
- `low_engagement` + `trend_declining` + sufficient history → reduces REINFORCE score
- Critical risk flags → hard override to MENTOR
- Mastery already achieved → ADVANCE path

**Critical rule:** REINFORCE is NOT indefinite. Exceeding `MAX_REINFORCEMENT_ATTEMPTS`
with ineffective results hard-overrides to MENTOR.

---

## 5. ADVANCE Policy

**Intent:** Confirm and reward demonstrated mastery with forward progress.

**Required (ALL must hold):**
1. `mastery_status` = `mastered`
2. `latest_score` ≥ `MIN_MASTERY_SCORE` (75)
3. `attempt_count` ≥ `MIN_CONSISTENT_ATTEMPTS` (3)
4. `mastery_consistency` = `consistent` OR recent scores all above threshold

**Supporting signals:**
- `trend_stable` / `trend_improving`
- `high_engagement` / `medium_engagement`
- `velocity_fast`

**Hard blockers (prevent ADVANCE even if evidence score is highest):**
- `latest_score` < `ADVANCE_BLOCK_BELOW_SCORE` (65) — guards stale mastery flags
- `single_high_spike` without consistent history — spike ≠ mastery (e.g. 45→52→91)
- `trend_declining` + `engagement_low` — conflicting evidence
- `attempt_count` < `MIN_CONSISTENT_ATTEMPTS` — insufficient history

**Anti-pattern explicitly guarded:**
> A sudden jump from low scores to a single high score does NOT constitute mastery.
> Example: `45 → 52 → 91` is detected as a spike and ADVANCE is blocked.

---

## 6. MENTOR Policy

**Intent:** Recognise that automated adaptation is insufficient; a human coach must intervene.

**MENTOR does NOT mean "score is low." It means the learner is stuck.**

**Strong signals (high weight):**
- `max_reinforcement_hit` + `intervention_ineffective` + `mastery_not_reached` → hard override
- Critical risk flags (`dropout_risk`, `exam_failing`, etc.) → hard override
- `trend_declining` + `sufficient_history`
- `score_far_below_mastery` + `trend_declining`
- `hard_inactivity` (≥ 7 days)

**Moderate signals:**
- `low_engagement`
- `has_risk_flags` (count ≥ threshold)
- `prior_mentor_intervention` without improvement
- `persistent_weakness` + `high_reinforcement`
- `velocity_stalled`

**Soft inhibitors (reduce MENTOR probability):**
- `trend_improving` — learner may still recover
- `high_engagement` — learner is engaged, reduce urgency

---

## 7. Override Conditions (Priority Order)

Overrides are evaluated BEFORE evidence scoring. The first firing override locks the decision.

| Priority | Condition | Decision |
|----------|-----------|----------|
| 1 | Any `CRITICAL_RISK_FLAGS` present | MENTOR |
| 2 | `reinforcement_count` ≥ MAX **AND** `effectiveness` = ineffective **AND** not mastered | MENTOR |
| 3 | `mastery` = mastered **AND** consistent **AND** sufficient history **AND** score ≥ threshold **AND** no spike | ADVANCE |
| 4 | `reinforcement_count` ≥ MAX **AND** not mastered **AND** NOT (improving + high engagement) | MENTOR |

---

## 8. Conflicting Signals

The engine is explicitly designed to handle contradictory evidence. Examples:

**Score=90, trend=declining, engagement=low, reinforcement=2:**
- ADVANCE is blocked by: declining trend + low engagement + single spike pattern
- REINFORCE is weakened by: high reinforcement count + low engagement
- MENTOR accumulates: declining trend + low engagement + inactivity signals
- Result: MENTOR or REINFORCE depending on relative weights; reasoning explains the conflict

**Score=58, trend=improving, engagement=high, reinforcement=0:**
- REINFORCE accumulates: mastery_not_reached + improving + high engagement + no prior reinforcement
- MENTOR has almost no signal
- Result: REINFORCE; reasoning emphasises the improving momentum

**The reasoning always identifies which signals dominated and why competing signals were weaker.**

---

## 9. Insufficient Data Handling

When `latest_score` is `null` OR `mastery_status` is `unknown`:

- Engine does NOT fabricate evidence.
- Returns `confidence` ≤ `INSUFFICIENT_DATA_CONFIDENCE` (0.30).
- Decision defaults to `reinforce` (safest option pending more data).
- `reasoning_source` = `fallback`.
- `signals` includes `data_insufficient`.
- Missing fields are listed in `metadata`.

---

## 10. LLM Reasoning Layer

The LLM is a **reasoning narrator**, not a decision maker.

**What the LLM receives:**
- The pre-computed decision (from the policy engine)
- Evidence scores for all three candidates
- Named signals that fired
- Full learner context

**What the LLM cannot do:**
- Override the policy decision
- Invent signals not present in the context
- Return a decision not in `{reinforce, advance, mentor}`

**Validation applied to every LLM response:**
1. JSON parseable (extracts from markdown fences if needed)
2. `decision` matches policy engine's decision
3. `reasoning` ≥ 20 characters and non-empty
4. `confidence` ∈ [0.0, 1.0]
5. `signals` is a non-empty list
6. `rejected_alternatives` is a non-empty dict

**On any validation failure:** deterministic fallback is used automatically.
`reasoning_source` distinguishes `"llm"` from `"fallback"`.

---

## 11. API Contract

### POST `/api/v1/decisions/evaluate`

**Request:** `LearnerContext` JSON (see `schemas.py`)  
**Response:** `DecisionResponse` JSON

Key response fields:

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `reinforce` \| `advance` \| `mentor` | The adaptive decision |
| `reasoning` | string | Human-readable explanation |
| `confidence` | float [0,1] | Confidence in the decision |
| `signals` | list[string] | Signals that drove the decision |
| `decision_factors` | object | Supporting/blocking signals per candidate |
| `rejected_alternatives` | object | Why each non-winning candidate was rejected |
| `reasoning_source` | `llm` \| `fallback` | Whether LLM or fallback generated the reasoning |

### GET `/api/v1/decisions/test-cases`
Lists all 8 predefined test case names.

### POST `/api/v1/decisions/test/{case_name}`
Runs a predefined test case by name. Returns full decision response.

---

## 12. Test Cases

| Case | Score | Trend | Engagement | Reinforcement | Expected |
|------|-------|-------|------------|---------------|----------|
| CASE_01 | 62 | improving | high | 0 | REINFORCE |
| CASE_02 | 88 | stable | high | 1 (effective) | ADVANCE |
| CASE_03 | 48 | declining | low | 3 (ineffective) | MENTOR |
| CASE_04 | 90 | declining | low | 2 | NOT ADVANCE |
| CASE_05 | 58 | improving | high | 0 | REINFORCE |
| CASE_06 | null | unknown | unknown | 0 | Low-confidence default |
| CASE_07 | 82 | declining | low | 2 | NOT ADVANCE (conflict) |
| CASE_08 | 55 | declining | medium | 3 (ineffective) | MENTOR |

---

## 13. Running the Module

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env — OPENAI_API_KEY is optional (fallback works without it)

# Start the API server
uvicorn app.main:app --reload --port 8003

# Swagger UI
open http://localhost:8003/docs

# Run standalone test script (no LLM needed)
python -m scripts.test_decisions

# Run pytest tests
pytest app/tests/test_decisions.py -v
```

---

## 14. Example curl Commands

```bash
# Evaluate a learner context
curl -X POST http://localhost:8003/api/v1/decisions/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": 101,
    "lesson_id": 12,
    "context_version": 1,
    "performance": {
      "latest_score": 62,
      "average_score": 64,
      "previous_scores": [58, 62, 64],
      "trend": "improving",
      "attempt_count": 3
    },
    "mastery": {
      "status": "not_mastered",
      "threshold": 70,
      "consistency": "insufficient"
    },
    "engagement": {"level": "high", "inactivity_days": 1},
    "learning": {"velocity": "normal", "completion_percentage": 65},
    "intervention": {
      "reinforcement_count": 0,
      "effectiveness": "none",
      "previous_mentor_intervention": false
    },
    "course": {
      "lesson_difficulty": "medium",
      "required_lesson": true,
      "certification_required": true,
      "certification_risk": "medium"
    },
    "risk_flags": [],
    "weakness_tags": ["recursion"],
    "strength_tags": ["problem_solving"]
  }'

# List test cases
curl http://localhost:8003/api/v1/decisions/test-cases

# Run a specific test case
curl -X POST http://localhost:8003/api/v1/decisions/test/CASE_03_REPEATED_FAILURE

# Health check
curl http://localhost:8003/api/v1/decisions/health
```
