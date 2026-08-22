import json
import os
from typing import Any


def _safe_json_loads(raw):
    if raw is None:
        raise ValueError("No LLM output")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ValueError("Empty LLM output")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed JSON") from exc
    if isinstance(raw, dict):
        return raw
    raise ValueError("Unsupported LLM output type")


def call_llm(context: dict[str, Any]):
    """Use the Limitless LLM only if configuration is available."""
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    if not (api_key and base_url and model):
        raise RuntimeError("LLM unavailable")

    # This project is intentionally demo-scoped; actual LLM calls are not executed here.
    # In real hackathon deployment, this function would invoke the configured provider.
    raise RuntimeError("LLM integration not configured in this local workspace")
