"""
decision_engine/test_cases.py
==============================
Predefined learner contexts for development and testing.

These contexts are intentionally designed to exercise different branches of
the decision engine.  They are READ-ONLY — nothing here modifies learner data.

Each case documents:
  - What it tests
  - Which signals should dominate
  - What the expected decision is (and WHY it is not just a threshold check)
"""

from __future__ import annotations

from app.decision_engine.schemas import (
    CourseContext,
    DifficultyEnum,
    EffectivenessEnum,
    EngagementContext,
    EngagementLevelEnum,
    InterventionContext,
    LearnerContext,
    LearningContext,
    MasteryConsistencyEnum,
    MasteryContext,
    MasteryStatusEnum,
    PerformanceContext,
    TrendEnum,
    VelocityEnum,
    CertRiskEnum,
)

# ---------------------------------------------------------------------------
# Case registry
# ---------------------------------------------------------------------------

TEST_CASES: dict[str, LearnerContext] = {}


def _register(name: str, ctx: LearnerContext) -> LearnerContext:
    TEST_CASES[name] = ctx
    return ctx


# ---------------------------------------------------------------------------
# CASE_01 — Improving learner, no prior reinforcement
# Expected: REINFORCE
# Why: Not mastered, improving trend, high engagement, no prior reinforcement.
#      The recoverable gap and upward momentum make continued practice optimal.
# ---------------------------------------------------------------------------
CASE_01_IMPROVING_LEARNER = _register(
    "CASE_01_IMPROVING_LEARNER",
    LearnerContext(
        learner_id=101,
        lesson_id=12,
        context_version=1,
        performance=PerformanceContext(
            latest_score=62,
            average_score=60,
            previous_scores=[55, 58, 62],
            trend=TrendEnum.improving,
            attempt_count=3,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.not_mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.insufficient,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=1),
        learning=LearningContext(velocity=VelocityEnum.normal, completion_percentage=65),
        intervention=InterventionContext(
            reinforcement_count=0,
            effectiveness=EffectivenessEnum.none,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=True,
            certification_required=True,
            certification_risk=CertRiskEnum.medium,
        ),
        risk_flags=[],
        weakness_tags=["recursion"],
        strength_tags=["problem_solving"],
    ),
)

