"""
Context builder — public service interface for Workflow 2.

Workflow 3 calls build_learner_context() to obtain the structured evidence
package. This function is the single integration point; Workflow 3 does not
need to know about the database schema or internal calculation details.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.performance import LearnerContextPackage
from app.workflows.performance.analyzer import analyze_learner_performance


def build_learner_context(
    db: Session,
    learner_id: int,
    lesson_id: int,
) -> LearnerContextPackage:
    """
    Build and return a structured learner context package.

    This is the primary integration point for Workflow 3.

    Parameters
    ----------
    db:
        Active SQLAlchemy database session.
    learner_id:
        Identifier of the learner to analyse.
    lesson_id:
        Identifier of the lesson to analyse.

    Returns
    -------
    LearnerContextPackage
        A fully populated, deterministic context object.

    Raises
    ------
    LookupError
        If no progress record exists for the learner/lesson pair,
        or if the lesson itself does not exist.
    ValueError
        If the lesson has no mastery threshold configured.
    """
    return analyze_learner_performance(db=db, learner_id=learner_id, lesson_id=lesson_id)
