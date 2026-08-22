"""
AssessmentAttempt model.

One row per distinct graded attempt at a lesson.
Supports idempotency via the optional idempotency_key column.
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_attempt_score_range"),
        CheckConstraint("time_spent_minutes >= 0", name="ck_attempt_time_spent"),
        CheckConstraint("attempt_number >= 1", name="ck_attempt_number_positive"),
        # Idempotency: one row per unique external key (when provided)
        UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    time_spent_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Caller-supplied idempotency key (UUID or similar); nullable = not provided
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="assessment_attempts")
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="assessment_attempts")

    def __repr__(self) -> str:
        return (
            f"<AssessmentAttempt id={self.id} "
            f"learner={self.learner_id} lesson={self.lesson_id} "
            f"attempt={self.attempt_number} score={self.score}>"
        )
