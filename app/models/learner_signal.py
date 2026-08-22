"""
LearnerSignal model.

Aggregated qualitative signals per (learner, lesson).
Populated and updated by the service layer after each activity submission.
Workflow 2 reads this table for performance trend analysis.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PerformanceTrend(str, enum.Enum):
    improving = "improving"
    stable = "stable"
    declining = "declining"
    insufficient_data = "insufficient_data"


class LearnerSignal(Base):
    __tablename__ = "learner_signals"
    __table_args__ = (
        UniqueConstraint("learner_id", "lesson_id", name="uq_signal_learner_lesson"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )

    performance_trend: Mapped[PerformanceTrend] = mapped_column(
        Enum(PerformanceTrend, name="performance_trend"),
        nullable=False,
        default=PerformanceTrend.insufficient_data,
        server_default="insufficient_data",
    )

    # Stored as PostgreSQL TEXT[] arrays
    # risk_flags: e.g. ["low_engagement", "repeated_failure", "time_overrun"]
    risk_flags: Mapped[list[str]] = mapped_column(
        PG_ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    # strength_tags: e.g. ["fast_completion", "high_accuracy", "consistent"]
    strength_tags: Mapped[list[str]] = mapped_column(
        PG_ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    # weakness_tags: e.g. ["slow_progress", "low_retention", "needs_review"]
    weakness_tags: Mapped[list[str]] = mapped_column(
        PG_ARRAY(String), nullable=False, default=list, server_default="{}"
    )

    # Denormalised engagement level mirrored from learner_progress for quick reads
    engagement_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="signals")
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="signals")

    def __repr__(self) -> str:
        return (
            f"<LearnerSignal id={self.id} "
            f"learner={self.learner_id} lesson={self.lesson_id} "
            f"trend={self.performance_trend}>"
        )
