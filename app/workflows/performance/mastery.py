def evaluate_mastery(scores: list[int], threshold: int) -> dict:
    """Evaluate mastery status based on scores and threshold."""
    if threshold is None:
        raise ValueError("Missing lesson mastery threshold")
        
    if not scores:
        return {
            "status": "insufficient_data",
            "evidence": "No assessment history available to evaluate mastery."
        }
        
    valid_scores = [s for s in scores if 0 <= s <= 100]
    if not valid_scores:
        return {
            "status": "insufficient_data",
            "evidence": "No valid assessment history available to evaluate mastery."
        }
        
    latest = valid_scores[-1]
    
    if latest >= threshold:
        # Check consistency: are recent scores also good?
        if len(valid_scores) >= 2 and valid_scores[-2] >= threshold - 5:
            return {
                "status": "mastered",
                "evidence": f"Latest score ({latest}) and recent history demonstrate consistent performance above threshold ({threshold})."
            }
        elif len(valid_scores) >= 2:
            return {
                "status": "approaching",
                "evidence": f"Latest score ({latest}) is above threshold ({threshold}), but previous score ({valid_scores[-2]}) was lower. Needs consistency."
            }
        else:
            return {
                "status": "approaching",
                "evidence": f"Latest score ({latest}) is above threshold ({threshold}), but there is insufficient history to confirm consistent mastery."
            }
            
    if latest >= threshold - 10:
        return {
            "status": "approaching",
            "evidence": f"Latest score ({latest}) is nearing the threshold ({threshold})."
        }
        
    return {
        "status": "not_mastered",
        "evidence": f"Latest score ({latest}) is significantly below the threshold ({threshold})."
    }