# ---------------------------------------------------------------------------
# CASE_02 — Clear mastery
# Expected: ADVANCE
# Why: Mastered status, consistent scores, sufficient history, no blockers.
#      All advance requirements are satisfied.
# ---------------------------------------------------------------------------
CASE_02_CLEAR_MASTERY = _register(
    "CASE_02_CLEAR_MASTERY",
    LearnerContext(
        learner_id=102,
        lesson_id=5,
        context_version=1,
        performance=PerformanceContext(
            latest_score=88,
            average_score=85,
            previous_scores=[82, 84, 88],
            trend=TrendEnum.stable,
            attempt_count=4,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.consistent,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
        learning=LearningContext(velocity=VelocityEnum.fast, completion_percentage=100),
        intervention=InterventionContext(
            reinforcement_count=1,
            effectiveness=EffectivenessEnum.effective,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=True,
            certification_required=True,
            certification_risk=CertRiskEnum.low,
        ),
        risk_flags=[],
        weakness_tags=[],
        strength_tags=["algorithms", "data_structures"],
    ),
)

# ---------------------------------------------------------------------------
# CASE_03 — Repeated failure, max reinforcement, ineffective
# Expected: MENTOR
# Why: Override fires — max reinforcement reached AND ineffective AND not mastered.
#      Low engagement + declining trend + score far below threshold.
# ---------------------------------------------------------------------------
CASE_03_REPEATED_FAILURE = _register(
    "CASE_03_REPEATED_FAILURE",
    LearnerContext(
        learner_id=103,
        lesson_id=8,
        context_version=1,
        performance=PerformanceContext(
            latest_score=48,
            average_score=52,
            previous_scores=[55, 52, 50, 48],
            trend=TrendEnum.declining,
            attempt_count=5,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.not_mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.inconsistent,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=4),
        learning=LearningContext(velocity=VelocityEnum.stalled, completion_percentage=40),
        intervention=InterventionContext(
            reinforcement_count=3,
            effectiveness=EffectivenessEnum.ineffective,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.hard,
            required_lesson=True,
            certification_required=True,
            certification_risk=CertRiskEnum.high,
        ),
        risk_flags=["exam_failing"],
        weakness_tags=["dynamic_programming", "recursion"],
        strength_tags=[],
    ),
)

# ---------------------------------------------------------------------------
# CASE_04 — High score but declining trend + low engagement
# Expected: NOT automatically ADVANCE — engine must flag the conflict.
#           Likely REINFORCE or MENTOR depending on scores; engine explains.
# Why: Score=90 satisfies mastery threshold, but declining trend + low engagement
#      + high reinforcement count block ADVANCE. The engine should explain
#      that the high score is not sufficient evidence of stable mastery.
# ---------------------------------------------------------------------------
CASE_04_HIGH_SCORE_DECLINING = _register(
    "CASE_04_HIGH_SCORE_DECLINING",
    LearnerContext(
        learner_id=104,
        lesson_id=15,
        context_version=1,
        performance=PerformanceContext(
            latest_score=90,
            average_score=70,
            previous_scores=[78, 72, 68, 90],
            trend=TrendEnum.declining,
            attempt_count=4,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.in_progress,
            threshold=75,
            consistency=MasteryConsistencyEnum.inconsistent,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=5),
        learning=LearningContext(velocity=VelocityEnum.slow, completion_percentage=75),
        intervention=InterventionContext(
            reinforcement_count=2,
            effectiveness=EffectivenessEnum.partially_effective,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=True,
            certification_required=False,
            certification_risk=CertRiskEnum.low,
        ),
        risk_flags=[],
        weakness_tags=["system_design"],
        strength_tags=["coding_speed"],
    ),
)

# ---------------------------------------------------------------------------
# CASE_05 — Low score but improving fast, high engagement
# Expected: REINFORCE
# Why: Score=58 is below mastery, but strong improving trend, high engagement,
#      zero prior reinforcement. The learner is self-correcting — reinforce.
# ---------------------------------------------------------------------------
CASE_05_LOW_SCORE_IMPROVING = _register(
    "CASE_05_LOW_SCORE_IMPROVING",
    LearnerContext(
        learner_id=105,
        lesson_id=3,
        context_version=1,
        performance=PerformanceContext(
            latest_score=58,
            average_score=52,
            previous_scores=[44, 50, 55, 58],
            trend=TrendEnum.improving,
            attempt_count=4,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.not_mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.insufficient,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.high, inactivity_days=0),
        learning=LearningContext(velocity=VelocityEnum.fast, completion_percentage=50),
        intervention=InterventionContext(
            reinforcement_count=0,
            effectiveness=EffectivenessEnum.none,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=False,
            certification_required=False,
            certification_risk=CertRiskEnum.low,
        ),
        risk_flags=[],
        weakness_tags=["loops"],
        strength_tags=["debugging"],
    ),
)

# ---------------------------------------------------------------------------
# CASE_06 — Insufficient history, unknown engagement
# Expected: Controlled low-confidence REINFORCE (default safe action)
# Why: No meaningful history. Engine must NOT fabricate evidence.
#      Returns lowest possible confidence.
# ---------------------------------------------------------------------------
CASE_06_INSUFFICIENT_HISTORY = _register(
    "CASE_06_INSUFFICIENT_HISTORY",
    LearnerContext(
        learner_id=106,
        lesson_id=1,
        context_version=1,
        performance=PerformanceContext(
            latest_score=None,
            average_score=None,
            previous_scores=[],
            trend=TrendEnum.unknown,
            attempt_count=0,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.unknown,
            threshold=None,
            consistency=MasteryConsistencyEnum.unknown,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.unknown, inactivity_days=0),
        learning=LearningContext(velocity=VelocityEnum.unknown, completion_percentage=None),
        intervention=InterventionContext(
            reinforcement_count=0,
            effectiveness=EffectivenessEnum.none,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.easy,
            required_lesson=True,
            certification_required=False,
            certification_risk=CertRiskEnum.unknown,
        ),
        risk_flags=[],
        weakness_tags=[],
        strength_tags=[],
    ),
)

# ---------------------------------------------------------------------------
# CASE_07 — Conflicting signals: high score, declining trend, low engagement,
#           high attempt count
# Expected: NOT a blind ADVANCE. Engine must reason through the conflict.
#           Expected: MENTOR or REINFORCE depending on weight balance.
# ---------------------------------------------------------------------------
CASE_07_CONFLICTING_SIGNALS = _register(
    "CASE_07_CONFLICTING_SIGNALS",
    LearnerContext(
        learner_id=107,
        lesson_id=20,
        context_version=2,
        performance=PerformanceContext(
            latest_score=82,
            average_score=63,
            previous_scores=[70, 65, 58, 60, 82],
            trend=TrendEnum.declining,
            attempt_count=5,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.in_progress,
            threshold=75,
            consistency=MasteryConsistencyEnum.inconsistent,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.low, inactivity_days=6),
        learning=LearningContext(velocity=VelocityEnum.slow, completion_percentage=70),
        intervention=InterventionContext(
            reinforcement_count=2,
            effectiveness=EffectivenessEnum.partially_effective,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.hard,
            required_lesson=True,
            certification_required=True,
            certification_risk=CertRiskEnum.medium,
        ),
        risk_flags=["exam_failing"],
        weakness_tags=["concurrency", "memory_management"],
        strength_tags=["syntax"],
    ),
)

# ---------------------------------------------------------------------------
# CASE_08 — Score declining, 3 reinforcements, ineffective
# Expected: MENTOR
# Why: Override fires: max reinforcement + ineffective + not mastered.
#      Direct override to MENTOR.
# ---------------------------------------------------------------------------
CASE_08_INEFFECTIVE_REINFORCEMENT = _register(
    "CASE_08_INEFFECTIVE_REINFORCEMENT",
    LearnerContext(
        learner_id=108,
        lesson_id=9,
        context_version=1,
        performance=PerformanceContext(
            latest_score=55,
            average_score=57,
            previous_scores=[60, 58, 56, 55],
            trend=TrendEnum.declining,
            attempt_count=4,
        ),
        mastery=MasteryContext(
            status=MasteryStatusEnum.not_mastered,
            threshold=75,
            consistency=MasteryConsistencyEnum.inconsistent,
        ),
        engagement=EngagementContext(level=EngagementLevelEnum.medium, inactivity_days=2),
        learning=LearningContext(velocity=VelocityEnum.slow, completion_percentage=55),
        intervention=InterventionContext(
            reinforcement_count=3,
            effectiveness=EffectivenessEnum.ineffective,
            previous_mentor_intervention=False,
        ),
        course=CourseContext(
            lesson_difficulty=DifficultyEnum.medium,
            required_lesson=True,
            certification_required=True,
            certification_risk=CertRiskEnum.medium,
        ),
        risk_flags=[],
        weakness_tags=["object_oriented_design"],
        strength_tags=["testing"],
    ),
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_case(name: str) -> LearnerContext:
    """Retrieve a test case by name.  Raises KeyError if not found."""
    if name not in TEST_CASES:
        available = ", ".join(TEST_CASES.keys())
        raise KeyError(f"Unknown test case '{name}'. Available: {available}")
    return TEST_CASES[name]


def list_cases() -> list[str]:
    return list(TEST_CASES.keys())
