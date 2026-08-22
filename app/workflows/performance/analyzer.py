"""
Performance analyzer for Workflow 2 — Context & Performance Analysis.

Responsibilities
----------------
* Fetch raw data from the database (bounded queries — no unlimited record loads).
* Validate and sanitise assessment scores (flag corrupted values outside 0–100).
* Deduplicate assessment records deterministically.
* Compute all contextual signals:
    - score trend
    - attempt pressure
    - mastery status + evidence
    - engagement status
    - intervention effectiveness
    - certification risk
    - conflicting signals
* Return a fully populated LearnerContextPackage.

This module does NOT make the final reinforce/advance/mentor decision.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.shared import (
    AssessmentRecord,
    InterventionHistory,
    Lesson,
    LearnerProgress,
    Course,
)
from app.schemas.performance import (
    AnalyzeRequest,
    AttemptPressure,
    CertificationContext,
    CertificationRisk,
    EngagementContext,
    EngagementStatus,
    InterventionContext,
    InterventionEffectiveness,
    LearnerContextPackage,
    MasteryContext,
    PerformanceContext,
    ScoreTrend,
)
from app.workflows.performance.mastery import evaluate_mastery
from app.workflows.performance.trend import calculate_trend

logger = logging.getLogger(__name__)

# Maximum number of assessment records to load per learner/lesson pair.
# Prevents unbounded memory use for learners with very large attempt histories.
MAX_ASSESSMENT_RECORDS: int = 200

# Score boundaries — values outside this range are treated as corrupted.
SCORE_MIN: float = 0.0
SCORE_MAX: float = 100.0

# Attempt pressure thresholds
ATTEMPT_PRESSURE_MEDIUM: int = 3
ATTEMPT_PRESSURE_HIGH: int = 6


def _parse_json_tags(raw: Optional[str]) -> List[str]:
    """Safely parse a JSON-encoded list of strings from the database."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _validate_scores(
    records: List[AssessmentRecord],
) -> Tuple[List[float], int]:
    """
    Separate valid scores from corrupted ones.

    Returns
    -------
    (valid_scores_chronological, corrupted_count)
    """
    valid: List[float] = []
    corrupted = 0
    for rec in records:
        if rec.score is None or not (SCORE_MIN <= rec.score <= SCORE_MAX):
            corrupted += 1
            logger.warning(
                "Corrupted score detected: assessment_id=%s score=%s — excluded from analysis.",
                rec.id,
                rec.score,
            )
        else:
            valid.append(rec.score)
    return valid, corrupted


def _deduplicate_records(records: List[AssessmentRecord]) -> List[AssessmentRecord]:
    """
    Remove exact duplicate assessment records deterministically.

    Two records are considered duplicates if they share the same
    (learner_id, lesson_id, score, attempted_at). The record with the
    lower primary key is kept so the result is stable across calls.
    """
    seen: set[tuple] = set()
    unique: List[AssessmentRecord] = []
    for rec in sorted(records, key=lambda r: r.id):
        key = (rec.learner_id, rec.lesson_id, rec.score, rec.attempted_at)
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    return unique


def _attempt_pressure(attempt_count: int) -> AttemptPressure:
    if attempt_count >= ATTEMPT_PRESSURE_HIGH:
        return "high"
    if attempt_count >= ATTEMPT_PRESSURE_MEDIUM:
        return "medium"
    return "low"


def _engagement_status(raw_level: Optional[str]) -> EngagementStatus:
    if not raw_level:
        return "unknown"
    normalised = raw_level.strip().lower()
    if normalised in ("high",):
        return "high"
    if normalised in ("medium", "moderate"):
        return "medium"
    if normalised in ("low",):
        return "low"
    return "unknown"


