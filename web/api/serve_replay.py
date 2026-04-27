"""FastAPI replay server backing the dashboard.

Reads provenance from Postgres (`common.runs`, `common.problem_graphs`,
`common.dispatches`, `common.outcomes`) and exposes JSON endpoints the
Next.js UI consumes to render the bake-off, problem graph, and per-skill
panels.

Phase 1 is post-hoc only: a run completes in ~10 s, then the dashboard
fetches it and renders the race. SSE streaming for live runs is Phase 2;
the schema matches it (event-shaped responses) so we can swap in a
streaming endpoint later without changing the UI.

Run with:
    uv run uvicorn web.api.serve_replay:app --reload --host 0.0.0.0 --port 8765
or via:
    qao serve  (TODO: add CLI subcommand)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from orchestrator.cli import _load_dotenv  # auto-load .env so POSTGRES_* are present
from orchestrator.storage import fetch_all, fetch_one

UI_OUT_DIR = Path(__file__).resolve().parents[1] / "ui" / "out"  # Next.js static export
UI_LEGACY_DIR = Path(__file__).resolve().parents[1] / "ui"        # legacy throwaway index.html

logger = logging.getLogger(__name__)

# Load .env on import so POSTGRES_PASSWORD etc. are visible.
_load_dotenv()

app = FastAPI(
    title="quantum-ai-orchestrator replay API",
    version="0.1.0",
    description=(
        "Read-only provenance replay for the orchestrator dashboard. "
        "All data is Postgres-backed; this service does not run pipelines."
    ),
)

# Permissive CORS for local dev — Next.js dev server runs on a different port.
# Phase 2 should tighten this once the UI's served from the same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Liveness check — verifies Postgres reachability."""
    try:
        row = fetch_one("SELECT current_database() AS db, current_user AS \"user\"")
        return {"status": "ok", "postgres": row}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Postgres unreachable: {e}")


@app.get("/api/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=500),
    skill: str | None = Query(None, description="Filter by skill name"),
) -> dict[str, Any]:
    """List recent runs, newest first."""
    if skill:
        rows = fetch_all(
            """
            SELECT run_id, ask_text, skill, status,
                   started_at, finished_at,
                   EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000 AS wall_time_ms
              FROM common.runs
             WHERE skill = %s
             ORDER BY started_at DESC
             LIMIT %s
            """,
            (skill, limit),
        )
    else:
        rows = fetch_all(
            """
            SELECT run_id, ask_text, skill, status,
                   started_at, finished_at,
                   EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000 AS wall_time_ms
              FROM common.runs
             ORDER BY started_at DESC
             LIMIT %s
            """,
            (limit,),
        )
    # Normalize numeric/datetime types for JSON
    for r in rows:
        r["run_id"] = str(r["run_id"])
        if r.get("wall_time_ms") is not None:
            r["wall_time_ms"] = int(r["wall_time_ms"])
    return {"count": len(rows), "runs": rows}


