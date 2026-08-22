from app.workflows.performance.mastery import evaluate_mastery
from app.workflows.performance.trend import calculate_trend


def build_context_package(learner_id: int, lesson_id: int, raw_data: dict) -> dict:
    """Build the structured learner context package for Workflow 3."""
    
    scores = raw_data.get("scores", [])
    
    # Optimize: Avoid O(N) scan on massive histories by iterating backwards
    # and stopping once we have the 20 most recent valid scores.
    recent_scores = []
    for s in reversed(scores):
        if 0 <= s <= 100:
            recent_scores.append(s)
            if len(recent_scores) == 20:
                break
    recent_scores.reverse()
    
    latest_score = recent_scores[-1] if recent_scores else None
    average_score = sum(recent_scores) / len(recent_scores) if recent_scores else None
    
    # We still need total valid attempt count, but we can optimize by only counting
    attempt_count = sum(1 for s in scores if 0 <= s <= 100)
    
    trend = calculate_trend(recent_scores)
    
    threshold = raw_data.get("threshold")
    if threshold is None:
        raise ValueError("Missing lesson mastery threshold")
        
    mastery = evaluate_mastery(recent_scores, threshold)
    
    engagement_raw = raw_data.get("engagement")
    if engagement_raw in ["high", "medium", "low"]:
        engagement_status = engagement_raw
    else:
        engagement_status = "unknown"
        
    # Attempt pressure
    if attempt_count == 0:
        attempt_pressure = "low"
    elif attempt_count <= 2:
        attempt_pressure = "low"
    elif attempt_count <= 4:
        attempt_pressure = "medium"
    else:
        attempt_pressure = "high"
        
    # Intervention effectiveness
    intervention_history = raw_data.get("intervention_history")
    if intervention_history is None:
        intervention_effectiveness = "insufficient_data"
        intervention_count = 0
    else:
        intervention_count = intervention_history.get("count", 0)
        if intervention_count == 0:
            intervention_effectiveness = "none"
        else:
            # Simple heuristic: if trend is improving after intervention, it's effective
            if trend == "improving":
                intervention_effectiveness = "effective"
            elif trend == "declining":
                intervention_effectiveness = "ineffective"
            else:
                intervention_effectiveness = "insufficient_data"
                
    # Certification risk
    cert_required = raw_data.get("certification_required", False)
    if not cert_required:
        cert_risk = "low"
    else:
        if mastery["status"] == "not_mastered" and attempt_pressure == "high":
            cert_risk = "high"
        elif mastery["status"] == "not_mastered" and trend == "declining":
            cert_risk = "high"
        elif mastery["status"] == "approaching" or attempt_pressure == "medium":
            cert_risk = "medium"
        else:
            cert_risk = "low"
            
    # Conflicting signals
    risk_flags = raw_data.get("risk_flags", [])
    if engagement_status == "low" and trend == "improving":
        risk_flags.append("low_engagement_but_improving")
    if latest_score and latest_score >= threshold and trend == "declining":
        risk_flags.append("high_score_but_declining")
        
    return {
        "learner_id": learner_id,
        "lesson_id": lesson_id,
        "performance": {
            "latest_score": latest_score,
            "average_score": round(average_score, 1) if average_score is not None else None,
            "trend": trend,
            "attempt_count": attempt_count,
            "attempt_pressure": attempt_pressure
        },
        "mastery": {
            "status": mastery["status"],
            "evidence": mastery["evidence"],
            "threshold": threshold
        },
        "engagement": {
            "status": engagement_status
        },
        "intervention": {
            "history": intervention_count,
            "effectiveness": intervention_effectiveness
        },
        "certification": {
            "required": cert_required,
            "risk": cert_risk
        },
        "risk_flags": list(set(risk_flags)),
        "strength_tags": raw_data.get("strength_tags", []),
        "weakness_tags": raw_data.get("weakness_tags", [])
    }
