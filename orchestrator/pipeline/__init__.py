"""Orchestrator pipeline modules.

The pipeline stages in order:
1. Decomposer: NL ask → problem graph DAG
2. Formulator: problem → backend-ready input
3. Dispatcher: picks backends from registry + Postgres preferences
4. (Backends execute in parallel)
5. Evaluator: scores solutions
6. Reassembler: walks DAG bottom-up to produce final answer
7. Strategist: updates Postgres preferences (Phase 2)
"""

from .types import (
    BackendChoice,
    BackendClass,
    BackendConfig,
    BackendInput,
    Grade,
    Lesson,
    Outcome,
    Problem,
    ProblemClass,
    ProblemGraph,
    Run,
    RunStatus,
    Solution,
)

__all__ = [
    # Types
    "BackendChoice",
    "BackendClass",
    "BackendConfig",
    "BackendInput",
    "Grade",
    "Lesson",
    "Outcome",
    "Problem",
    "ProblemClass",
    "ProblemGraph",
    "Run",
    "RunStatus",
    "Solution",
]
