# CYMONIC: Adaptive Learning Coach

This repository contains the core backend workflows for the **CYMONIC Adaptive Learning Coach** hackathon project. The system dynamically analyzes learner performance, reasons over their context, and executes adaptive learning strategies (Reinforce, Advance, or Mentor) without relying on hardcoded score thresholds.

## 🏗️ Architecture & Workflows

This project implements three critical workflows in the adaptive learning loop:

1. **Workflow 2 (Context & Performance Analysis)**: Ingests raw learner data, calculates performance trends, evaluates mastery against thresholds, and builds a structured context package.
2. **Workflow 3 (Adaptive Agent Reasoning)**: Consumes the context package and uses an LLM (with a deterministic fallback) to reason over the evidence and select the best intervention strategy.
3. **Workflow 4 (Strategy Execution)**: Safely executes the validated decision, updates the learner's progression state, assigns targeted practice, or creates in-app mentor interventions.

## 📦 Dependencies & Versions

The project is built with modern, high-performance Python tools. The following versions were used during development:

- **Python**: `3.14.x` (Compatible with `3.10+`)
- **Pydantic**: `2.13.4` (For fast, Rust-based request validation)
- **pytest**: `9.1.1` (For comprehensive unit testing)
- **pytest-asyncio**: `1.4.0` (For testing asynchronous endpoints)

*(Note: While designed for **FastAPI** and **SQLAlchemy/PostgreSQL**, this repository currently uses a mock in-memory datastore and API-style router functions to demonstrate the core logic for the hackathon scope.)*

## 🚀 Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/elayaraji13502/Cymonic.git
   cd Cymonic
   ```

2. **Create a virtual environment** (Recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install pydantic==2.13.4 pytest==9.1.1 pytest-asyncio==1.4.0
   ```

## 🎮 Running the Demo

We have included an end-to-end demo script that simulates a struggling learner, evaluates their context, and executes a reinforcement strategy.

Run the demo from the root directory:
```bash
python demo.py
```

**What you will see:**
1. The initial state of the learner.
2. The reasoning engine's decision (e.g., `reinforce`) along with its confidence score and explanation of rejected alternatives.
3. The execution result updating the learner's state.
4. The final learner state and certification progress.

## 🧪 Running the Tests

The project includes a robust test suite with **70 tests** covering 100% of the edge cases, business constraints, and idempotency checks.

To run the full test suite:
```bash
python -m pytest app/tests/
```

## 📁 Project Structure

```text
app/
├── routers/          # API-style endpoints for the workflows
├── schemas/          # Pydantic models for request validation
├── services/         # External service adapters (e.g., LLM integration)
├── tests/            # Comprehensive edge-case and workflow tests
└── workflows/
    ├── decision/       # Workflow 3: Reasoning, validation, and fallback logic
    ├── learning_path/  # Workflow 4: Strategy execution and state updates
    └── performance/    # Workflow 2: Trend, mastery, and context building
```

## 🛡️ Key Features
- **No Hardcoded Decisions**: Decisions are made based on holistic context (engagement, trends, attempt pressure), not just a flat score threshold.
- **Idempotency**: Repeated execution requests are handled safely without duplicating interventions or skipping lessons.
- **Asynchronous I/O**: Endpoints are written as `async def` to support high concurrency in FastAPI.
- **O(1) Lookups**: Optimized data structures prevent performance bottlenecks on massive learner histories.