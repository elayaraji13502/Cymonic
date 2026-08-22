"""
decision_engine/policy.py
=========================
Narrative decision policy — the "constitution" of the decision engine.

This module does NOT contain logic.  It contains:
  1. Prose descriptions of each decision condition (used in docs/prompts).
  2. SIGNAL_LABELS — mapping signal identifiers to human-readable strings
     (used in reasoning text and API responses).

Having this separate from evaluator.py keeps the rules
discoverable and editable without touching executable code.
"""

from __future__ import annotations

from app.config.decision_policy import POLICY

# ---------------------------------------------------------------------------
# Narrative policy definitions
# ---------------------------------------------------------------------------

REINFORCE_POLICY = f"""
REINFORCE — Additional practice or exercises

Primary intent: Give the learner more opportunity to close a performance gap
that is bridgeable through continued self-directed effort.

Required conditions (must hold):
  • Mastery has NOT been achieved.
  • The gap between current score and mastery threshold is ≤ 20 points
    (recoverable gap), OR the learner shows an improving trend.

Supporting conditions (weighted positively):
  • Score trend is improving.
  • Engagement is medium or high.
  • Reinforcement count is below {POLICY.MAX_REINFORCEMENT_ATTEMPTS}.
  • Previous reinforcement was effective or partially effective, or
    there has been no prior reinforcement at all.
  • Learning velocity is normal or fast.
  • No critical risk flags are present.

Blocking conditions (prevent REINFORCE):
  • Reinforcement count ≥ {POLICY.MAX_REINFORCEMENT_ATTEMPTS} AND
    intervention effectiveness is 'ineffective'.
  • Engagement is low AND trend is declining AND attempts ≥ {POLICY.MIN_CONSISTENT_ATTEMPTS}.
  • Critical risk flags are present.
  • Mastery is already achieved.
"""

ADVANCE_POLICY = f"""
ADVANCE — Proceed to the next lesson or assessment

Primary intent: Confirm and reward demonstrated mastery with forward progress.

Required conditions (ALL must hold):
  • Mastery status = mastered  (from Module 2).
  • Latest score ≥ {POLICY.MIN_MASTERY_SCORE}.
  • Sufficient assessment history: ≥ {POLICY.MIN_CONSISTENT_ATTEMPTS} attempts.
  • Mastery consistency is 'consistent' OR recent scores are all
    above threshold.

Supporting conditions (weighted positively):
  • Trend is stable or improving.
  • Engagement is medium or high.
  • Learning velocity is normal or fast.
  • No blocking risk flags.

Blocking conditions (prevent ADVANCE):
  • Latest score < {POLICY.ADVANCE_BLOCK_BELOW_SCORE} (guards stale mastery flag).
  • Trend is declining AND engagement is low (conflicting evidence rule).
  • Critical risk flags present.
  • Single-attempt high spike without consistent history.

Anti-pattern explicitly guarded: a sudden jump from low scores to a single
high score does NOT constitute mastery (e.g. 45 → 52 → 91 is flagged as a
high-spike, not consistent mastery, unless sufficient prior history exists).
"""

MENTOR_POLICY = f"""
MENTOR — Escalate to human support

Primary intent: Recognise that automated adaptation is insufficient and a
human coach, tutor, or advisor must intervene.

MENTOR does NOT mean "score is low."  It means the learner is stuck in a
pattern the automated system cannot resolve.

Strong mentor signals:
  • Reinforcement count ≥ {POLICY.MAX_REINFORCEMENT_ATTEMPTS} AND
    intervention_effectiveness = 'ineffective' AND mastery not achieved.
  • Declining trend AND high attempt count AND no improvement.
  • Low engagement AND high inactivity (≥ {POLICY.INACTIVITY_DAYS_HARD} days).
  • Critical risk flags (e.g. dropout_risk, exam_failing).
  • Previous mentor intervention was already attempted and the learner
    has returned without improvement.
  • Persistent weakness tags with no corresponding strength growth
    after multiple reinforcement cycles.
  • Score declining despite repeated reinforcement.

Mild mentor signals (increase probability but do not decide alone):
  • Risk flag count ≥ {POLICY.MENTOR_RISK_FLAG_COUNT}.
  • Prior mentor intervention.
  • Stalled learning velocity.
  • Certification risk = high.
"""

