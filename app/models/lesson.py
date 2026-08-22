"""
Lesson model.

A single unit within a course, ordered by sequence_number.
difficulty ranges 1–5 (1 = easiest).
mastery_threshold is the minimum score (0–100) to consider a lesson mastered.
"""
import enum

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DifficultyLevel(int, enum.Enum):
    beginner = 1
    elementary = 2
    intermediate = 3
    advanced = 4
    expert = 5


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("sequence_number >= 1", name="ck_lesson_sequence_positive"),
        CheckConstraint("mastery_threshold >= 0 AND mastery_threshold <= 100", name="ck_lesson_mastery_threshold"),
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="ck_lesson_difficulty_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mastery_threshold: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=70.0
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relationships
    course: Mapped["Course"] = relationship("Course", back_populates="lessons")
    progress_records: Mapped[list["LearnerProgress"]] = relationship(
        "LearnerProgress", back_populates="lesson", cascade="all, delete-orphan"
    )
    assessment_attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt", back_populates="lesson", cascade="all, delete-orphan"
    )
    signals: Mapped[list["LearnerSignal"]] = relationship(
        "LearnerSignal", back_populates="lesson", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lesson id={self.id} course_id={self.course_id} seq={self.sequence_number} title={self.title!r}>"
