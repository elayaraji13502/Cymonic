"""
Seed script — Workflow 1: Learner State & Dataset Management
============================================================
Populates the database with a realistic demo dataset:

  Learners  (5)  — one per behavioural profile
  Courses   (2)  — one foundational, one advanced/certified
  Lessons   (10) — 5 per course, varying difficulty
  Assessment attempts — multiple per learner/lesson pair
  Learner progress   — derived from attempt history
  Learner signals    — qualitative flags inferred from performance

Run via:
  python -m app.seed

The script is idempotent: re-running it on a database that already has
seed data will skip insertion and exit cleanly.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import get_session_factory
from app.models import (  # noqa: F401  — ensure all models are registered
    AssessmentAttempt,
    Course,
    Learner,
    LearnerProgress,
    LearnerSignal,
    Lesson,
)
from app.models.learner import LearnerStatus
from app.models.learner_progress import EngagementLevel, MasteryStatus, ProgressStatus
from app.models.learner_signal import PerformanceTrend

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

NOW = datetime.now(tz=timezone.utc)


def _ago(**kwargs) -> datetime:
    return NOW - timedelta(**kwargs)


# ---------------------------------------------------------------------------
# Raw seed definitions
# ---------------------------------------------------------------------------

COURSES = [
    {
        "id": 1,
        "title": "Python Fundamentals",
        "description": (
            "Covers core Python concepts: variables, control flow, functions, "
            "modules, and basic data structures. Suitable for beginners."
        ),
        "certification_required": False,
    },
    {
        "id": 2,
        "title": "Machine Learning Engineering",
        "description": (
            "Applied ML engineering: feature engineering, model training, "
            "evaluation pipelines, and deployment patterns. Certification required."
        ),
        "certification_required": True,
    },
]

# sequence_number, title, difficulty (1-5), mastery_threshold, is_required
LESSONS_COURSE_1 = [
    (1, "Variables & Data Types",          1, 70.0, True),
    (2, "Control Flow & Loops",            2, 70.0, True),
    (3, "Functions & Scope",               2, 72.0, True),
    (4, "Lists, Dicts & Comprehensions",   3, 75.0, True),
    (5, "Modules, Packages & I/O",         3, 75.0, False),
]

LESSONS_COURSE_2 = [
    (1, "Feature Engineering Basics",      3, 75.0, True),
    (2, "Supervised Learning Pipelines",   4, 78.0, True),
    (3, "Model Evaluation & Metrics",      4, 78.0, True),
    (4, "Hyperparameter Tuning",           5, 80.0, True),
    (5, "Model Deployment Patterns",       5, 80.0, False),
]

# Learner profiles — no adaptive outcomes, just realistic historical state
LEARNERS = [
    # id, name, email, status, profile_tag
    (1, "Alice Chen",    "alice.chen@example.com",    LearnerStatus.active,    "high_performer"),
    (2, "Ben Okafor",    "ben.okafor@example.com",    LearnerStatus.active,    "struggling_improving"),
    (3, "Carmen Lopez",  "carmen.lopez@example.com",  LearnerStatus.active,    "persistent_failure"),
    (4, "David Kim",     "david.kim@example.com",     LearnerStatus.active,    "inconsistent"),
    (5, "Eva Müller",    "eva.muller@example.com",    LearnerStatus.inactive,  "low_engagement"),
]


# ---------------------------------------------------------------------------
# Attempt histories per learner
# Each entry: (learner_id, lesson_id, [(score, minutes, days_ago), ...])
# lesson_id uses 1-based global IDs:
#   course 1 lessons → ids 1-5, course 2 lessons → ids 6-10
# ---------------------------------------------------------------------------

ATTEMPT_HISTORIES: list[tuple[int, int, list[tuple[float, float, int]]]] = [
    # ── ALICE (high performer) ──────────────────────────────────────────
    # Course 1 — all lessons, consistently high scores
    (1, 1, [(92.0, 18, 60), (96.0, 12, 55)]),
    (1, 2, [(88.0, 22, 50), (94.0, 18, 45)]),
    (1, 3, [(91.0, 25, 40), (97.0, 20, 35)]),
    (1, 4, [(85.0, 30, 30), (93.0, 22, 25)]),
    (1, 5, [(90.0, 20, 20), (95.0, 15, 15)]),
    # Course 2 — strong start
    (1, 6, [(84.0, 35, 10), (89.0, 28, 7)]),
    (1, 7, [(80.0, 40, 5)]),

    # ── BEN (struggling but improving) ─────────────────────────────────
    # Course 1 — slow start, clear upward trend over multiple retries
    (2, 1, [(48.0, 30, 80), (57.0, 28, 70), (68.0, 25, 60), (74.0, 20, 50)]),
    (2, 2, [(40.0, 35, 45), (52.0, 32, 38), (65.0, 28, 30), (71.0, 22, 22)]),
    (2, 3, [(55.0, 40, 15), (63.0, 35, 10), (72.0, 30, 5)]),
    (2, 4, [(50.0, 45, 3)]),

    # ── CARMEN (persistent failure) ─────────────────────────────────────
    # Course 1 — repeated attempts, scores stay low, some slight movement
    (3, 1, [(38.0, 40, 90), (42.0, 38, 80), (40.0, 42, 70), (45.0, 40, 60)]),
    (3, 2, [(30.0, 50, 50), (35.0, 48, 40), (33.0, 50, 30)]),
    (3, 3, [(28.0, 55, 20), (31.0, 52, 10)]),

    # ── DAVID (inconsistent performer) ─────────────────────────────────
    # Course 1 — high variance: sometimes good, sometimes fails
    (4, 1, [(82.0, 20, 70), (55.0, 25, 60), (88.0, 18, 50), (60.0, 22, 40)]),
    (4, 2, [(75.0, 28, 35), (48.0, 30, 28), (79.0, 25, 20)]),
    (4, 3, [(91.0, 20, 15), (52.0, 35, 8), (85.0, 22, 3)]),
    # Course 2 — dipped in again inconsistently
    (4, 6, [(70.0, 38, 2)]),

    # ── EVA (low engagement) ────────────────────────────────────────────
    # Course 1 — barely started, one attempt with moderate score, then gone
    (5, 1, [(62.0, 55, 120)]),
    (5, 2, [(58.0, 60, 100)]),
    # Never continued further
]


# ---------------------------------------------------------------------------
# Derived progress & signal computation helpers
# ---------------------------------------------------------------------------

def _compute_progress(
    learner_id: int,
    course_id: int,
    lesson_id: int,
    lesson_mastery_threshold: float,
    attempts: list[tuple[float, float, int]],
) -> dict:
    """Derive a LearnerProgress record from raw attempt data."""
    scores = [a[0] for a in attempts]
    times = [a[1] for a in attempts]
    latest_score = scores[-1]
    total_time = sum(times)
    attempt_count = len(attempts)
    last_activity = _ago(days=attempts[-1][2])

    # mastery
    if latest_score >= lesson_mastery_threshold:
        mastery = MasteryStatus.mastered
    elif latest_score >= lesson_mastery_threshold * 0.9:
        mastery = MasteryStatus.approaching
    else:
        mastery = MasteryStatus.below_threshold

    # status
    if latest_score >= lesson_mastery_threshold:
        status = ProgressStatus.completed
    elif attempt_count >= 3 and latest_score < 50:
        status = ProgressStatus.failed
    else:
        status = ProgressStatus.in_progress

    # completion_percentage: proxy via score relative to threshold
    completion_pct = min(100.0, round(latest_score / lesson_mastery_threshold * 100, 1))

    # learning_velocity: slope between first and last score (normalised)
    if len(scores) >= 2:
        velocity = round((scores[-1] - scores[0]) / max(1, len(scores) - 1), 2)
    else:
        velocity = 0.0

    # engagement: driven by time_spent vs attempt_count
    avg_time = total_time / attempt_count
    if avg_time < 20:
        engagement = EngagementLevel.low
    elif avg_time < 35:
        engagement = EngagementLevel.medium
    else:
        engagement = EngagementLevel.high

    return {
        "learner_id": learner_id,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "status": status,
        "completion_percentage": completion_pct,
        "current_score": latest_score,
        "attempt_count": attempt_count,
        "time_spent_minutes": total_time,
        "engagement_level": engagement,
        "learning_velocity": velocity,
        "mastery_status": mastery,
        "last_activity_at": last_activity,
        "updated_at": last_activity,
    }


def _compute_signal(
    learner_id: int,
    lesson_id: int,
    lesson_mastery_threshold: float,
    attempts: list[tuple[float, float, int]],
    engagement: EngagementLevel,
) -> dict:
    """Derive a LearnerSignal record from raw attempt data."""
    scores = [a[0] for a in attempts]
    times = [a[1] for a in attempts]
    latest_score = scores[-1]
    attempt_count = len(scores)
    avg_time = sum(times) / attempt_count

    # Performance trend
    if len(scores) < 2:
        trend = PerformanceTrend.insufficient_data
    else:
        delta = scores[-1] - scores[0]
        if delta >= 8:
            trend = PerformanceTrend.improving
        elif delta <= -8:
            trend = PerformanceTrend.declining
        else:
            trend = PerformanceTrend.stable

    # Risk flags
    risk_flags: list[str] = []
    if latest_score < 50:
        risk_flags.append("low_score")
    if attempt_count >= 3 and latest_score < lesson_mastery_threshold:
        risk_flags.append("repeated_failure")
    if engagement == EngagementLevel.low:
        risk_flags.append("low_engagement")
    if avg_time > 45:
        risk_flags.append("time_overrun")
    if trend == PerformanceTrend.declining:
        risk_flags.append("declining_performance")

    # Strength tags
    strength_tags: list[str] = []
    if latest_score >= 90:
        strength_tags.append("high_accuracy")
    if avg_time < 20 and latest_score >= lesson_mastery_threshold:
        strength_tags.append("fast_completion")
    if trend == PerformanceTrend.improving:
        strength_tags.append("consistent_improvement")
    if latest_score >= lesson_mastery_threshold:
        strength_tags.append("mastery_achieved")

    # Weakness tags
    weakness_tags: list[str] = []
    if latest_score < lesson_mastery_threshold:
        weakness_tags.append("below_mastery_threshold")
    if len(set(round(s) for s in scores)) == len(scores) and max(scores) - min(scores) > 30:
        weakness_tags.append("high_score_variance")
    if attempt_count >= 4 and latest_score < lesson_mastery_threshold:
        weakness_tags.append("needs_intervention")

    return {
        "learner_id": learner_id,
        "lesson_id": lesson_id,
        "performance_trend": trend,
        "engagement_level": engagement.value,
        "risk_flags": risk_flags,
        "strength_tags": strength_tags,
        "weakness_tags": weakness_tags,
        "updated_at": NOW,
    }


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------

async def seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        # ── idempotency guard ─────────────────────────────────────────────
        result = await session.execute(select(Learner).limit(1))
        if result.scalars().first() is not None:
            log.info("Seed data already present — skipping.")
            return

        log.info("Seeding courses …")
        course_map: dict[int, Course] = {}
        for c in COURSES:
            course = Course(
                id=c["id"],
                title=c["title"],
                description=c["description"],
                certification_required=c["certification_required"],
                created_at=_ago(days=180),
            )
            session.add(course)
            course_map[c["id"]] = course

        log.info("Seeding lessons …")
        lesson_map: dict[int, tuple[int, float]] = {}  # lesson_id → (course_id, mastery_threshold)
        lesson_id_counter = 1
        for course_id, raw_lessons in [(1, LESSONS_COURSE_1), (2, LESSONS_COURSE_2)]:
            for seq, title, diff, thresh, required in raw_lessons:
                lesson = Lesson(
                    id=lesson_id_counter,
                    course_id=course_id,
                    title=title,
                    sequence_number=seq,
                    difficulty=diff,
                    mastery_threshold=thresh,
                    is_required=required,
                )
                session.add(lesson)
                lesson_map[lesson_id_counter] = (course_id, thresh)
                lesson_id_counter += 1

        log.info("Seeding learners …")
        for l_id, name, email, status, _ in LEARNERS:
            learner = Learner(
                id=l_id,
                name=name,
                email=email,
                status=status,
                created_at=_ago(days=150),
            )
            session.add(learner)

        # Flush so FKs resolve
        await session.flush()

        log.info("Seeding assessment attempts, progress and signals …")
        attempt_id = 1
        for learner_id, lesson_id, raw_attempts in ATTEMPT_HISTORIES:
            course_id, mastery_threshold = lesson_map[lesson_id]

            # Insert attempts in chronological order (oldest first)
            sorted_attempts = sorted(raw_attempts, key=lambda a: a[2], reverse=True)
            for attempt_number, (score, minutes, days_ago) in enumerate(sorted_attempts, start=1):
                attempt = AssessmentAttempt(
                    id=attempt_id,
                    learner_id=learner_id,
                    lesson_id=lesson_id,
                    score=score,
                    time_spent_minutes=minutes,
                    attempt_number=attempt_number,
                    idempotency_key=None,       # seed data has no idempotency keys
                    submitted_at=_ago(days=days_ago),
                )
                session.add(attempt)
                attempt_id += 1

            # Derive and insert progress
            progress_data = _compute_progress(
                learner_id, course_id, lesson_id, mastery_threshold, raw_attempts
            )
            progress = LearnerProgress(**progress_data)
            session.add(progress)

            # Derive and insert signal
            signal_data = _compute_signal(
                learner_id, lesson_id, mastery_threshold,
                raw_attempts, progress_data["engagement_level"]
            )
            signal = LearnerSignal(**signal_data)
            session.add(signal)

        await session.commit()
        log.info("Seed complete — %d learners, %d courses, %d lessons seeded.",
                 len(LEARNERS), len(COURSES), lesson_id_counter - 1)


if __name__ == "__main__":
    asyncio.run(seed())
