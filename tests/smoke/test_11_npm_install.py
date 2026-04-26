"""Phase-0 viz render 5: `npm install` of the dashboard's visualization deps
completes cleanly.

The full Next.js scaffold lands in Phase 1; here we exercise a minimal
package.json that pins the load-bearing viz libraries from plan §8 — React
Flow, Recharts, deck.gl, Plotly, and react-three-fiber + drei. If any of
these resolve poorly (peer-dep mismatch, removed package, network) we want
to know during Phase 0 rather than discovering it during the demo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parents[2] / "web" / "ui"

REQUIRED_DEPS = {
    "@xyflow/react",
    "@react-three/fiber",
    "@react-three/drei",
    "deck.gl",
    "plotly.js-basic-dist",
    "recharts",
}


@pytest.mark.viz
def test_npm_install_dashboard_viz_deps(write_artifact):
    if shutil.which("npm") is None:
        pytest.skip("npm not on PATH")
    pkg_json = UI_DIR / "package.json"
    if not pkg_json.exists():
        pytest.skip(f"{pkg_json} missing")

    declared = set(json.loads(pkg_json.read_text()).get("dependencies", {}).keys())
    missing_decls = REQUIRED_DEPS - declared
    assert not missing_decls, f"package.json missing required deps: {missing_decls}"

    proc = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
        cwd=UI_DIR, capture_output=True, text=True, timeout=600,
    )
    write_artifact("11_npm_install.stdout.txt", proc.stdout)
    write_artifact("11_npm_install.stderr.txt", proc.stderr)
    assert proc.returncode == 0, f"npm install failed:\n{proc.stderr[-2000:]}"

    nm = UI_DIR / "node_modules"
    installed = {p.name for p in nm.iterdir() if p.is_dir() and not p.name.startswith(".")}
    scoped = {f"{p.name}/{c.name}" for p in nm.iterdir() if p.is_dir() and p.name.startswith("@")
              for c in p.iterdir() if c.is_dir()}
    installed |= scoped

    missing = REQUIRED_DEPS - installed
    assert not missing, f"npm install did not produce: {missing}"

    write_artifact("11_npm_install.json", {
        "installed_packages_count": len(installed),
        "required_present": sorted(REQUIRED_DEPS),
    })