# ---------------------------------------------------------------------------
# Human-readable signal labels
# ---------------------------------------------------------------------------

SIGNAL_LABELS: dict[str, str] = {
    # Mastery
    "mastery_achieved":            "Mastery has been achieved",
    "mastery_not_reached":         "Mastery threshold not yet reached",
    "mastery_unknown":             "Mastery status is unknown",
    "mastery_consistent":          "Performance is consistently above mastery threshold",

    # Performance
    "score_above_mastery":         "Latest score is at or above mastery threshold",
    "score_near_mastery":          "Latest score is within 10 pts of mastery threshold",
    "score_far_below_mastery":     "Latest score is >20 pts below mastery threshold",
    "recoverable_gap":             "Performance gap is recoverable (≤20 pts below threshold)",
    "single_high_spike":           "Latest score is a spike (≥20 pts above average) — insufficient for mastery confirmation",

    # Trend
    "trend_improving":             "Performance trend is improving",
    "trend_stable":                "Performance trend is stable",
    "trend_declining":             "Performance trend is declining",
    "trend_unknown":               "Performance trend is unknown",

    # History
    "sufficient_history":          f"Sufficient assessment history (≥{POLICY.MIN_CONSISTENT_ATTEMPTS} attempts)",
    "low_attempt_count":           f"Low attempt count (<{POLICY.MIN_CONSISTENT_ATTEMPTS}) — limited evidence",

    # Engagement
    "high_engagement":             "Engagement level is high",
    "medium_engagement":           "Engagement level is medium",
    "low_engagement":              "Engagement level is low",
    "engagement_unknown":          "Engagement level is unknown",
    "soft_inactivity":             f"Mild inactivity (≥{POLICY.INACTIVITY_DAYS_SOFT} days)",
    "hard_inactivity":             f"Prolonged inactivity (≥{POLICY.INACTIVITY_DAYS_HARD} days)",

    # Velocity
    "velocity_fast":               "Learning velocity is fast",
    "velocity_stalled":            "Learning velocity is stalled",

    # Intervention
    "no_prior_reinforcement":      "No prior reinforcement cycles attempted",
    "low_reinforcement_count":     "Reinforcement count is below the escalation threshold",
    "high_reinforcement_count":    f"Reinforcement count is at or above {POLICY.HIGH_REINFORCEMENT_COUNT}",
    "max_reinforcement_hit":       f"Maximum reinforcement cycles ({POLICY.MAX_REINFORCEMENT_ATTEMPTS}) reached",
    "intervention_effective":      "Previous reinforcement was effective",
    "intervention_partial":        "Previous reinforcement was partially effective",
    "intervention_ineffective":    "Previous reinforcement was ineffective — automated approach is not working",
    "prior_mentor_intervention":   "A previous mentor intervention has already been attempted",

    # Course
    "required_lesson":             "This is a required lesson",
    "certification_required":      "Certification is required — progress decisions carry higher stakes",
    "certification_risk_high":     "High certification risk detected",
    "lesson_difficulty_hard":      "Lesson difficulty is high",

    # Risk
    "has_risk_flags":              "Multiple risk flags are present",
    "critical_risk":               "Critical risk flag detected — immediate escalation needed",

    # Weakness
    "persistent_weakness":         "Persistent weakness tags present without corresponding mastery growth",

    # Data quality
    "data_insufficient":           "Insufficient data to make a high-confidence decision",
    "conflicting_signals":         "Conflicting signals detected — see reasoning for resolution",
}


def label(signal_id: str) -> str:
    """Return the human-readable label for a signal identifier."""
    return SIGNAL_LABELS.get(signal_id, signal_id.replace("_", " ").capitalize())
