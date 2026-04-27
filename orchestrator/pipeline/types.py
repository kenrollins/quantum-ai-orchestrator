"""Core types for the orchestrator pipeline.

These types flow through all six pipeline stages. The schema is locked —
adding a new problem class or backend type means updating this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ProblemClass(str, Enum):
    """Closed enum of problem classes. Formulator and Evaluator dispatch on this."""

    QEC_SYNDROME = "qec_syndrome"
    QUBO_ASSIGNMENT = "qubo_assignment"
    QUBO_ROUTING = "qubo_routing"
    QUBO_PORTFOLIO = "qubo_portfolio"


class BackendClass(str, Enum):
    """Backend implementation categories."""

    CLASSICAL = "classical"
    QUANTUM_INSPIRED_ANNEALING = "quantum_inspired_annealing"
    GATE_MODEL_SIMULATION = "gate_model_simulation"
    AI_DECODER = "ai_decoder"
    CLASSICAL_DECODER = "classical_decoder"
    TENSOR_NETWORK_SIMULATION = "tensor_network_simulation"
    VARIATIONAL_SIMULATION = "variational_simulation"


class RunStatus(str, Enum):
    """Status of a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Problem:
    """A node in the problem graph DAG.

    The Decomposer emits these. A single-leaf graph has one Problem with
    parent_id=None. A decomposed ask has multiple Problems linked by parent_id.
    """

    problem_id: str
    problem_class: ProblemClass
    params: dict[str, Any]
    parent_id: str | None = None

    @property
    def fingerprint(self) -> bytes:
        """Content-addressable hash for caching and preference lookup."""
        content = f"{self.problem_class.value}:{sorted(self.params.items())}"
        return hashlib.sha256(content.encode()).digest()[:16]

    @property
    def size_bucket(self) -> str:
        """Coarse size bucket for preference table lookup.

        Returns a string like 'd5_p1e-3' for QEC or 'n96' for QUBO.
        """
        if self.problem_class == ProblemClass.QEC_SYNDROME:
            d = self.params.get("distance", 0)
            p = self.params.get("noise_rate", 0)
            return f"d{d}_p{p:.0e}"
        elif self.problem_class in (
            ProblemClass.QUBO_ASSIGNMENT,
            ProblemClass.QUBO_ROUTING,
            ProblemClass.QUBO_PORTFOLIO,
        ):
            # Binary variable count
            n = self.params.get("num_vars", self.params.get("assets", 0) * self.params.get("tasks", 0))
            return f"n{n}"
        return "unknown"


@dataclass
class ProblemGraph:
    """The full DAG produced by the Decomposer.

    For simple asks, this contains a single leaf. For decomposed asks,
    it contains multiple Problems linked by parent_id.
    """

    run_id: UUID
    ask_text: str
    skill: str
    problems: list[Problem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def root(self) -> Problem | None:
        """The root problem (parent_id is None)."""
        for p in self.problems:
            if p.parent_id is None:
                return p
        return None

    @property
    def leaves(self) -> list[Problem]:
        """Problems with no children (these get dispatched to backends)."""
        parent_ids = {p.parent_id for p in self.problems if p.parent_id}
        return [p for p in self.problems if p.problem_id not in parent_ids]


@dataclass
class BackendInput:
    """Backend-ready input produced by the Formulator.

    The payload type depends on problem_class:
    - QEC_SYNDROME: syndrome tensor + metadata
    - QUBO_*: QUBO matrix Q or Ising (J, h)
    """

    problem: Problem
    payload: dict[str, Any]


@dataclass
class BackendConfig:
    """A backend entry from config/backends.yaml."""

    name: str
    backend_class: BackendClass
    library: str
    applicable_problem_classes: list[ProblemClass]
    gpu_required: bool
    gpu_lane: str | None  # "any", "0", "1", or None for CPU
    footprint_gb: float
    latency_target_ms: int
    phase: int


@dataclass
class BackendChoice:
    """A dispatched backend assignment."""

    backend: BackendConfig
    gpu_lane: int | None  # Actual lane assignment (0, 1, or None)


@dataclass
class Solution:
    """Result from a backend run."""

    backend_name: str
    payload: dict[str, Any]  # Backend-specific result
    wall_time_ms: int
    success: bool
    error: str | None = None


@dataclass
class Grade:
    """Evaluation score for a solution.

    quality: 0.0–1.0, higher is better (e.g., 1 - LER for QEC, obj/bound for QUBO)
    wall_time_ms: actual execution time
    metric_payload: domain-specific metrics (LER, iterations, energy, etc.)
    """

    quality: float
    wall_time_ms: int
    metric_payload: dict[str, Any]


@dataclass
class Outcome:
    """Full result of a backend dispatch: input, solution, and grade."""

    dispatch_id: UUID
    problem: Problem
    backend_choice: BackendChoice
    solution: Solution
    grade: Grade
    dispatched_at: datetime
    finished_at: datetime


@dataclass
class Lesson:
    """A learned preference from the Strategist.

    Bi-temporal: valid_from/valid_to track when this preference was active.
    """

    lesson_id: UUID
    problem_class: ProblemClass
    size_bucket: str
    preferred_backend: str
    confidence: float
    rationale: str | None
    valid_from: datetime
    valid_to: datetime | None = None  # None = currently valid


@dataclass
class Run:
    """A complete pipeline run."""

    run_id: UUID
    ask_text: str
    skill: str
    status: RunStatus
    problem_graph: ProblemGraph | None = None
    outcomes: list[Outcome] = field(default_factory=list)
    # Full race history: every (problem, backend) pair we dispatched, including
    # losers. `outcomes` only carries winners; `race_history` carries all so
    # provenance and the dashboard can show the bake-off.
    race_history: list[Outcome] = field(default_factory=list)
    final_answer: dict[str, Any] | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def create(cls, ask_text: str, skill: str) -> Run:
        """Factory for a new pending run."""
        return cls(
            run_id=uuid4(),
            ask_text=ask_text,
            skill=skill,
            status=RunStatus.PENDING,
        )