def _intervention_effectiveness(
    interventions: List[InterventionHistory],
) -> Tuple[InterventionEffectiveness, Optional[str]]:
    """
    Derive intervention effectiveness from the history of past interventions.

    Returns
    -------
    (effectiveness, last_intervention_type)
    """
    if not interventions:
        return "none", None

    # Only consider interventions where outcome has been recorded
    resolved = [i for i in interventions if i.was_effective is not None]
    last_type = interventions[-1].intervention_type if interventions else None

    if not resolved:
        return "insufficient_data", last_type

    effective_count = sum(1 for i in resolved if i.was_effective)
    if effective_count == 0:
        return "ineffective", last_type
    if effective_count == len(resolved):
        return "effective", last_type
    # Mixed results — report as insufficient_data so Workflow 3 can reason over it
    return "insufficient_data", last_type


def _certification_risk(
    certification_required: bool,
    valid_scores: List[float],
    mastery_status: str,
    mastery_threshold: float,
    risk_flags: List[str],
) -> CertificationRisk:
    """
    Compute certification risk as a contextual signal.

    This is NOT a pass/fail decision — it is evidence for Workflow 3.
    """
    if not certification_required:
        return "low"

    if mastery_status == "mastered":
        return "low"

    if not valid_scores:
        return "high"

    recent_mean = sum(valid_scores[-3:]) / len(valid_scores[-3:])
    gap = mastery_threshold - recent_mean

    # High risk: far below threshold or explicit risk flags present
    if gap > 20 or "at_risk" in risk_flags or "failing" in risk_flags:
        return "high"

    # Medium risk: below threshold but within reach
    if gap > 0:
        return "medium"

    # Recent mean is at or above threshold but mastery not yet confirmed
    return "medium"


def _detect_conflicting_signals(
    risk_flags: List[str],
    mastery_status: str,
    trend: ScoreTrend,
    engagement_status: EngagementStatus,
) -> List[str]:
    """
    Identify signals that contradict each other.

    Conflicts are preserved in the context package rather than silently resolved,
    so Workflow 3 can reason over the tension.
    """
    conflicts: List[str] = []

    # Strong recent performance despite risk flags
    if risk_flags and mastery_status in ("mastered", "approaching") and trend == "improving":
        conflicts.append(
            "risk_flags_present_despite_strong_recent_performance"
        )

    # Low engagement but improving scores
    if engagement_status == "low" and trend == "improving":
        conflicts.append("low_engagement_with_improving_scores")

    # High engagement but declining scores
    if engagement_status == "high" and trend == "declining":
        conflicts.append("high_engagement_with_declining_scores")

    # Mastered status but declining trend
    if mastery_status == "mastered" and trend == "declining":
        conflicts.append("mastered_status_with_declining_trend")

    return conflicts


