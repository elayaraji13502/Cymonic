def build_reasoning_prompt(context):
    latest = context.get("latest_score")
    average = context.get("average_score")
    trend = context.get("trend")
    mastery = context.get("mastery")
    threshold = context.get("threshold")
    engagement = context.get("engagement")
    attempts = context.get("attempts")
    previous_reinforcement = context.get("previous_reinforcement")
    effectiveness = context.get("reinforcement_effectiveness")
    risk_flags = context.get("risk_flags")
    certification_risk = context.get("certification_risk")
    required_lesson = context.get("required_lesson")
    lesson_difficulty = context.get("lesson_difficulty")

    return {
        "system": "You are a cautious learning decision engine. Reason over learner context, not score thresholds alone.",
        "user": (
            "LEARNER CONTEXT:\n"
            f"Performance: latest_score={latest} average_score={average} trend={trend}\n"
            f"Mastery: status={mastery} threshold={threshold}\n"
            f"Engagement: {engagement}\n"
            f"Attempts: {attempts}\n"
            f"Intervention: reinforcement_count={previous_reinforcement} effectiveness={effectiveness}\n"
            f"Risk: risk_flags={risk_flags} certification_risk={certification_risk}\n"
            f"Lesson: difficulty={lesson_difficulty} required={required_lesson}\n\n"
            "Instructions: Analyze the evidence. Compare reinforce, advance, and mentor. Select exactly one. "
            "Explain why. Identify supporting signals. Explain why the strongest alternatives were rejected. "
            "Return strict JSON with keys: decision, reasoning, confidence, signals, rejected_alternatives. "
            "decision must be one of reinforce, advance, mentor. confidence must be a number from 0.0 to 1.0. "
            "The reasoning must be grounded only in the provided context."
        ),
    }
