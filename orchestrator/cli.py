"""Command-line entry points for the orchestrator.

Three console scripts declared in pyproject.toml:

  qao         -> orchestrator.cli:main    (primary; subcommands `run`, `ping`, `info`)
  qao-replay  -> orchestrator.cli:replay  (replay a recorded run from Postgres — Phase 2)
  qao-bench   -> orchestrator.cli:bench   (repeated runs for benchmarking)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="qao",
    help="quantum-ai-orchestrator: NL ask → pipeline → races → answer.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Quiet noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def _load_dotenv(path: Path | None = None) -> int:
    """Tiny dotenv loader. Reads KEY=VAL lines from .env and sets os.environ."""
    if path is None:
        # Walk up from CWD looking for .env
        p = Path.cwd()
        for _ in range(5):
            cand = p / ".env"
            if cand.exists():
                path = cand
                break
            if p.parent == p:
                break
            p = p.parent
    if path is None or not path.exists():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


# Load .env on import so all subcommands see Postgres creds without manual sourcing.
_load_dotenv()


def _print_run_summary(run, format_: str = "human") -> None:
    """Pretty-print a Run object."""
    if format_ == "json":
        # Custom JSON with non-stringable bits sanitized
        out = {
            "run_id": str(run.run_id),
            "ask": run.ask_text,
            "skill": run.skill,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "wall_time_ms": (
                int((run.finished_at - run.started_at).total_seconds() * 1000)
                if run.started_at and run.finished_at else None
            ),
            "outcomes": [
                {
                    "problem_id": o.problem.problem_id,
                    "winning_backend": o.backend_choice.backend.name,
                    "gpu_lane": o.backend_choice.gpu_lane,
                    "quality": o.grade.quality,
                    "wall_time_ms": o.solution.wall_time_ms,
                    "metrics": {
                        k: v for k, v in o.grade.metric_payload.items()
                        if isinstance(v, (int, float, str, bool, type(None)))
                    },
                }
                for o in run.outcomes
            ],
            "final_answer": _json_safe(run.final_answer),
            "error": run.error,
        }
        typer.echo(json.dumps(out, indent=2, default=str))
        return

    # Human-readable
    typer.echo(f"\n  run_id    {run.run_id}")
    typer.echo(f"  ask       {run.ask_text}")
    typer.echo(f"  skill     {run.skill}")
    typer.echo(f"  status    {run.status.value if hasattr(run.status, 'value') else run.status}")
    if run.started_at and run.finished_at:
        wall = (run.finished_at - run.started_at).total_seconds() * 1000
        typer.echo(f"  wall_time {wall:.0f}ms")
    if run.error:
        typer.echo(f"  error     {run.error}")
    typer.echo("")
    typer.echo("  Outcomes:")
    for o in run.outcomes:
        line = (
            f"    [{o.problem.problem_id}] {o.backend_choice.backend.name}"
            f" (gpu_lane={o.backend_choice.gpu_lane}) quality={o.grade.quality:.4f}"
            f" wall={o.solution.wall_time_ms}ms"
        )
        # Add a key metric if available
        m = o.grade.metric_payload
        if "ler" in m:
            line += f" LER={m['ler']:.4f}"
        elif "objective" in m:
            line += f" obj={m['objective']}"
        typer.echo(line)
    if run.final_answer:
        typer.echo("")
        typer.echo(f"  Final answer:")
        meta = run.final_answer.get("metadata", {})
        for k, v in meta.items():
            typer.echo(f"    {k:14s} {v}")


def _json_safe(obj):
    """Best-effort recursive sanitize for JSON output."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


@app.command("run")
def run_cmd(
    ask: Annotated[str, typer.Argument(help="Natural-language ask, e.g. 'decode a distance-5 surface code at p=0.005'")],
    top_k: Annotated[int, typer.Option(help="Max backends to race per problem")] = 3,
    phase: Annotated[int, typer.Option(help="Max backend phase to include (1=Phase-1)")] = 1,
    output: Annotated[str, typer.Option("--output", "-o", help="Output format: human or json")] = "human",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose logging")] = False,
) -> None:
    """Run the full pipeline against an ask and print the result."""
    _setup_logging(verbose)
    from orchestrator.pipeline.runner import run_pipeline_sync

    if output not in ("human", "json"):
        typer.echo(f"--output must be 'human' or 'json', got {output!r}", err=True)
        raise typer.Exit(2)

    typer.echo(f"  ask: {ask}", err=True)
    run = run_pipeline_sync(ask, top_k=top_k, phase=phase)
    _print_run_summary(run, format_=output)
    if run.status.value == "failed" if hasattr(run.status, "value") else str(run.status) == "failed":
        raise typer.Exit(1)


