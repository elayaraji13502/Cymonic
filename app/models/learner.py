"""
Learner model.

Represents a registered user of the learning platform.
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LearnerStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[LearnerStatus] = mapped_column(
        Enum(LearnerStatus, name="learner_status"),
        nullable=False,
        default=LearnerStatus.active,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships (back-populated from child tables)
    progress_records: Mapped[list["LearnerProgress"]] = relationship(
        "LearnerProgress", back_populates="learner", cascade="all, delete-orphan"
    )
    assessment_attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt", back_populates="learner", cascade="all, delete-orphan"
    )
    signals: Mapped[list["LearnerSignal"]] = relationship(
        "LearnerSignal", back_populates="learner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Learner id={self.id} email={self.email!r} status={self.status}>"
