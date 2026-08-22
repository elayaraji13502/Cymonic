import asyncio
import json

from app.routers.decisions import evaluate_decision_endpoint
from app.routers.learning_path import apply_decision_endpoint, get_certification_status, get_learning_path
from app.workflows.learning_path.executor import DATASTORE


def setup_demo_data():
    DATASTORE.clear()
    DATASTORE.update({
        "learners": {
            1: {
                "id": 1,
                "name": "Arun",
                "current_lesson_id": 1,
                "completed_lessons": [],
                "course_id": 10,
                "course_progress": 0,
                "next_lesson_id": 2,
                "required_lessons_completed": 0,
                "required_assessments_passed": 0,
                "reinforcement_count": 0,
                "reinforcement_state": "none",
                "mentor_state": "none",
                "certification_state": {"eligible": False, "course_completion": 0},
                "completed_courses": [],
                "decision_history": [],
                "execution_keys": set(),
                "active_reinforcement": None,
                "active_mentor": None,
            }
        },
        "lessons": {
            1: {"id": 1, "course_id": 10, "title": "Intro to Python", "required": True, "next_lesson_id": 2, "prerequisites": []},
            2: {"id": 2, "course_id": 10, "title": "Control Flow", "required": True, "next_lesson_id": 3, "prerequisites": [1]},
            3: {"id": 3, "course_id": 10, "title": "Data Structures", "required": True, "next_lesson_id": None, "prerequisites": [2]},
        },
        "courses": {
            10: {"id": 10, "name": "Python Foundations", "required_lessons": [1, 2, 3], "required_assessments_total": 1}
        },
        "decision_history": [],
    })


async def run_demo():
    setup_demo_data()
    print("=== CYMONIC ADAPTIVE LEARNING COACH DEMO ===\n")

    # Simulate a struggling learner context
    learner_context = {
        "latest_score": 65,
        "average_score": 68,
        "trend": "declining",
        "attempts": 2,
        "mastery": "not_mastered",
        "threshold": 75,
        "engagement": "medium",
        "learning_velocity": "slow",
        "previous_reinforcement": 0,
        "reinforcement_effectiveness": "none",
        "risk_flags": [],
        "certification_risk": "low",
        "lesson_difficulty": "medium",
        "required_lesson": True,
        "previous_decisions": [],
    }

    print("1. Initial Learner State:")
    print(json.dumps(await get_learning_path(1), indent=2))
    print("\n--------------------------------------------------\n")

    print("2. Running Workflow 3 (Decision Evaluation)...")
    decision_payload = await evaluate_decision_endpoint({
        "learner_id": 1,
        "lesson_id": 1,
        "learner_context": learner_context
    })
    print("Decision Output:")
    print(json.dumps(decision_payload, indent=2))
    print("\n--------------------------------------------------\n")

    print("3. Running Workflow 4 (Strategy Execution)...")
    # Pass the validated decision to Workflow 4
    execution_payload = {
        "learner_id": 1,
        "lesson_id": 1,
        **decision_payload
    }
    execution_result = await apply_decision_endpoint(execution_payload)
    print("Execution Result:")
    print(json.dumps(execution_result, indent=2))
    print("\n--------------------------------------------------\n")

    print("4. Final Learner State:")
    print(json.dumps(await get_learning_path(1), indent=2))
    print("\nCertification Status:")
    print(json.dumps(await get_certification_status(1, 10), indent=2))


if __name__ == "__main__":
    asyncio.run(run_demo())
