"""
SQLAlchemy model registry.

Import all models here so that Base.metadata is fully populated
before Alembic or create_all() runs.
"""
from app.models.learner import Learner
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.learner_progress import LearnerProgress
from app.models.assessment_attempt import AssessmentAttempt
from app.models.learner_signal import LearnerSignal

__all__ = [
    "Learner",
    "Course",
    "Lesson",
    "LearnerProgress",
    "AssessmentAttempt",
    "LearnerSignal",
]
