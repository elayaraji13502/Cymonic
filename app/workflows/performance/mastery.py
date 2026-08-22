"""
Mastery evaluator for Workflow 2 — Context & Performance Analysis.

Design principles
-----------------
* Mastery is NOT claimed from a single high score if broader evidence contradicts it.
* The evaluator considers: latest score, recent mean, consistency (std-dev proxy),
  and attempt count.
* It returns both a status and a human-readable evidence string so Workflow 3
  can reason over the explanation, not just the label.

Mastery levels
--------------
mastered        – strong, consistent evidence above the threshold
approaching     – recent scores are near or above the threshold but not yet consistent
not_mastered    – scores are clearly below the threshold
insufficient_data – not enough attempts to make a determination

Thresholds used internally
--------------------------
APPROACHING_RATIO   – how close to the mastery threshold "approaching" begins
                      (e.g. 0.90 means within 10 % of the threshold)
CONSISTENCY_WINDOW  – how many recent scores to use for consistency checks
MIN_ATTEMPTS_MASTERY – minimum attempts before "mastered" can be claimed
"""

from __future__ import annotations

from typing import List, Tuple

from app.schemas.performance import MasteryStatus

# A learner is "approaching" if their recent mean is at least this fraction of the threshold.
APPROACHING_RATIO: float = 0.90

# Number of most-recent scores used for consistency evaluation.
CONSISTENCY_WINDOW: int = 3

# Minimum number of valid attempts before "mastered" can be declared.
MIN_ATTEMPTS_MASTERY: int = 2

# Maximum allowed standard-deviation-like spread for a "mastered" determination.
# If the recent scores vary by more than this, mastery is not yet consistent.
MAX_SPREAD_FOR_MASTERY: float = 10.0


def _recent_mean(scores: List[float], window: int) -> float:
    recent = scores[-window:] if len(scores) >= window else scores
    return sum(recent) / len(recent)


def _score_spread(scores: List[float], window: int) -> float:
    """Return the range (max – min) of the most recent `window` scores."""
    recent = scores[-window:] if len(scores) >= window else scores
    if len(recent) < 2:
        return 0.0
    return max(recent) - min(recent)


def evaluate_mastery(
    scores: List[float],
    mastery_threshold: float,
    latest_score: float | None,
) -> Tuple[MasteryStatus, str]:
    """
    Evaluate mastery status from multi-signal evidence.

    Parameters
    ----------
    scores:
        Chronologically ordered list of valid scores (oldest first).
        Must already be validated (0–100); corrupted values removed.
    mastery_threshold:
        The lesson's required mastery score (0–100).
    latest_score:
        The most recent valid score, or None if no valid scores exist.

    Returns
    -------
    (MasteryStatus, evidence_string)
    """
    if not scores or latest_score is None:
        return (
            "insufficient_data",
            "No valid assessment scores are available to evaluate mastery.",
        )

    if len(scores) < MIN_ATTEMPTS_MASTERY:
        # Only one score — cannot claim mastery or reliable approaching status
        if latest_score >= mastery_threshold:
            return (
                "approaching",
                (
                    f"Latest score ({latest_score:.1f}) meets the mastery threshold "
                    f"({mastery_threshold:.1f}), but only one attempt has been recorded. "
                    "Consistent performance across multiple attempts is required before "
                    "mastery can be confirmed."
                ),
            )
        approaching_floor = mastery_threshold * APPROACHING_RATIO
        if latest_score >= approaching_floor:
            return (
                "approaching",
                (
                    f"Latest score ({latest_score:.1f}) is near the mastery threshold "
                    f"({mastery_threshold:.1f}), but only one attempt has been recorded. "
                    "More attempts are needed to confirm a reliable trend."
                ),
            )
        return (
            "not_mastered",
            (
                f"Latest score ({latest_score:.1f}) is below the mastery threshold "
                f"({mastery_threshold:.1f}) with only one attempt recorded."
            ),
        )

    recent_mean = _recent_mean(scores, CONSISTENCY_WINDOW)
    spread = _score_spread(scores, CONSISTENCY_WINDOW)
    approaching_floor = mastery_threshold * APPROACHING_RATIO

    # --- mastered ---
    if (
        recent_mean >= mastery_threshold
        and latest_score >= mastery_threshold
        and spread <= MAX_SPREAD_FOR_MASTERY
    ):
        return (
            "mastered",
            (
                f"Recent mean score ({recent_mean:.1f}) and latest score ({latest_score:.1f}) "
                f"both meet the mastery threshold ({mastery_threshold:.1f}). "
                f"Score spread over recent attempts is {spread:.1f}, indicating consistent mastery."
            ),
        )

    # --- approaching: recent mean is near or above threshold but not yet consistent ---
    if recent_mean >= approaching_floor:
        if recent_mean >= mastery_threshold and spread > MAX_SPREAD_FOR_MASTERY:
            return (
                "approaching",
                (
                    f"Recent mean score ({recent_mean:.1f}) meets the mastery threshold "
                    f"({mastery_threshold:.1f}), but score spread ({spread:.1f}) indicates "
                    "inconsistent performance. Consistent mastery has not yet been demonstrated."
                ),
            )
        return (
            "approaching",
            (
                f"Recent mean score ({recent_mean:.1f}) is near the mastery threshold "
                f"({mastery_threshold:.1f}). Performance is trending toward mastery but "
                "has not yet demonstrated consistent achievement above the threshold."
            ),
        )

    # --- not_mastered ---
    return (
        "not_mastered",
        (
            f"Recent mean score ({recent_mean:.1f}) is below the mastery threshold "
            f"({mastery_threshold:.1f}). The learner has not yet demonstrated sufficient "
            "performance to approach mastery."
        ),
    )
