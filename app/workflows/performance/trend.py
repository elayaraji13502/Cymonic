def calculate_trend(scores: list[int]) -> str:
    """Calculate the performance trend based on historical scores.
    
    Scores should be ordered from oldest to newest.
    """
    if not scores:
        return "insufficient_data"
    
    # Filter out corrupted scores
    valid_scores = [s for s in scores if 0 <= s <= 100]
    
    if len(valid_scores) < 2:
        return "insufficient_data"
    
    # Compare recent performance against earlier performance
    # For simplicity, compare the average of the first half to the second half
    mid = len(valid_scores) // 2
    first_half = valid_scores[:mid]
    second_half = valid_scores[mid:]
    
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    
    diff = avg_second - avg_first
    
    if diff >= 3:
        return "improving"
    elif diff <= -3:
        return "declining"
    else:
        return "stable"
