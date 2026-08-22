"""
Progress Service — Workflow 1: Learner State & Dataset Management
=================================================================

Responsibilities
----------------
1. Validate business rules (learner/course/lesson existence, FK integrity).
2. Detect and handle duplicate submissions via idempotency keys.
3. Record assessment attempts and update learner progress atomically.
4. Recompute qualitative signals (trend, risk flags, tags) after each attempt.
5. Expose clean integration-contract functions for Workflow 2.

Design rules
------------
- All database writes happen inside a single transaction; any failure triggers
  a full rollback so the learner is never left in a partially updated state.
- No adaptive decision logic lives here.  We store facts, not outcomes.
- Raw SQLAlchemy / database exceptions are caught and re-raised as domain
  exceptions so the router never exposes internal details to callers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_attempt import AssessmentAttempt
from app.models.course import Course
from app.models.learner import Learner
from app.models.learner_progress import (
    EngagementLevel,
    LearnerProgress,
    MasteryStatus,
    ProgressStatus,
)
from app.models.learner_signal import LearnerSignal, PerformanceTrend
from app.models.lesson import Lesson
from app.schemas.progress import (
    ActivityRequest,
    ActivityResponse,
    AssessmentAttemptDetail,
    AssessmentHistoryContext,
    CourseProgressResponse,
    LearnerProgressContext,
    LearnerSignalContext,
    LearnerSignalDetail,
    LessonProgressContext,
    LessonProgressDetail,
)
from app.workflows.progress.exceptions import (
    CourseNotFoundError,
    DatabaseError,
    DuplicateActivityError,
    LearnerNotFoundError,
    LessonCourseMismatchError,
    LessonNotFoundError,
)

log = logging.getLogger(__name__)

_NOW = lambda: datetime.now(tz=timezone.utc)  # noqa: E731


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_engagement(avg_time_minutes: float) -> EngagementLevel:
    if avg_time_minutes < 20:
        return EngagementLevel.low
    if avg_time_minutes < 35:
        return EngagementLevel.medium
    return EngagementLevel.high


def _derive_mastery(score: float, threshold: float) -> MasteryStatus:
    if score >= threshold:
        return MasteryStatus.mastered
    if score >= threshold * 0.9:
        return MasteryStatus.approaching
    if score > 0:
        return MasteryStatus.below_threshold
    return MasteryStatus.not_attempted


def _derive_status(score: float, threshold: float, attempt_count: int) -> ProgressStatus:
    if score >= threshold:
        return ProgressStatus.completed
    if attempt_count >= 3 and score < 50:
        return ProgressStatus.failed
    return ProgressStatus.in_progress


def _derive_trend(scores: list[float]) -> PerformanceTrend:
    if len(scores) < 2:
        return PerformanceTrend.insufficient_data
    delta = scores[-1] - scores[0]
    if delta >= 8:
        return PerformanceTrend.improving
    if delta <= -8:
        return PerformanceTrend.declining
    return PerformanceTrend.stable


def _compute_risk_flags(
    latest_score: float,
    threshold: float,
    attempt_count: int,
    engagement: EngagementLevel,
    trend: PerformanceTrend,
    avg_time: float,
) -> list[str]:
    flags: list[str] = []
    if latest_score < 50:
        flags.append("low_score")
    if attempt_count >= 3 and latest_score < threshold:
        flags.append("repeated_failure")
    if engagement == EngagementLevel.low:
        flags.append("low_engagement")
    if avg_time > 45:
        flags.append("time_overrun")
    if trend == PerformanceTrend.declining:
        flags.append("declining_performance")
    return flags


def _compute_strength_tags(
    latest_score: float,
    threshold: float,
    avg_time: float,
    trend: PerformanceTrend,
) -> list[str]:
    tags: list[str] = []
    if latest_score >= 90:
        tags.append("high_accuracy")
    if avg_time < 20 and latest_score >= threshold:
        tags.append("fast_completion")
    if trend == PerformanceTrend.improving:
        tags.append("consistent_improvement")
    if latest_score >= threshold:
        tags.append("mastery_achieved")
    return tags


def _compute_weakness_tags(
    latest_score: float,
    threshold: float,
    attempt_count: int,
    scores: list[float],
) -> list[str]:
    tags: list[str] = []
    if latest_score < threshold:
        tags.append("below_mastery_threshold")
    if len(scores) >= 2 and (max(scores) - min(scores)) > 30:
        tags.append("high_score_variance")
    if attempt_count >= 4 and latest_score < threshold:
        tags.append("needs_intervention")
    return tags


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

async def _get_learner_or_404(session: AsyncSession, learner_id: int) -> Learner:
    result = await session.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalars().first()
    if learner is None:
        raise LearnerNotFoundError(learner_id)
    return learner


async def _get_course_or_404(session: AsyncSession, course_id: int) -> Course:
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalars().first()
    if course is None:
        raise CourseNotFoundError(course_id)
    return course


async def _get_lesson_or_404(session: AsyncSession, lesson_id: int) -> Lesson:
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalars().first()
    if lesson is None:
        raise LessonNotFoundError(lesson_id)
    return lesson


async def _check_idempotency(
    session: AsyncSession, idempotency_key: str | None
) -> AssessmentAttempt | None:
    """Return an existing attempt if the key was already used, else None."""
    if not idempotency_key:
        return None
    result = await session.execute(
        select(AssessmentAttempt).where(
            AssessmentAttempt.idempotency_key == idempotency_key
        )
    )
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Core public service functions
# ---------------------------------------------------------------------------

async def record_activity(
    session: AsyncSession,
    request: ActivityRequest,
) -> ActivityResponse:
    """
    Record a learner assessment attempt and update learner progress atomically.

    Transaction steps (per spec §10):
      1. Validate request (done by Pydantic before reaching here).
      2. Validate learner / course / lesson existence.
      3. Check lesson-course FK integrity.
      4. Check idempotency key for duplicate submissions.
      5. Determine next attempt number.
      6. Create AssessmentAttempt row.
      7. Upsert LearnerProgress row.
      8. Upsert LearnerSignal row.
      9. Commit.
     10. On any DB error → rollback + raise DatabaseError.
    """
    try:
        # ── Step 2: Validate entities ─────────────────────────────────────
        learner = await _get_learner_or_404(session, request.learner_id)
        course = await _get_course_or_404(session, request.course_id)
        lesson = await _get_lesson_or_404(session, request.lesson_id)

        # ── Step 3: Lesson ↔ Course integrity ─────────────────────────────
        if lesson.course_id != course.id:
            raise LessonCourseMismatchError(lesson.id, course.id, lesson.course_id)

        # ── Step 4: Idempotency check ─────────────────────────────────────
        existing = await _check_idempotency(session, request.idempotency_key)
        if existing is not None:
            # Fetch the associated progress row to get progress_id
            prog_result = await session.execute(
                select(LearnerProgress).where(
                    LearnerProgress.learner_id == existing.learner_id,
                    LearnerProgress.lesson_id == existing.lesson_id,
                    LearnerProgress.course_id == request.course_id,
                )
            )
            prog = prog_result.scalars().first()
            raise DuplicateActivityError(
                idempotency_key=request.idempotency_key,
                existing_attempt_id=existing.id,
            )

        # ── Step 5: Next attempt number ───────────────────────────────────
        count_result = await session.execute(
            select(func.count(AssessmentAttempt.id)).where(
                AssessmentAttempt.learner_id == request.learner_id,
                AssessmentAttempt.lesson_id == request.lesson_id,
            )
        )
        existing_count = count_result.scalar_one()
        next_attempt_number = existing_count + 1

        now = _NOW()

        # ── Step 6: Create attempt ────────────────────────────────────────
        attempt = AssessmentAttempt(
            learner_id=request.learner_id,
            lesson_id=request.lesson_id,
            score=request.score,
            time_spent_minutes=request.time_spent_minutes,
            attempt_number=next_attempt_number,
            idempotency_key=request.idempotency_key,
            submitted_at=now,
        )
        session.add(attempt)
        await session.flush()   # get attempt.id before continuing

        # ── Step 7: Upsert LearnerProgress ───────────────────────────────
        prog_result = await session.execute(
            select(LearnerProgress).where(
                LearnerProgress.learner_id == request.learner_id,
                LearnerProgress.course_id == request.course_id,
                LearnerProgress.lesson_id == request.lesson_id,
            )
        )
        progress = prog_result.scalars().first()
        is_new_progress = progress is None

        # Fetch all historical scores for velocity / signal computation
        hist_result = await session.execute(
            select(AssessmentAttempt.score)
            .where(
                AssessmentAttempt.learner_id == request.learner_id,
                AssessmentAttempt.lesson_id == request.lesson_id,
            )
            .order_by(AssessmentAttempt.submitted_at)
        )
        all_scores: list[float] = [float(r) for r in hist_result.scalars().all()]
        # Include the current attempt (already flushed)
        if request.score not in all_scores:
            all_scores.append(request.score)

        # Recompute velocity from all historical scores
        if len(all_scores) >= 2:
            velocity = round(
                (all_scores[-1] - all_scores[0]) / max(1, len(all_scores) - 1), 2
            )
        else:
            velocity = 0.0

        mastery_threshold = float(lesson.mastery_threshold)

        total_time: float
        new_attempt_count: int
        if progress is None:
            total_time = request.time_spent_minutes
            new_attempt_count = 1
        else:
            total_time = float(progress.time_spent_minutes) + request.time_spent_minutes
            new_attempt_count = progress.attempt_count + 1

        avg_time = total_time / new_attempt_count
        engagement = _derive_engagement(avg_time)
        mastery = _derive_mastery(request.score, mastery_threshold)
        status = _derive_status(request.score, mastery_threshold, new_attempt_count)
        completion_pct = min(100.0, round(request.score / mastery_threshold * 100, 1))

        response_status: str
        if progress is None:
            progress = LearnerProgress(
                learner_id=request.learner_id,
                course_id=request.course_id,
                lesson_id=request.lesson_id,
                status=status,
                completion_percentage=completion_pct,
                current_score=request.score,
                attempt_count=1,
                time_spent_minutes=total_time,
                engagement_level=engagement,
                learning_velocity=velocity,
                mastery_status=mastery,
                last_activity_at=now,
                updated_at=now,
            )
            session.add(progress)
            response_status = "created"
        else:
            progress.status = status
            progress.completion_percentage = completion_pct
            progress.current_score = request.score
            progress.attempt_count = new_attempt_count
            progress.time_spent_minutes = total_time
            progress.engagement_level = engagement
            progress.learning_velocity = velocity
            progress.mastery_status = mastery
            progress.last_activity_at = now
            progress.updated_at = now
            response_status = "updated"

        await session.flush()

        # ── Step 8: Upsert LearnerSignal ──────────────────────────────────
        sig_result = await session.execute(
            select(LearnerSignal).where(
                LearnerSignal.learner_id == request.learner_id,
                LearnerSignal.lesson_id == request.lesson_id,
            )
        )
        signal = sig_result.scalars().first()

        trend = _derive_trend(all_scores)
        risk_flags = _compute_risk_flags(
            request.score, mastery_threshold, new_attempt_count, engagement, trend, avg_time
        )
        strength_tags = _compute_strength_tags(
            request.score, mastery_threshold, avg_time, trend
        )
        weakness_tags = _compute_weakness_tags(
            request.score, mastery_threshold, new_attempt_count, all_scores
        )

        if signal is None:
            signal = LearnerSignal(
                learner_id=request.learner_id,
                lesson_id=request.lesson_id,
                performance_trend=trend,
                engagement_level=engagement.value,
                risk_flags=risk_flags,
                strength_tags=strength_tags,
                weakness_tags=weakness_tags,
                updated_at=now,
            )
            session.add(signal)
        else:
            signal.performance_trend = trend
            signal.engagement_level = engagement.value
            signal.risk_flags = risk_flags
            signal.strength_tags = strength_tags
            signal.weakness_tags = weakness_tags
            signal.updated_at = now

        # ── Step 9: Commit (or rollback on failure) ───────────────────────
        await session.commit()

        await session.refresh(progress)

        return ActivityResponse(
            progress_id=progress.id,
            learner_id=request.learner_id,
            lesson_id=request.lesson_id,
            score=request.score,
            attempt_number=next_attempt_number,
            status=response_status,
        )

    except (LearnerNotFoundError, CourseNotFoundError, LessonNotFoundError,
            LessonCourseMismatchError, DuplicateActivityError):
        # Domain errors raised before any DB writes — no rollback needed.
        # DuplicateActivityError: detected before the attempt row is created.
        # 404/409 errors: detected before flush. Rollback is safe but unnecessary.
        raise

    except (IntegrityError, SQLAlchemyError) as exc:
        # Step 10: Rollback on any DB failure
        await session.rollback()
        log.exception("Database error during record_activity: %s", exc)
        raise DatabaseError("record_activity") from exc

    except Exception as exc:
        await session.rollback()
        log.exception("Unexpected error during record_activity: %s", exc)
        raise DatabaseError("record_activity.unexpected") from exc


async def get_course_progress(
    session: AsyncSession,
    learner_id: int,
    course_id: int,
) -> CourseProgressResponse:
    """
    Return the full progress snapshot for a learner across all lessons in a course.
    Used by GET /api/v1/progress/{learner_id}/{course_id}.
    """
    try:
        learner = await _get_learner_or_404(session, learner_id)
        course = await _get_course_or_404(session, course_id)

        # All lessons in the course (ordered by sequence)
        lessons_result = await session.execute(
            select(Lesson)
            .where(Lesson.course_id == course_id)
            .order_by(Lesson.sequence_number)
        )
        lessons: list[Lesson] = list(lessons_result.scalars().all())
        lesson_ids = [l.id for l in lessons]

        # Progress rows for this learner in this course
        prog_result = await session.execute(
            select(LearnerProgress).where(
                LearnerProgress.learner_id == learner_id,
                LearnerProgress.course_id == course_id,
            )
        )
        progress_map: dict[int, LearnerProgress] = {
            p.lesson_id: p for p in prog_result.scalars().all()
        }

        # Signals
        sig_result = await session.execute(
            select(LearnerSignal).where(
                LearnerSignal.learner_id == learner_id,
                LearnerSignal.lesson_id.in_(lesson_ids),
            )
        )
        signal_map: dict[int, LearnerSignal] = {
            s.lesson_id: s for s in sig_result.scalars().all()
        }

        # Recent attempts (last 10 across all lessons in this course)
        attempts_result = await session.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.learner_id == learner_id,
                AssessmentAttempt.lesson_id.in_(lesson_ids),
            )
            .order_by(desc(AssessmentAttempt.submitted_at))
            .limit(10)
        )
        recent_attempts = list(attempts_result.scalars().all())

        # Build lesson details
        lesson_details: list[LessonProgressDetail] = []
        completed_count = 0
        failed_count = 0
        total_completion = 0.0

        for lesson in lessons:
            prog = progress_map.get(lesson.id)
            if prog:
                detail = LessonProgressDetail(
                    lesson_id=lesson.id,
                    lesson_title=lesson.title,
                    sequence_number=lesson.sequence_number,
                    difficulty=lesson.difficulty,
                    mastery_threshold=float(lesson.mastery_threshold),
                    status=prog.status.value,
                    completion_percentage=float(prog.completion_percentage),
                    current_score=float(prog.current_score) if prog.current_score is not None else None,
                    attempt_count=prog.attempt_count,
                    time_spent_minutes=float(prog.time_spent_minutes),
                    engagement_level=prog.engagement_level.value,
                    learning_velocity=float(prog.learning_velocity),
                    mastery_status=prog.mastery_status.value,
                    last_activity_at=prog.last_activity_at,
                    updated_at=prog.updated_at,
                )
                if prog.status == ProgressStatus.completed:
                    completed_count += 1
                elif prog.status == ProgressStatus.failed:
                    failed_count += 1
                total_completion += float(prog.completion_percentage)
            else:
                detail = LessonProgressDetail(
                    lesson_id=lesson.id,
                    lesson_title=lesson.title,
                    sequence_number=lesson.sequence_number,
                    difficulty=lesson.difficulty,
                    mastery_threshold=float(lesson.mastery_threshold),
                    status=ProgressStatus.not_started.value,
                    completion_percentage=0.0,
                    current_score=None,
                    attempt_count=0,
                    time_spent_minutes=0.0,
                    engagement_level=EngagementLevel.medium.value,
                    learning_velocity=0.0,
                    mastery_status=MasteryStatus.not_attempted.value,
                    last_activity_at=None,
                    updated_at=_NOW(),
                )
            lesson_details.append(detail)

        overall_pct = round(total_completion / len(lessons), 1) if lessons else 0.0

        signal_details = [
            LearnerSignalDetail(
                lesson_id=s.lesson_id,
                performance_trend=s.performance_trend.value,
                engagement_level=s.engagement_level,
                risk_flags=s.risk_flags,
                strength_tags=s.strength_tags,
                weakness_tags=s.weakness_tags,
                updated_at=s.updated_at,
            )
            for s in signal_map.values()
        ]

        attempt_details = [
            AssessmentAttemptDetail(
                id=a.id,
                lesson_id=a.lesson_id,
                score=float(a.score),
                time_spent_minutes=float(a.time_spent_minutes),
                attempt_number=a.attempt_number,
                submitted_at=a.submitted_at,
            )
            for a in recent_attempts
        ]

        return CourseProgressResponse(
            learner_id=learner_id,
            learner_name=learner.name,
            course_id=course_id,
            course_title=course.title,
            overall_completion_percentage=overall_pct,
            total_lessons=len(lessons),
            completed_lessons=completed_count,
            failed_lessons=failed_count,
            lessons=lesson_details,
            recent_attempts=attempt_details,
            signals=signal_details,
        )

    except (LearnerNotFoundError, CourseNotFoundError):
        raise

    except (IntegrityError, SQLAlchemyError) as exc:
        log.exception("Database error during get_course_progress: %s", exc)
        raise DatabaseError("get_course_progress") from exc


# ---------------------------------------------------------------------------
# Integration contract — consumed by Workflow 2
# ---------------------------------------------------------------------------

async def get_learner_progress(
    session: AsyncSession,
    learner_id: int,
    course_id: int,
) -> LearnerProgressContext:
    """
    Return the full learner-course context Workflow 2 needs for
    performance analysis.  Raises LearnerNotFoundError / CourseNotFoundError
    on invalid IDs.
    """
    snapshot = await get_course_progress(session, learner_id, course_id)
    return LearnerProgressContext(
        learner_id=learner_id,
        course_id=course_id,
        lessons=snapshot.lessons,
        signals=snapshot.signals,
    )


async def get_lesson_progress(
    session: AsyncSession,
    learner_id: int,
    lesson_id: int,
) -> LessonProgressContext:
    """
    Return progress state for a single lesson.
    Returns a 'not_started' context when no progress row exists yet.
    """
    try:
        await _get_learner_or_404(session, learner_id)
        lesson = await _get_lesson_or_404(session, lesson_id)

        result = await session.execute(
            select(LearnerProgress).where(
                LearnerProgress.learner_id == learner_id,
                LearnerProgress.lesson_id == lesson_id,
            )
        )
        prog = result.scalars().first()

        if prog is None:
            return LessonProgressContext(
                learner_id=learner_id,
                lesson_id=lesson_id,
                status=ProgressStatus.not_started.value,
                completion_percentage=0.0,
                current_score=None,
                attempt_count=0,
                time_spent_minutes=0.0,
                engagement_level=EngagementLevel.medium.value,
                learning_velocity=0.0,
                mastery_status=MasteryStatus.not_attempted.value,
                last_activity_at=None,
            )

        return LessonProgressContext(
            learner_id=learner_id,
            lesson_id=lesson_id,
            status=prog.status.value,
            completion_percentage=float(prog.completion_percentage),
            current_score=float(prog.current_score) if prog.current_score is not None else None,
            attempt_count=prog.attempt_count,
            time_spent_minutes=float(prog.time_spent_minutes),
            engagement_level=prog.engagement_level.value,
            learning_velocity=float(prog.learning_velocity),
            mastery_status=prog.mastery_status.value,
            last_activity_at=prog.last_activity_at,
        )

    except (LearnerNotFoundError, LessonNotFoundError):
        raise

    except (IntegrityError, SQLAlchemyError) as exc:
        log.exception("Database error during get_lesson_progress: %s", exc)
        raise DatabaseError("get_lesson_progress") from exc


async def get_assessment_history(
    session: AsyncSession,
    learner_id: int,
    lesson_id: int,
) -> AssessmentHistoryContext:
    """
    Return all scored attempts for a learner on a specific lesson,
    oldest first.
    """
    try:
        await _get_learner_or_404(session, learner_id)
        await _get_lesson_or_404(session, lesson_id)

        result = await session.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.learner_id == learner_id,
                AssessmentAttempt.lesson_id == lesson_id,
            )
            .order_by(AssessmentAttempt.submitted_at)
        )
        attempts = list(result.scalars().all())

        return AssessmentHistoryContext(
            learner_id=learner_id,
            lesson_id=lesson_id,
            attempts=[
                AssessmentAttemptDetail(
                    id=a.id,
                    lesson_id=a.lesson_id,
                    score=float(a.score),
                    time_spent_minutes=float(a.time_spent_minutes),
                    attempt_number=a.attempt_number,
                    submitted_at=a.submitted_at,
                )
                for a in attempts
            ],
        )

    except (LearnerNotFoundError, LessonNotFoundError):
        raise

    except (IntegrityError, SQLAlchemyError) as exc:
        log.exception("Database error during get_assessment_history: %s", exc)
        raise DatabaseError("get_assessment_history") from exc


async def get_learner_signals(
    session: AsyncSession,
    learner_id: int,
    lesson_id: int,
) -> LearnerSignalContext:
    """
    Return aggregated qualitative signals for a learner on a specific lesson.
    Returns signal=None when no signal row exists yet.
    """
    try:
        await _get_learner_or_404(session, learner_id)
        await _get_lesson_or_404(session, lesson_id)

        result = await session.execute(
            select(LearnerSignal).where(
                LearnerSignal.learner_id == learner_id,
                LearnerSignal.lesson_id == lesson_id,
            )
        )
        signal = result.scalars().first()

        signal_detail: LearnerSignalDetail | None = None
        if signal is not None:
            signal_detail = LearnerSignalDetail(
                lesson_id=signal.lesson_id,
                performance_trend=signal.performance_trend.value,
                engagement_level=signal.engagement_level,
                risk_flags=signal.risk_flags,
                strength_tags=signal.strength_tags,
                weakness_tags=signal.weakness_tags,
                updated_at=signal.updated_at,
            )

        return LearnerSignalContext(
            learner_id=learner_id,
            lesson_id=lesson_id,
            signal=signal_detail,
        )

    except (LearnerNotFoundError, LessonNotFoundError):
        raise

    except (IntegrityError, SQLAlchemyError) as exc:
        log.exception("Database error during get_learner_signals: %s", exc)
        raise DatabaseError("get_learner_signals") from exc