@app.get("/api/runs/{run_id}")
def get_run(run_id: UUID) -> dict[str, Any]:
    """Return one run with its full race history.

    Shape:
        {
          "run": {...},
          "problems": [{problem_id, problem_class, params, ...}, ...],
          "dispatches": [{dispatch_id, problem_id, backend_name, gpu_lane,
                          quality, wall_time_ms, metric_payload, is_winner}, ...]
        }

    `is_winner` is computed per-problem as max(quality) tiebroken by min(wall_time_ms).
    """
    run = fetch_one(
        """
        SELECT run_id, ask_text, skill, status, started_at, finished_at,
               EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000 AS wall_time_ms
          FROM common.runs
         WHERE run_id = %s
        """,
        (str(run_id),),
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run["run_id"] = str(run["run_id"])
    if run.get("wall_time_ms") is not None:
        run["wall_time_ms"] = int(run["wall_time_ms"])

    problems = fetch_all(
        """
        SELECT problem_id, parent_id, problem_class, params, created_at
          FROM common.problem_graphs
         WHERE run_id = %s
         ORDER BY created_at, problem_id
        """,
        (str(run_id),),
    )

    dispatches = fetch_all(
        """
        SELECT d.dispatch_id, d.problem_id, d.backend_name, d.gpu_lane,
               d.dispatched_at,
               o.quality, o.wall_time_ms, o.metric_payload, o.finished_at
          FROM common.dispatches d
          LEFT JOIN common.outcomes o USING (dispatch_id)
         WHERE d.graph_id IN (
             SELECT graph_id FROM common.problem_graphs WHERE run_id = %s
         )
         ORDER BY d.problem_id, d.backend_name
        """,
        (str(run_id),),
    )

    # Mark winners per problem_id (max quality, ties broken by lowest wall_time_ms).
    by_problem: dict[str, list[dict[str, Any]]] = {}
    for d in dispatches:
        d["dispatch_id"] = str(d["dispatch_id"])
        if d.get("quality") is not None:
            d["quality"] = float(d["quality"])
        d["is_winner"] = False
        by_problem.setdefault(d["problem_id"], []).append(d)
    for _pid, ds in by_problem.items():
        rated = [d for d in ds if d["quality"] is not None and d["quality"] > 0]
        if rated:
            best = max(rated, key=lambda d: (d["quality"], -(d["wall_time_ms"] or 1_000_000)))
            best["is_winner"] = True

    return {"run": run, "problems": problems, "dispatches": dispatches}


@app.get("/api/runs/{run_id}/race")
def get_race(
    run_id: UUID,
    problem_id: str = Query(..., description="Which problem within the run"),
) -> dict[str, Any]:
    """Return the bake-off detail for one problem in a run."""
    rows = fetch_all(
        """
        SELECT d.dispatch_id, d.backend_name, d.gpu_lane, d.dispatched_at,
               o.quality, o.wall_time_ms, o.metric_payload, o.finished_at
          FROM common.dispatches d
          LEFT JOIN common.outcomes o USING (dispatch_id)
         WHERE d.problem_id = %s
           AND d.graph_id IN (
               SELECT graph_id FROM common.problem_graphs WHERE run_id = %s
           )
         ORDER BY d.dispatched_at, d.backend_name
        """,
        (problem_id, str(run_id)),
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No race data for run {run_id} problem {problem_id}",
        )
    for r in rows:
        r["dispatch_id"] = str(r["dispatch_id"])
        if r.get("quality") is not None:
            r["quality"] = float(r["quality"])
    return {"run_id": str(run_id), "problem_id": problem_id, "participants": rows}


@app.get("/api/qec/circuit-svg")
def qec_circuit_svg(
    distance: int = Query(5, ge=3, le=11),
    rounds: int = Query(1, ge=1, le=5),
    basis: str = Query("X", regex="^[XZxz]$"),
) -> Any:
    """Serve a Stim-rendered SVG of a rotated surface-code memory circuit.

    Phase-0 smoke #7 verified this works:
        stim.Circuit.generated('surface_code:rotated_memory_x', ...).diagram()

    Default is a small d=3 single-round circuit so the QEC Lab thumbnail is
    readable. Distance 5 with 5 rounds is intelligible at full panel width.
    """
    from fastapi.responses import Response
    try:
        import stim
    except ImportError:
        raise HTTPException(503, "stim not installed")

    basis_l = basis.lower()
    code_kind = f"surface_code:rotated_memory_{basis_l}"
    try:
        circ = stim.Circuit.generated(
            code_kind,
            distance=distance,
            rounds=rounds,
            after_clifford_depolarization=0.001,
            after_reset_flip_probability=0.001,
            before_measure_flip_probability=0.001,
        )
        # `timeline-svg` lays the circuit out horizontally; "detector-slice-svg"
        # would show stabilizer geometry. Default is timeline.
        diagram = circ.diagram("timeline-svg")
        svg = str(diagram)
    except Exception as e:
        raise HTTPException(500, f"stim render failed: {e}")

    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/qec/ler-curve")
def qec_ler_curve(
    distance: int | None = Query(None, description="Filter by surface code distance"),
    rounds: int | None = Query(None, description="Filter by n_rounds"),
    basis: str | None = Query(None, description="Filter by measurement basis (X or Z)"),
) -> dict[str, Any]:
    """LER curve data: noise_rate -> LER per backend, across all historical QEC runs.

    Returns rows shaped for a Recharts LineChart with three series
    (pymatching, ising_speed, ising_accuracy). For each (noise_rate, backend)
    we report the most recent successful run's LER + shot count + run_id, so
    the dashboard can deep-link back to the source race.
    """
    where = ["pg.problem_class = 'qec_syndrome'", "o.metric_payload ? 'ler'"]
    params: list[Any] = []
    if distance is not None:
        where.append("(pg.params->>'distance')::int = %s")
        params.append(distance)
    if rounds is not None:
        where.append("(pg.params->>'rounds')::int = %s")
        params.append(rounds)
    if basis is not None:
        where.append("upper(coalesce(pg.params->>'basis', 'X')) = %s")
        params.append(basis.upper())

    sql = f"""
        WITH ranked AS (
          SELECT
            r.run_id,
            (pg.params->>'distance')::int   AS distance,
            (pg.params->>'noise_rate')::float8 AS noise_rate,
            (pg.params->>'shots')::int      AS shots,
            d.backend_name,
            (o.metric_payload->>'ler')::float8        AS ler,
            (o.metric_payload->>'logical_errors')::int AS logical_errors,
            o.wall_time_ms,
            r.started_at,
            ROW_NUMBER() OVER (
              PARTITION BY (pg.params->>'noise_rate'),
                           (pg.params->>'distance'),
                           d.backend_name
              ORDER BY r.started_at DESC
            ) AS rn
          FROM common.runs r
          JOIN common.problem_graphs pg ON pg.run_id = r.run_id
          JOIN common.dispatches d  ON d.graph_id = pg.graph_id
          LEFT JOIN common.outcomes o ON o.dispatch_id = d.dispatch_id
          WHERE {' AND '.join(where)}
            AND r.status = 'succeeded'
        )
        SELECT * FROM ranked WHERE rn = 1 ORDER BY noise_rate, backend_name;
    """
    rows = fetch_all(sql, tuple(params) if params else None)
    for r in rows:
        r["run_id"] = str(r["run_id"])

    # Pivot for Recharts: one row per noise_rate, one column per backend.
    by_p: dict[float, dict[str, Any]] = {}
    backends_seen: set[str] = set()
    for r in rows:
        p = r["noise_rate"]
        if p is None:
            continue
        bucket = by_p.setdefault(p, {"noise_rate": p})
        backends_seen.add(r["backend_name"])
        bucket[r["backend_name"]] = r["ler"]
        bucket[f"{r['backend_name']}_run_id"] = r["run_id"]
        bucket[f"{r['backend_name']}_shots"] = r["shots"]
        bucket[f"{r['backend_name']}_logical_errors"] = r["logical_errors"]
        bucket[f"{r['backend_name']}_wall_time_ms"] = r["wall_time_ms"]

    series = sorted(backends_seen)
    points = sorted(by_p.values(), key=lambda b: b["noise_rate"])

    return {
        "filter": {"distance": distance, "rounds": rounds, "basis": basis},
        "series": series,
        "points": points,
        "raw": rows,
    }


@app.get("/api/backends")
def list_backends() -> dict[str, Any]:
    """List the registered backends from the YAML registry (not Postgres)."""
    from orchestrator.pipeline.dispatcher import get_backend_registry

    registry = get_backend_registry()
    return {
        "count": len(registry),
        "backends": [
            {
                "name": b.name,
                "class": b.backend_class.value,
                "applicable_problem_classes": [c.value for c in b.applicable_problem_classes],
                "gpu_required": b.gpu_required,
                "footprint_gb": b.footprint_gb,
                "latency_target_ms": b.latency_target_ms,
                "phase": b.phase,
            }
            for b in registry
        ],
    }


# ---------------------------------------------------------------------------
# Static UI serving.
#   Prefer the Next.js production export at web/ui/out/ (built by `npm run
#   build`). When that's absent, fall back to the throwaway web/ui/index.html
#   so a freshly-cloned tree still renders something. When neither exists, /
#   redirects to /api/health.
# ---------------------------------------------------------------------------

if (UI_OUT_DIR / "index.html").exists():
    # Mount the Next.js bundle at root. Static export contains _next/ assets,
    # html=True makes / serve index.html and 404s become 404.html.
    app.mount("/", StaticFiles(directory=UI_OUT_DIR, html=True), name="ui")
elif (UI_LEGACY_DIR / "index.html").exists():
    @app.get("/")
    def root_ui() -> FileResponse:
        return FileResponse(UI_LEGACY_DIR / "index.html")
else:
    @app.get("/")
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/api/health")