@app.command("ping")
def ping_cmd(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Health-check the dependencies the pipeline needs."""
    _setup_logging(verbose)
    typer.echo("Checking orchestrator dependencies...\n")
    ok = True

    # Ollama
    try:
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        models = client.models.list()
        names = [m.id for m in models.data][:5]
        typer.echo(f"  [ok]    Ollama: {len(models.data)} models available; sample: {names}")
    except Exception as e:
        typer.echo(f"  [FAIL]  Ollama: {e}")
        ok = False

    # GPUs
    try:
        import torch
        if torch.cuda.is_available():
            n = torch.cuda.device_count()
            names = [torch.cuda.get_device_name(i) for i in range(n)]
            typer.echo(f"  [ok]    GPUs: {n} visible, {names}")
        else:
            typer.echo(f"  [WARN]  GPUs: torch CUDA not available")
            ok = False
    except Exception as e:
        typer.echo(f"  [FAIL]  GPU check: {e}")
        ok = False

    # CUDA-Q container
    if shutil.which("docker") is None:
        typer.echo(f"  [WARN]  Docker not on PATH (cudaq_qaoa backend will fail)")
    else:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", "nvcr.io/nvidia/quantum/cuda-quantum:cu12-0.9.1"],
                capture_output=True, timeout=5, check=False,
            )
            if result.returncode == 0:
                typer.echo(f"  [ok]    cuda-quantum container image present")
            else:
                typer.echo(f"  [WARN]  cuda-quantum image not pulled (cudaq_qaoa backend will fail)")
        except subprocess.TimeoutExpired:
            typer.echo(f"  [WARN]  Docker daemon not responding")
            ok = False

    # Ising weights
    fast = Path("/data/models/nvidia-ising/fast")
    accurate = Path("/data/models/nvidia-ising/accurate")
    code_dir = Path("/data/models/nvidia-ising/Ising-Decoding/code")
    for label, p in [("Ising fast weights", fast), ("Ising accurate weights", accurate), ("Ising code dir", code_dir)]:
        if p.exists():
            typer.echo(f"  [ok]    {label}: {p}")
        else:
            typer.echo(f"  [FAIL]  {label}: missing at {p}")
            ok = False

    # Postgres
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    pg_db = os.environ.get("POSTGRES_DB", "quantum_ai_orchestrator")
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_pwd = os.environ.get("POSTGRES_PASSWORD")
    if pg_pwd is None:
        typer.echo(f"  [WARN]  Postgres: POSTGRES_PASSWORD not set in env (storage layer will fail)")
    else:
        try:
            import psycopg
            with psycopg.connect(
                host=pg_host, port=pg_port, dbname=pg_db, user=pg_user, password=pg_pwd,
                connect_timeout=3,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_database(), current_user")
                    db, user = cur.fetchone()
                    typer.echo(f"  [ok]    Postgres: connected as {user} to {db} at {pg_host}:{pg_port}")
        except Exception as e:
            typer.echo(f"  [WARN]  Postgres: {e}")

    typer.echo("")
    if ok:
        typer.echo("All required dependencies present.")
    else:
        typer.echo("One or more required dependencies missing — see above.")
        raise typer.Exit(1)


@app.command("info")
def info_cmd() -> None:
    """List registered backends and skills."""
    from orchestrator.pipeline.dispatcher import get_backend_registry
    from orchestrator.pipeline.formulator import SKILL_FORMULATORS
    from orchestrator.pipeline.evaluator import SKILL_EVALUATORS

    typer.echo("\nSkills (formulators):")
    for cls, mod in SKILL_FORMULATORS.items():
        typer.echo(f"  {cls.value:20s} -> {mod}")

    typer.echo("\nSkills (evaluators):")
    for cls, mod in SKILL_EVALUATORS.items():
        typer.echo(f"  {cls.value:20s} -> {mod}")

    typer.echo("\nBackends:")
    typer.echo(f"  {'name':<22}{'class':<28}{'gpu':<6}{'phase':<6}{'problem_classes'}")
    for b in get_backend_registry():
        classes = ",".join(c.value for c in b.applicable_problem_classes)
        typer.echo(
            f"  {b.name:<22}{b.backend_class.value:<28}"
            f"{('yes' if b.gpu_required else 'no'):<6}{b.phase:<6}{classes}"
        )
    typer.echo("")


@app.command("serve")
def serve_cmd(
    host: Annotated[str, typer.Option(help="Bind address. Use 0.0.0.0 for LAN access.")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="HTTP port")] = 8765,
    reload: Annotated[bool, typer.Option(help="Auto-reload on code changes (dev only)")] = False,
) -> None:
    """Start the FastAPI replay server (API + dashboard).

    Default binds to 0.0.0.0:8765 so the dashboard is reachable from other LAN
    hosts. The /api/* endpoints back the dashboard's run list, bake-off, LER
    curve, Stim circuit SVG, and bipartite assignment panels. The Next.js
    static build at web/ui/out/ is mounted at /.

    For UI hot-reload during development, run `npm run dev` in web/ui/ on a
    separate port (3045 by default); the dev server proxies /api/* to this one.
    """
    import uvicorn
    typer.echo(f"  qao replay server on http://{host}:{port}/")
    typer.echo(f"  api: http://{host}:{port}/api/health")
    if host == "0.0.0.0":
        typer.echo(f"  reachable from any LAN host on this subnet")
    uvicorn.run(
        "web.api.serve_replay:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def main() -> None:
    """Entry point declared in pyproject.toml as `qao`."""
    app()


# --- separate console scripts ---


_bench_app = typer.Typer(name="qao-bench", add_completion=False, no_args_is_help=True)


@_bench_app.command()
def _bench_run(
    ask: Annotated[str, typer.Argument()],
    runs: Annotated[int, typer.Option(help="Number of pipeline runs")] = 10,
    top_k: Annotated[int, typer.Option()] = 3,
    phase: Annotated[int, typer.Option()] = 1,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run an ask N times and print latency / quality stats."""
    _setup_logging(verbose)
    from orchestrator.pipeline.runner import run_pipeline_sync

    typer.echo(f"  ask: {ask}")
    typer.echo(f"  runs: {runs}, top_k: {top_k}, phase: {phase}")
    times: list[int] = []
    qualities: list[float] = []
    for i in range(runs):
        start = time.perf_counter()
        run = run_pipeline_sync(ask, top_k=top_k, phase=phase)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        times.append(elapsed_ms)
        if run.outcomes:
            qualities.append(run.outcomes[0].grade.quality)
        winner = run.outcomes[0].backend_choice.backend.name if run.outcomes else "?"
        typer.echo(f"  run {i+1}/{runs}: winner={winner} wall={elapsed_ms}ms")

    if times:
        typer.echo("")
        typer.echo(f"  wall_time_ms: min={min(times)} median={sorted(times)[len(times)//2]} max={max(times)} mean={sum(times)/len(times):.1f}")
    if qualities:
        typer.echo(f"  quality:      min={min(qualities):.4f} mean={sum(qualities)/len(qualities):.4f} max={max(qualities):.4f}")


def bench() -> None:
    """Entry point declared in pyproject.toml as `qao-bench`."""
    _bench_app()


_replay_app = typer.Typer(name="qao-replay", add_completion=False, no_args_is_help=True)


@_replay_app.command()
def _replay_run(
    run_id: Annotated[str, typer.Argument(help="UUID of a previous run")],
) -> None:
    """Replay a previously recorded run from Postgres provenance.

    Phase 2: requires the storage layer (orchestrator/storage/) which is not yet wired.
    """
    _ = run_id
    typer.echo(
        "qao-replay needs the Postgres storage layer (orchestrator/storage/), "
        "which is not yet implemented. See memory/phase1-pipeline-state.md for the plan.",
        err=True,
    )
    raise typer.Exit(2)


def replay() -> None:
    """Entry point declared in pyproject.toml as `qao-replay`."""
    _replay_app()


if __name__ == "__main__":
    main()
