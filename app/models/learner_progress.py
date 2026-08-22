"""
LearnerProgress model.

One row per (learner, course, lesson) triple.
This is the primary state record Workflow 2 will query.

Fields intentionally rich enough to support adaptive reasoning without
duplicating decision logic (that belongs to later workflows).
"""
import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProgressStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class MasteryStatus(str, enum.Enum):
    not_attempted = "not_attempted"
    below_threshold = "below_threshold"
    approaching = "approaching"
    mastered = "mastered"


class EngagementLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class LearnerProgress(Base):
    __tablename__ = "learner_progress"
    __table_args__ = (
        UniqueConstraint("learner_id", "course_id", "lesson_id", name="uq_progress_learner_course_lesson"),
        CheckConstraint("completion_percentage >= 0 AND completion_percentage <= 100", name="ck_progress_completion_pct"),
        CheckConstraint("current_score >= 0 AND current_score <= 100", name="ck_progress_score_range"),
        CheckConstraint("attempt_count >= 0", name="ck_progress_attempt_count"),
        CheckConstraint("time_spent_minutes >= 0", name="ck_progress_time_spent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Core progress
    status: Mapped[ProgressStatus] = mapped_column(
        Enum(ProgressStatus, name="progress_status"),
        nullable=False,
        default=ProgressStatus.not_started,
        server_default="not_started",
    )
    completion_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0.0, server_default="0"
    )
    current_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    time_spent_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")

    # Qualitative signals — updated by service logic after each attempt
    engagement_level: Mapped[EngagementLevel] = mapped_column(
        Enum(EngagementLevel, name="engagement_level"),
        nullable=False,
        default=EngagementLevel.medium,
        server_default="medium",
    )
    # learning_velocity: positive = improving, negative = declining, 0 = stable
    learning_velocity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")

    mastery_status: Mapped[MasteryStatus] = mapped_column(
        Enum(MasteryStatus, name="mastery_status"),
        nullable=False,
        default=MasteryStatus.not_attempted,
        server_default="not_attempted",
    )

    # Timestamps
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="progress_records")
    course: Mapped["Course"] = relationship("Course", back_populates="progress_records")
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="progress_records")

    def __repr__(self) -> str:
        return (
            f"<LearnerProgress id={self.id} "
            f"learner={self.learner_id} lesson={self.lesson_id} "
            f"score={self.current_score} status={self.status}>"
        )
