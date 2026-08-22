from app.schemas.requests import ApplyDecisionRequest
from app.workflows.learning_path.executor import DATASTORE, apply_decision


async def get_learning_path(learner_id):
    learner = DATASTORE["learners"].get(int(learner_id))
    if learner is None:
        raise ValueError("Unknown learner")
    return {
        "current_lesson": learner.get("current_lesson_id"),
        "completed_lessons": learner.get("completed_lessons", []),
        "next_lesson": learner.get("next_lesson_id"),
        "current_recommendation_state": learner.get("reinforcement_state", "none"),
        "reinforcement_state": learner.get("reinforcement_state", "none"),
        "mentor_state": learner.get("mentor_state", "none"),
        "certification_progress": learner.get("certification_state", {"eligible": False, "course_completion": 0}),
    }


async def get_certification_status(learner_id, course_id):
    learner = DATASTORE["learners"].get(int(learner_id))
    if learner is None:
        raise ValueError("Unknown learner")
    course = DATASTORE["courses"].get(int(course_id))
    if course is None:
        raise ValueError("Unknown course")

    # Optimize: Use O(1) set lookups instead of O(N) list scans
    required_lessons_set = set(course.get("required_lessons", []))
    required_total = len(required_lessons_set)
    
    required_completed = sum(1 for lesson_id in learner.get("completed_lessons", []) if lesson_id in required_lessons_set)
    
    assessments_total = course.get("required_assessments_total", 0)
    assessments_passed = learner.get("required_assessments_passed", 0)
    completion = min(100, int((required_completed / required_total) * 100 if required_total else 0))
    eligible = required_completed >= required_total and assessments_passed >= assessments_total

    return {
        "course_completion": completion,
        "required_lessons_completed": required_completed,
        "required_lessons_total": required_total,
        "required_assessments_passed": assessments_passed,
        "required_assessments_total": assessments_total,
        "certification_eligible": eligible,
    }


async def apply_decision_endpoint(payload: dict):
    if not isinstance(payload, dict):
        raise ValueError("Decision payload must be a dictionary")
        
    # Optimize: Use Pydantic for fast, robust validation
    try:
        request = ApplyDecisionRequest(**payload)
    except Exception as e:
        raise ValueError(f"Invalid request: {e}")
        
    return apply_decision(request.model_dump())
