from app.workflows.decision.schemas import VALID_DECISIONS, normalize_decision

DATASTORE = {
    "learners": {},
    "lessons": {},
    "courses": {},
    "decision_history": [],
}


def _ensure_learner(learner_id):
    learner = DATASTORE["learners"].get(learner_id)
    if learner is None:
        raise ValueError("Unknown learner")
    return learner


def _ensure_lesson(lesson_id):
    lesson = DATASTORE["lessons"].get(lesson_id)
    if lesson is None:
        raise ValueError("Unknown lesson")
    return lesson


def _decision_key(learner_id, lesson_id, decision):
    return f"{learner_id}:{lesson_id}:{decision}"


def _build_progress_snapshot(learner):
    return {
        "current_lesson_id": learner.get("current_lesson_id"),
        "completed_lessons": learner.get("completed_lessons", []),
        "next_lesson_id": learner.get("next_lesson_id"),
        "course_progress": learner.get("course_progress", 0),
        "certification_state": learner.get("certification_state", {"eligible": False, "course_completion": 0}),
    }


def apply_decision(payload: dict):
    if not isinstance(payload, dict):
        raise ValueError("Decision payload must be a dictionary")

    learner_id = payload.get("learner_id")
    lesson_id = payload.get("lesson_id")
    decision = normalize_decision(payload.get("decision"))
    reasoning = str(payload.get("reasoning", "")).strip()
    confidence = float(payload.get("confidence", 0.0))
    reasoning_source = str(payload.get("reasoning_source", "fallback")).strip().lower()

    if learner_id is None or lesson_id is None:
        raise ValueError("Learner and lesson identifiers are required")
    if decision is None or decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")
    if not reasoning:
        raise ValueError("Missing reasoning")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Invalid confidence")

    learner = _ensure_learner(int(learner_id))
    lesson = _ensure_lesson(int(lesson_id))

    if learner.get("course_id") != lesson.get("course_id"):
        raise ValueError("Lesson does not belong to the learner course")

    learner.setdefault("execution_keys", set())
    execution_key = _decision_key(int(learner_id), int(lesson_id), decision)
    if execution_key in learner["execution_keys"]:
        if decision == "mentor":
            return {
                "decision": decision,
                "action": "mentor_intervention_created",
                "next_step": "Review mentor guidance and retry remediation",
                "updated_progress": _build_progress_snapshot(learner),
                "state_updated": False,
                "mentor_payload": learner.get("active_mentor", {
                    "type": "mentor_checkin",
                    "status": "pending",
                }),
                "reasoning": reasoning,
                "confidence": confidence,
                "reasoning_source": reasoning_source,
            }
        if decision == "reinforce":
            return {
                "decision": decision,
                "action": "reinforcement_assigned",
                "next_step": "Complete targeted practice exercises",
                "updated_progress": _build_progress_snapshot(learner),
                "state_updated": False,
                "reasoning": reasoning,
                "confidence": confidence,
                "reasoning_source": reasoning_source,
            }
        return {
            "decision": decision,
            "action": "lesson_advanced",
            "next_step": "Proceed to the next lesson",
            "updated_progress": _build_progress_snapshot(learner),
            "state_updated": False,
            "reasoning": reasoning,
            "confidence": confidence,
            "reasoning_source": reasoning_source,
        }

    if decision == "reinforce":
        reinforcement_count = int(learner.get("reinforcement_count", 0)) + 1
        learner["reinforcement_count"] = reinforcement_count
        learner["reinforcement_state"] = "active"
        learner["active_reinforcement"] = {
            "lesson_id": lesson_id,
            "exercise_type": "targeted_practice",
            "status": "active",
        }
        learner["execution_keys"].add(execution_key)
        result = {
            "decision": "reinforce",
            "action": "reinforcement_assigned",
            "next_step": "Complete targeted practice exercises",
            "updated_progress": _build_progress_snapshot(learner),
            "state_updated": True,
            "reasoning": reasoning,
            "confidence": confidence,
            "reasoning_source": reasoning_source,
        }
    elif decision == "advance":
        # Optimize: Use O(1) set lookup
        required_lesson_ids = set(DATASTORE["courses"][learner["course_id"]]["required_lessons"])
        if lesson_id not in required_lesson_ids:
            raise ValueError("Lesson is not part of the required course path")

        completed_lessons = learner.get("completed_lessons", [])
        
        # Reject if trying to advance a lesson they aren't currently on and haven't completed
        if lesson_id != learner.get("current_lesson_id") and lesson_id not in completed_lessons:
            raise ValueError("Learner has not satisfied the current lesson requirements")

        if lesson_id not in completed_lessons:
            learner.setdefault("completed_lessons", [])
            learner["completed_lessons"].append(lesson_id)

        next_lesson_id = lesson.get("next_lesson_id")
        if next_lesson_id is None:
            learner["course_progress"] = 100
            learner["current_lesson_id"] = lesson_id
            learner["next_lesson_id"] = None
            learner["certification_state"] = {"eligible": True, "course_completion": 100}
        else:
            learner["current_lesson_id"] = next_lesson_id
            learner["next_lesson_id"] = next_lesson_id
            learner["course_progress"] = min(100, max(learner.get("course_progress", 0), 50 + (len(learner.get("completed_lessons", [])) * 10)))
        learner["execution_keys"].add(execution_key)
        learner["required_lessons_completed"] = len(learner.get("completed_lessons", []))
        result = {
            "decision": "advance",
            "action": "lesson_advanced",
            "next_step": "Proceed to the next lesson",
            "updated_progress": _build_progress_snapshot(learner),
            "state_updated": True,
            "reasoning": reasoning,
            "confidence": confidence,
            "reasoning_source": reasoning_source,
        }
    elif decision == "mentor":
        if learner.get("active_mentor") is not None and learner["active_mentor"].get("status") == "pending":
            mentor_payload = learner["active_mentor"]
        else:
            mentor_payload = {
                "type": "mentor_checkin",
                "learner": learner.get("name", "Learner"),
                "lesson": DATASTORE["lessons"].get(lesson_id, {}).get("title", "Unknown lesson"),
                "reason": reasoning,
                "recommended_action": "Review prerequisite concepts.",
                "status": "pending",
            }
            learner["active_mentor"] = mentor_payload
            learner["mentor_state"] = "pending"
        learner["execution_keys"].add(execution_key)
        result = {
            "decision": "mentor",
            "action": "mentor_intervention_created",
            "next_step": "Review mentor guidance and retry remediation",
            "updated_progress": _build_progress_snapshot(learner),
            "state_updated": True,
            "mentor_payload": mentor_payload,
            "reasoning": reasoning,
            "confidence": confidence,
            "reasoning_source": reasoning_source,
        }
    else:
        raise ValueError("Unsupported decision")

    record = {
        "learner_id": learner_id,
        "lesson_id": lesson_id,
        "decision": decision,
        "reasoning": reasoning,
        "confidence": confidence,
        "reasoning_source": reasoning_source,
        "executed_action": result["action"],
        "created_at": "now",
    }
    DATASTORE["decision_history"].append(record)
    learner.setdefault("decision_history", []).append(record)
    return result
