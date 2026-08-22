VALID_DECISIONS = {"reinforce", "advance", "mentor"}
REQUIRED_CONTEXT_KEYS = {
    "latest_score",
    "average_score",
    "trend",
    "attempts",
    "mastery",
    "threshold",
    "engagement",
    "learning_velocity",
    "previous_reinforcement",
    "reinforcement_effectiveness",
    "risk_flags",
    "certification_risk",
    "lesson_difficulty",
    "required_lesson",
    "previous_decisions",
}


def normalize_decision(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    return text if text in VALID_DECISIONS else None


def validate_context(context):
    if not isinstance(context, dict):
        raise ValueError("Missing learner context.")
    missing = sorted(REQUIRED_CONTEXT_KEYS - set(context.keys()))
    if missing:
        raise ValueError(f"Incomplete learner context. Missing: {', '.join(missing)}")
    return context


def build_empty_rejected_alternatives():
    return {"reinforce": "", "advance": "", "mentor": ""}
