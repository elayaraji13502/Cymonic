from app.workflows.decision.agent import evaluate_decision


def evaluate_decision_endpoint(payload: dict):
    """API-style adapter for POST /api/v1/decisions/evaluate.

    The project does not include a web framework in this local workspace, so this
    function provides the contract expected by Workflow 4 while preserving the
    validated structured decision output.
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    learner_id = payload.get("learner_id")
    lesson_id = payload.get("lesson_id")
    if learner_id is None or lesson_id is None:
        raise ValueError("Request requires learner_id and lesson_id")

    learner_context = payload.get("learner_context")
    if learner_context is None:
        learner_context = {}

    return evaluate_decision(
        learner_id=int(learner_id),
        lesson_id=int(lesson_id),
        learner_context=learner_context,
    )
