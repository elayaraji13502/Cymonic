"""
Pytest configuration and shared fixtures for Workflow 1 tests.

Strategy
--------
- Uses SQLite in-memory via aiosqlite (no PostgreSQL required for tests).
- Creates all tables via Base.metadata.create_all() before the test session.
- Each test gets an isolated AsyncSession whose commit() is intercepted so it
  only releases the inner SAVEPOINT — the outer connection-level transaction
  is rolled back at the end of the test, keeping tests fully independent.
- The FastAPI TestClient is replaced with httpx.AsyncClient pointed at the
  ASGI app, using the overridden `get_db` dependency.

SAVEPOINT isolation pattern
----------------------------
  1. Open a raw async connection and BEGIN an outer transaction.
  2. Bind an AsyncSession to that connection.
  3. Call session.begin_nested() to set a SAVEPOINT.
  4. Monkey-patch session.commit() → session.begin_nested() so the service's
     commit() call just releases the SAVEPOINT and opens a new one rather than
     actually committing to the DB.
  5. After the test, rollback the outer connection transaction — everything
     written during the test disappears.

Note on SQLite vs PostgreSQL
----------------------------
SQLite does not support PostgreSQL ARRAY columns.  The LearnerSignal model
uses ARRAY(String).  We patch those columns to JSON before the engine is
created so that SQLite accepts them.  The migration (which targets PostgreSQL)
is correct and unchanged.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

# ---------------------------------------------------------------------------
# SQLite-compatible model patch  (must happen BEFORE create_all)
# ---------------------------------------------------------------------------
from app.models.learner_signal import LearnerSignal  # noqa: E402

LearnerSignal.__table__.c.risk_flags.type = JSON()
LearnerSignal.__table__.c.strength_tags.type = JSON()
LearnerSignal.__table__.c.weakness_tags.type = JSON()

# Trigger full model registry import
import app.models  # noqa: F401, E402

# ---------------------------------------------------------------------------
# Test database URL
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Session-scoped event loop
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Session-scoped engine — tables created once
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


# ---------------------------------------------------------------------------
# Per-test isolated AsyncSession
#
# Pattern:
#   outer connection transaction  (never committed — rolled back at teardown)
#     └── SAVEPOINT  (released each time the service calls session.commit())
#
# By replacing session.commit with a function that just opens a new SAVEPOINT
# we let the service code run unmodified while keeping all writes in the outer
# transaction that is rolled back after the test.
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as conn:
        await conn.begin()                           # outer transaction
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await session.begin_nested()                 # initial SAVEPOINT

        async def _mock_commit():
            """Release current savepoint, open a new one — don't touch outer tx."""
            await session.begin_nested()

        session.commit = _mock_commit                # type: ignore[method-assign]

        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()                    # discard all test writes


# ---------------------------------------------------------------------------
# Seed helpers (self-contained — not using app/seed.py)
# ---------------------------------------------------------------------------
from datetime import datetime, timezone

from app.models.assessment_attempt import AssessmentAttempt  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.models.learner import Learner, LearnerStatus  # noqa: E402
from app.models.learner_progress import (  # noqa: E402
    EngagementLevel,
    LearnerProgress,
    MasteryStatus,
    ProgressStatus,
)
from app.models.learner_signal import PerformanceTrend  # noqa: E402
from app.models.lesson import Lesson  # noqa: E402

_NOW = datetime.now(tz=timezone.utc)


async def make_learner(session: AsyncSession, **kwargs) -> Learner:
    defaults = dict(
        id=1, name="Test Learner", email="test@example.com",
        status=LearnerStatus.active, created_at=_NOW,
    )
    defaults.update(kwargs)
    obj = Learner(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def make_course(session: AsyncSession, **kwargs) -> Course:
    defaults = dict(
        id=1, title="Test Course", description="desc",
        certification_required=False, created_at=_NOW,
    )
    defaults.update(kwargs)
    obj = Course(**defaults)
    session.add(obj)
    await session.flush()
    return obj


async def make_lesson(session: AsyncSession, **kwargs) -> Lesson:
    defaults = dict(
        id=1, course_id=1, title="Test Lesson",
        sequence_number=1, difficulty=2,
        mastery_threshold=70.0, is_required=True,
    )
    defaults.update(kwargs)
    obj = Lesson(**defaults)
    session.add(obj)
    await session.flush()
    return obj


# ---------------------------------------------------------------------------
# FastAPI async test client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client bound to the FastAPI ASGI app.
    The `get_db` dependency is overridden to yield the test session so every
    request uses the same isolated, rollback-protected transaction.
    """
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
