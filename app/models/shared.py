"""
Shared database models.

Workflow 1 owns and writes to these tables.
Workflow 2 reads from them to build the learner context package.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Learner(Base):
    """Core learner identity record."""

    __tablename__ = "learners"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    progress_records = relationship("LearnerProgress", back_populates="learner")
    assessments = relationship("AssessmentRecord", back_populates="learner")


class Course(Base):
    """Course catalogue entry."""

    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(255), nullable=False)
    certification_required = Column(Boolean, default=False)

    lessons = relationship("Lesson", back_populates="course")


class Lesson(Base):
    """Individual lesson within a course."""

    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    # 1 = easiest, 5 = hardest
    difficulty = Column(Integer, nullable=False, default=3)
    # Score (0–100) a learner must reach to be considered as having mastered this lesson
    mastery_threshold = Column(Float, nullable=True)
    # Position in the course sequence
    sequence_order = Column(Integer, nullable=False, default=1)
    # Whether this lesson must be completed before the next one
    is_required = Column(Boolean, default=True)

    course = relationship("Course", back_populates="lessons")
    progress_records = relationship("LearnerProgress", back_populates="lesson")
    assessments = relationship("AssessmentRecord", back_populates="lesson")


class LearnerProgress(Base):
    """
    Aggregated progress record for a learner on a specific lesson.

    Workflow 1 maintains this record.
    """

    __tablename__ = "learner_progress"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)

    # Latest assessment score (0–100)
    latest_score = Column(Float, nullable=True)
    # Mean of all valid assessment scores
    average_score = Column(Float, nullable=True)
    # Total number of assessment attempts
    attempt_count = Column(Integer, default=0)
    # Cumulative time spent in seconds
    time_spent_seconds = Column(Integer, default=0)
    # Lesson completion percentage (0–100)
    completion_percentage = Column(Float, default=0.0)
    # Qualitative engagement level set by Workflow 1
    engagement_level = Column(String(50), nullable=True)
    # Rate of improvement over recent attempts
    learning_velocity = Column(Float, nullable=True)
    # Workflow 1 mastery determination
    mastery_status = Column(String(50), nullable=True)
    # Description of the most recent activity
    previous_activity = Column(Text, nullable=True)
    # JSON-serialised list of risk flag strings
    risk_flags = Column(Text, nullable=True)
    # JSON-serialised list of strength tag strings
    strength_tags = Column(Text, nullable=True)
    # JSON-serialised list of weakness tag strings
    weakness_tags = Column(Text, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    learner = relationship("Learner", back_populates="progress_records")
    lesson = relationship("Lesson", back_populates="progress_records")


class AssessmentRecord(Base):
    """
    Individual assessment attempt.

    Workflow 1 inserts rows here after each attempt.
    Workflow 2 reads these rows to compute trend and mastery signals.
    """

    __tablename__ = "assessment_records"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    # Score must be 0–100; values outside this range are treated as corrupted
    score = Column(Float, nullable=False)
    # Seconds taken to complete this attempt
    time_spent_seconds = Column(Integer, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    learner = relationship("Learner", back_populates="assessments")
    lesson = relationship("Lesson", back_populates="assessments")


class InterventionHistory(Base):
    """
    Record of adaptive interventions applied to a learner for a lesson.

    Workflow 3 writes here after making a decision.
    Workflow 2 reads here to compute intervention_effectiveness.
    """

    __tablename__ = "intervention_history"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    # e.g. "reinforce", "advance", "mentor"
    intervention_type = Column(String(50), nullable=False)
    # Score at the time the intervention was applied
    score_at_intervention = Column(Float, nullable=True)
    # Score on the next attempt after the intervention (null until recorded)
    score_after_intervention = Column(Float, nullable=True)
    # Whether the intervention is considered to have worked
    was_effective = Column(Boolean, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
