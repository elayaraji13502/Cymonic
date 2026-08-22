from app.schemas.performance import build_error_response
from app.workflows.performance.context_builder import build_context_package

# Mock database for Workflow 2
MOCK_DB = {
    "1_3": {
        "scores": [58, 62, 68],
        "threshold": 70,
        "engagement": "high",
        "intervention_history": {"count": 0},
        "certification_required": True,
        "risk_flags": [],
        "strength_tags": ["loops"],
        "weakness_tags": ["recursion"]
    },
    "2_4": {
        "scores": [90, 84, 76],
        "threshold": 80,
        "engagement": "low",
        "intervention_history": {"count": 1},
        "certification_required": True,
        "risk_flags": ["disengaged"],
        "strength_tags": [],
        "weakness_tags": []
    }
}

def get_performance_context(learner_id: int, lesson_id: int):
    key = f"{learner_id}_{lesson_id}"
    raw_data = MOCK_DB.get(key)
    
    if not raw_data:
        return build_error_response("NOT_FOUND", "Learner progress record not found.")
        
    try:
        context = build_context_package(learner_id, lesson_id, raw_data)
        return context
    except ValueError as e:
        return build_error_response("CONFIGURATION_ERROR", str(e))
    except Exception as e:
        return build_error_response("INTERNAL_ERROR", "An unexpected error occurred.")

def analyze_performance(payload: dict):
    learner_id = payload.get("learner_id")
    lesson_id = payload.get("lesson_id")
    
    if learner_id is None or lesson_id is None:
        return build_error_response("BAD_REQUEST", "learner_id and lesson_id are required.")
        
    context_response = get_performance_context(learner_id, lesson_id)
    
    if "error" in context_response:
        return context_response
        
    return {
        "learner_context": context_response,
        "analysis_status": "complete"
    }
