from app.schemas.requests import EvaluateDecisionRequest
from app.workflows.decision.agent import evaluate_decision


async def evaluate_decision_endpoint(payload: dict):
    """API-style adapter for POST /api/v1/decisions/evaluate.

    The project does not include a web framework in this local workspace, so this
    function provides the contract expected by Workflow 4 while preserving the
    validated structured decision output.
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    # Optimize: Use Pydantic for fast, robust validation
    try:
        request = EvaluateDecisionRequest(**payload)
    except Exception as e:
        raise ValueError(f"Invalid request: {e}")

    return evaluate_decision(
        learner_id=request.learner_id,
        lesson_id=request.lesson_id,
        learner_context=request.learner_context.model_dump(),
    )
