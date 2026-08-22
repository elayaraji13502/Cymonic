"""
app/main.py
===========
FastAPI application entry point for Module 3 — Adaptive Decision Engine.

Run locally:
    uvicorn app.main:app --reload --port 8003

Swagger UI:
    http://localhost:8003/docs

ReDoc:
    http://localhost:8003/redoc
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else
load_dotenv()

from app.api.decisions import router as decisions_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=" * 60)
    logger.info("Module 3 — Adaptive Decision Engine starting up")
    logger.info("LLM_MODEL     : %s", os.getenv("LLM_MODEL", "llama3-8b-8192"))
    logger.info("FORCE_FALLBACK: %s", os.getenv("FORCE_FALLBACK", "false"))
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and len(groq_key) > 20 and not groq_key.startswith("gsk_..."):
        logger.info("GROQ_API_KEY  : configured ✓")
    else:
        logger.info("GROQ_API_KEY  : not configured — running in fallback mode")
    logger.info("=" * 60)
    yield
    logger.info("Module 3 shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Adaptive Decision Engine",
    description=(
        "**Module 3** of the Adaptive Learning Coach.\n\n"
        "Receives a structured learner context from Module 2 and returns "
        "exactly one adaptive decision: **reinforce**, **advance**, or **mentor**.\n\n"
        "The decision is accompanied by:\n"
        "- Natural-language reasoning\n"
        "- Confidence score\n"
        "- Supporting signals\n"
        "- Rejected alternative explanations\n"
        "- Decision factors (supporting / blocking) per candidate\n\n"
        "This module does **not** modify learner data and does **not** "
        "execute Module 4 actions."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS (permissive for hackathon — restrict in production)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(decisions_router)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    return {
        "module": "Adaptive Decision Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/decisions/health",
    }