def analyze_learner_performance(
    db: Session,
    learner_id: int,
    lesson_id: int,
) -> LearnerContextPackage:
    """
    Build a structured learner context package from database records.

    This is the primary service function consumed by the API router and
    by Workflow 3 via build_learner_context().

    Raises
    ------
    ValueError  – if the lesson has no mastery threshold configured.
    LookupError – if no progress record exists for the learner/lesson pair.
    """
    # ------------------------------------------------------------------
    # 1. Load lesson and course context
    # ------------------------------------------------------------------
    lesson: Optional[Lesson] = db.get(Lesson, lesson_id)
    if lesson is None:
        raise LookupError(f"Lesson {lesson_id} not found.")

    if lesson.mastery_threshold is None:
        raise ValueError(
            f"Lesson {lesson_id} has no mastery_threshold configured. "
            "Cannot perform mastery evaluation."
        )

    course: Optional[Course] = db.get(Course, lesson.course_id)
    certification_required = course.certification_required if course else False

    # ------------------------------------------------------------------
    # 2. Load learner progress record (Workflow 1 aggregate)
    # ------------------------------------------------------------------
    progress: Optional[LearnerProgress] = (
        db.query(LearnerProgress)
        .filter(
            LearnerProgress.learner_id == learner_id,
            LearnerProgress.lesson_id == lesson_id,
        )
        .first()
    )

    if progress is None:
        raise LookupError(
            f"No progress record found for learner {learner_id} on lesson {lesson_id}."
        )

    # ------------------------------------------------------------------
    # 3. Load assessment records (bounded)
    # ------------------------------------------------------------------
    raw_records: List[AssessmentRecord] = (
        db.query(AssessmentRecord)
        .filter(
            AssessmentRecord.learner_id == learner_id,
            AssessmentRecord.lesson_id == lesson_id,
        )
        .order_by(AssessmentRecord.attempted_at.asc(), AssessmentRecord.id.asc())
        .limit(MAX_ASSESSMENT_RECORDS)
        .all()
    )

    deduped_records = _deduplicate_records(raw_records)
    valid_scores, corrupted_count = _validate_scores(deduped_records)

    # ------------------------------------------------------------------
    # 4. Load intervention history (bounded)
    # ------------------------------------------------------------------
    interventions: List[InterventionHistory] = (
        db.query(InterventionHistory)
        .filter(
            InterventionHistory.learner_id == learner_id,
            InterventionHistory.lesson_id == lesson_id,
        )
        .order_by(InterventionHistory.applied_at.asc())
        .limit(MAX_ASSESSMENT_RECORDS)
        .all()
    )

    # ------------------------------------------------------------------
    # 5. Compute contextual signals
    # ------------------------------------------------------------------
    trend: ScoreTrend = calculate_trend(valid_scores)

    latest_score: Optional[float] = valid_scores[-1] if valid_scores else None
    average_score: Optional[float] = (
        round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None
    )

    mastery_status, mastery_evidence = evaluate_mastery(
        scores=valid_scores,
        mastery_threshold=lesson.mastery_threshold,
        latest_score=latest_score,
    )

    engagement_raw = progress.engagement_level
    engagement_status = _engagement_status(engagement_raw)

    intervention_effectiveness, last_intervention_type = _intervention_effectiveness(interventions)

    risk_flags = _parse_json_tags(progress.risk_flags)
    strength_tags = _parse_json_tags(progress.strength_tags)
    weakness_tags = _parse_json_tags(progress.weakness_tags)

    cert_risk = _certification_risk(
        certification_required=certification_required,
        valid_scores=valid_scores,
        mastery_status=mastery_status,
        mastery_threshold=lesson.mastery_threshold,
        risk_flags=risk_flags,
    )

    conflicting_signals = _detect_conflicting_signals(
        risk_flags=risk_flags,
        mastery_status=mastery_status,
        trend=trend,
        engagement_status=engagement_status,
    )

    attempt_count = len(deduped_records)
    pressure = _attempt_pressure(attempt_count)

    # ------------------------------------------------------------------
    # 6. Assemble context package
    # ------------------------------------------------------------------
    return LearnerContextPackage(
        learner_id=learner_id,
        lesson_id=lesson_id,
        performance=PerformanceContext(
            latest_score=latest_score,
            average_score=average_score,
            trend=trend,
            attempt_count=attempt_count,
            attempt_pressure=pressure,
            time_spent_seconds=progress.time_spent_seconds or 0,
            completion_percentage=progress.completion_percentage or 0.0,
            learning_velocity=progress.learning_velocity,
            corrupted_score_count=corrupted_count,
        ),
        mastery=MasteryContext(
            status=mastery_status,
            threshold=lesson.mastery_threshold,
            evidence=mastery_evidence,
        ),
        engagement=EngagementContext(
            status=engagement_status,
            raw_level=engagement_raw,
        ),
        intervention=InterventionContext(
            history_count=len(interventions),
            effectiveness=intervention_effectiveness,
            last_intervention_type=last_intervention_type,
        ),
        certification=CertificationContext(
            required=certification_required,
            risk=cert_risk,
        ),
        risk_flags=risk_flags,
        strength_tags=strength_tags,
        weakness_tags=weakness_tags,
        conflicting_signals=conflicting_signals,
    )
