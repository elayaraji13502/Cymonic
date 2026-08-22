"""Initial schema — all Workflow 1 tables

Revision ID: 0001
Revises:
Create Date: 2026-08-22 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENUM_DEFS = [
    ("learner_status",    "'active','inactive','suspended'"),
    ("progress_status",   "'not_started','in_progress','completed','failed'"),
    ("mastery_status",    "'not_attempted','below_threshold','approaching','mastered'"),
    ("engagement_level",  "'low','medium','high'"),
    ("performance_trend", "'improving','stable','declining','insufficient_data'"),
]


def _create_enums(conn) -> None:
    for name, values in _ENUM_DEFS:
        conn.execute(sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({values});"
            f" EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        ))


def _drop_enums(conn) -> None:
    for name, _ in reversed(_ENUM_DEFS):
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    conn = op.get_bind()
    _create_enums(conn)

    # ── learners ─────────────────────────────────────────────────────────
    op.create_table(
        "learners",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", "suspended",
                            name="learner_status", create_type=False),
            server_default="active", nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_learners_email", "learners", ["email"], unique=True)

    # ── courses ──────────────────────────────────────────────────────────
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("certification_required", sa.Boolean(),
                  server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── lessons ──────────────────────────────────────────────────────────
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("mastery_threshold", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint("sequence_number >= 1",
                           name="ck_lesson_sequence_positive"),
        sa.CheckConstraint("mastery_threshold >= 0 AND mastery_threshold <= 100",
                           name="ck_lesson_mastery_threshold"),
        sa.CheckConstraint("difficulty >= 1 AND difficulty <= 5",
                           name="ck_lesson_difficulty_range"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lessons_course_id", "lessons", ["course_id"])

    # ── learner_progress ─────────────────────────────────────────────────
    op.create_table(
        "learner_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("not_started", "in_progress", "completed", "failed",
                            name="progress_status", create_type=False),
            server_default="not_started", nullable=False,
        ),
        sa.Column("completion_percentage", sa.Numeric(5, 2),
                  server_default="0", nullable=False),
        sa.Column("current_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("time_spent_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "engagement_level",
            postgresql.ENUM("low", "medium", "high",
                            name="engagement_level", create_type=False),
            server_default="medium", nullable=False,
        ),
        sa.Column("learning_velocity", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "mastery_status",
            postgresql.ENUM("not_attempted", "below_threshold", "approaching", "mastered",
                            name="mastery_status", create_type=False),
            server_default="not_attempted", nullable=False,
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("completion_percentage >= 0 AND completion_percentage <= 100",
                           name="ck_progress_completion_pct"),
        sa.CheckConstraint("current_score >= 0 AND current_score <= 100",
                           name="ck_progress_score_range"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_progress_attempt_count"),
        sa.CheckConstraint("time_spent_minutes >= 0", name="ck_progress_time_spent"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "course_id", "lesson_id",
                            name="uq_progress_learner_course_lesson"),
    )
    op.create_index("ix_learner_progress_learner_id", "learner_progress", ["learner_id"])
    op.create_index("ix_learner_progress_course_id",  "learner_progress", ["course_id"])
    op.create_index("ix_learner_progress_lesson_id",  "learner_progress", ["lesson_id"])

    # ── assessment_attempts ──────────────────────────────────────────────
    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("time_spent_minutes", sa.Float(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100",
                           name="ck_attempt_score_range"),
        sa.CheckConstraint("time_spent_minutes >= 0",  name="ck_attempt_time_spent"),
        sa.CheckConstraint("attempt_number >= 1",      name="ck_attempt_number_positive"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"],  ["lessons.id"],  ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key"),
    )
    op.create_index("ix_assessment_attempts_learner_id",
                    "assessment_attempts", ["learner_id"])
    op.create_index("ix_assessment_attempts_lesson_id",
                    "assessment_attempts", ["lesson_id"])
    op.create_index("ix_assessment_attempts_idempotency_key",
                    "assessment_attempts", ["idempotency_key"], unique=True)

    # ── learner_signals ──────────────────────────────────────────────────
    op.create_table(
        "learner_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column(
            "performance_trend",
            postgresql.ENUM("improving", "stable", "declining", "insufficient_data",
                            name="performance_trend", create_type=False),
            server_default="insufficient_data", nullable=False,
        ),
        sa.Column("risk_flags",     postgresql.ARRAY(sa.String()),
                  server_default="{}", nullable=False),
        sa.Column("strength_tags",  postgresql.ARRAY(sa.String()),
                  server_default="{}", nullable=False),
        sa.Column("weakness_tags",  postgresql.ARRAY(sa.String()),
                  server_default="{}", nullable=False),
        sa.Column("engagement_level", sa.String(20),
                  server_default="medium", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"],  ["lessons.id"],  ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "lesson_id", name="uq_signal_learner_lesson"),
    )
    op.create_index("ix_learner_signals_learner_id", "learner_signals", ["learner_id"])
    op.create_index("ix_learner_signals_lesson_id",  "learner_signals", ["lesson_id"])


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    op.drop_table("learner_signals")
    op.drop_table("assessment_attempts")
    op.drop_table("learner_progress")
    op.drop_table("lessons")
    op.drop_table("courses")
    op.drop_table("learners")
    _drop_enums(op.get_bind())
