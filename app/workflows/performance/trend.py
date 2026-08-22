"""
Trend calculator for Workflow 2 — Context & Performance Analysis.

Algorithm
---------
Given a chronologically ordered list of valid scores (oldest → newest):

1. If fewer than 2 scores exist → "insufficient_data"
2. If exactly 2 scores → compare directly (no window averaging needed)
3. If 3 or more scores → split into an "early" half and a "recent" half,
   compute the mean of each half, then compare the means.

Thresholds
----------
- |Δ mean| < STABLE_THRESHOLD  → "stable"
- Δ mean ≥  IMPROVING_THRESHOLD → "improving"
- Δ mean ≤ -DECLINING_THRESHOLD → "declining"
- Otherwise                     → "stable"

These thresholds are intentionally conservative so that a single lucky
high score does not flip the trend to "improving".
"""

from __future__ import annotations

from typing import List

from app.schemas.performance import ScoreTrend

# A mean difference smaller than this is considered noise, not a real trend.
STABLE_THRESHOLD: float = 3.0

# A mean difference at least this large is considered a meaningful improvement.
IMPROVING_THRESHOLD: float = 3.0

# A mean difference at least this negative is considered a meaningful decline.
DECLINING_THRESHOLD: float = 3.0


def calculate_trend(scores: List[float]) -> ScoreTrend:
    """
    Derive a score trend from a chronologically ordered list of valid scores.

    Parameters
    ----------
    scores:
        Chronologically ordered list of valid scores (oldest first).
        Scores must already be validated (0–100); corrupted values must be
        removed before calling this function.

    Returns
    -------
    ScoreTrend literal: "improving" | "stable" | "declining" | "insufficient_data"
    """
    if len(scores) < 2:
        return "insufficient_data"

    if len(scores) == 2:
        delta = scores[-1] - scores[0]
        if delta >= IMPROVING_THRESHOLD:
            return "improving"
        if delta <= -DECLINING_THRESHOLD:
            return "declining"
        return "stable"

    # Split into early and recent halves.
    # For an odd number of scores the middle score is included in the recent half
    # so that the most recent performance is weighted slightly more.
    midpoint = len(scores) // 2
    early_scores = scores[:midpoint]
    recent_scores = scores[midpoint:]

    early_mean = sum(early_scores) / len(early_scores)
    recent_mean = sum(recent_scores) / len(recent_scores)
    delta = recent_mean - early_mean

    if delta >= IMPROVING_THRESHOLD:
        return "improving"
    if delta <= -DECLINING_THRESHOLD:
        return "declining"
    return "stable"
