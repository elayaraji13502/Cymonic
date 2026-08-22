"""
module3_main.py
===============
FastAPI entry point for Module 3 — Adaptive Decision Engine (standalone).

This file is separate from app/main.py (which belongs to other modules in
the shared repo).  Run Module 3 independently with:

    uvicorn module3_main:app --reload --port 8003

Swagger UI:  http://localhost:8003/docs
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.decisions import router as decisions_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=" * 60)
    logger.info("Module 3 — Adaptive Decision Engine (LangGraph) starting")
    logger.info("LLM_MODEL     : %s", os.getenv("LLM_MODEL", "llama3-8b-8192"))
    logger.info("FORCE_FALLBACK: %s", os.getenv("FORCE_FALLBACK", "false"))
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and len(groq_key) > 20 and not groq_key.startswith("your_groq"):
        logger.info("GROQ_API_KEY  : configured ✓")
    else:
        logger.info("GROQ_API_KEY  : not configured — running in fallback mode")
    logger.info("=" * 60)
    yield
    logger.info("Module 3 shutting down.")


app = FastAPI(
    title="Adaptive Decision Engine",
    description=(
        "**Module 3** of the Adaptive Learning Coach — powered by **LangGraph**.\n\n"
        "Receives a structured learner context and returns exactly one adaptive "
        "decision: **reinforce**, **advance**, or **mentor**.\n\n"
        "The decision pipeline runs as a LangGraph stateful graph:\n"
        "- `extract_signals` → `check_data` → `evaluate_overrides`\n"
        "- → `score_evidence` → `select_candidate` → `llm_reasoning`\n"
        "- → `build_llm_response` OR `fallback_response`\n\n"
        "This module does **not** modify learner data and does **not** "
        "execute Module 4 actions."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decisions_router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "module": "Adaptive Decision Engine",
        "version": "2.0.0",
        "orchestration": "LangGraph",
        "docs": "/docs",
        "health": "/api/v1/decisions/health",
    }
