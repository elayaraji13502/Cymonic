"""
Adaptive Learning Coach — FastAPI application entry point.

Workflow 2: Context & Performance Analysis
"""

from fastapi import FastAPI

from app.routers import performance

app = FastAPI(
    title="Adaptive Learning Coach — Workflow 2",
    description="Context & Performance Analysis API",
    version="1.0.0",
)

app.include_router(performance.router)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}
