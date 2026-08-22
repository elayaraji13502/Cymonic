from .schemas import build_empty_rejected_alternatives


def generate_fallback_decision(context):
    latest = context.get("latest_score")
    average = context.get("average_score")
    trend = context.get("trend")
    mastery = context.get("mastery")
    engagement = context.get("engagement")
    attempts = context.get("attempts", 0)
    previous_reinforcement = context.get("previous_reinforcement", 0)
    risk_flags = context.get("risk_flags") or []
    certification_risk = context.get("certification_risk")
    threshold = context.get("threshold")

    if latest is None or average is None:
        raise ValueError("Missing learner scores for fallback evaluation")

    threshold = threshold if threshold is not None else 75
    signals = []
    contradiction = False

    if mastery == "mastered" and latest >= threshold and trend in {"improving", "stable"} and not risk_flags:
        decision = "advance"
        reasons = "The learner has reached mastery, remains above the required threshold, and shows stable progress without material risk signals."
        confidence = 0.82
        signals = ["mastery_reached", "performance_above_threshold", "stable_or_improving_trend"]
    elif previous_reinforcement >= 2 or certification_risk in {"high", "critical"}:
        decision = "mentor"
        reasons = "The learner has repeated intervention history or elevated certification risk, which points to a need for guided support rather than progression."
        confidence = 0.8
        signals = ["repeated_failure", "high_certification_risk"]
    elif latest < threshold or mastery != "mastered":
        decision = "reinforce"
        reasons = "The learner has not yet reached mastery and the current evidence supports reinforcement before progression."
        confidence = 0.78
        signals = ["mastery_not_reached", "below_threshold", "needs_support"]
    else:
        decision = "mentor"
        reasons = "The learner's context is mixed and not strong enough for unqualified advancement, so guided intervention is the safer choice."
        confidence = 0.64
        signals = ["mixed_evidence", "requires_guidance"]

    if trend == "declining" and latest >= threshold:
        contradiction = True
        reasons = "The latest score is strong, but the declining trend, low engagement, and risk signals indicate a conflict: advancement may be premature even though the score is high."
        confidence = max(0.44, confidence - 0.18)
        signals.append("declining_trend_despite_high_score")
        if decision == "advance":
            decision = "mentor"

    if engagement in {"low", "declining"} and trend in {"declining", "stable"} and previous_reinforcement == 0 and decision == "reinforce":
        reasons = "The learner is underperforming and disengaged, but there is no prior reinforcement history yet, so reinforcement is still the least risky path."
        signals.append("low_engagement")

    if risk_flags and decision == "reinforce":
        contradiction = True
        reasons = reasons + " The signals are conflicting because performance is partly acceptable while risk flags suggest caution."
        signals.append("conflicting_signals")

    if previous_reinforcement >= 1 and engagement in {"low", "declining"} and trend == "declining" and decision == "reinforce":
        decision = "mentor"
        reasons = "The learner is underperforming and disengaged after previous reinforcement, so continued reinforcement without adjustment is not the safest choice."
        confidence = max(0.55, confidence - 0.12)
        signals.append("persistent_failure_after_intervention")

    if attempts is not None and attempts <= 1:
        confidence = min(confidence, 0.7)
        reasons += " Insufficient historical data limits confidence in the recommendation."
        signals.append("insufficient_history")

    rejected = build_empty_rejected_alternatives()
    rejected["reinforce"] = "The learner is already showing sufficient progress, so reinforcement would repeat support without clear need." if decision != "reinforce" else "The learner has not yet met mastery and needs additional practice."
    rejected["advance"] = "Mastery has not been sufficiently demonstrated, or risk signals suggest advancement would be premature." if decision != "advance" else "The learner has reached the threshold and is ready to progress."
    rejected["mentor"] = "There is not enough evidence of sustained failure or persistent risk to justify mentor escalation." if decision != "mentor" else "The learner is showing repeated difficulty and needs guided support."

    if contradiction:
        signals.append("risk_conflict")

    return {
        "decision": decision,
        "reasoning": reasons,
        "confidence": float(min(max(confidence, 0.0), 1.0)),
        "signals": signals,
        "rejected_alternatives": rejected,
        "reasoning_source": "fallback",
    }
