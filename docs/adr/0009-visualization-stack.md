# ADR-0009: Visualization stack for dashboard panels

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

The dashboard (plan §8) requires multiple visualization types:

1. **Stim circuit diagrams** — surface-code circuits with detectors
2. **PyMatching matching graphs** — MWPM decoder structure
3. **D-Wave QUBO inspector** — problem structure for annealing backends
4. **QuTiP Bloch spheres** — single-qubit state visualization
5. **3D lattice views** — surface-code patches in 3D
6. **Charts** — LER curves, backend timing comparisons
7. **Flow diagrams** — problem-graph DAG visualization

Each requires specific libraries. The question: which libraries, and how do they integrate with a React dashboard?

## Decision

The visualization stack is:

| Panel | Backend (Python) | Frontend (JS) |
|-------|------------------|---------------|
| Stim circuits | `stim.Circuit.diagram("svg")` | inline SVG |
| PyMatching graphs | `pymatching.draw()` → PNG | `<img>` |
| D-Wave QUBO | `dwave.inspector` (offline mode) | `<img>` or iframe |
| Bloch spheres | `qutip.Bloch().save()` → PNG | `<img>` |
| 3D lattice | — | `@react-three/fiber` + `drei` |
| Charts | — | `recharts` + `plotly.js-basic-dist` |
| Flow/DAG | — | `@xyflow/react` (ReactFlow) |
| Geospatial (routing) | — | `deck.gl` |

All Python visualizations export static assets (SVG/PNG) that the dashboard fetches. Interactive 3D and charts are pure frontend.

Smoke tests validate each backend path:
- Test 07: Stim SVG export
- Test 08: PyMatching PNG export
- Test 09: D-Wave inspector QUBO encoding
- Test 10: QuTiP Bloch PNG export
- Test 11: npm install of all frontend deps

## Alternatives considered

- **Jupyter widgets (ipywidgets, plotly-dash)** — Great for notebooks, but we need a standalone React dashboard for demos. Widget embedding adds complexity.

- **Matplotlib for everything** — Would work but produces less polished output than specialized libraries. QuTiP's Bloch sphere is matplotlib-based anyway.

- **Three.js raw instead of react-three-fiber** — R3F provides React bindings that match our component model. Raw Three.js would require manual lifecycle management.

- **D3.js instead of Recharts** — D3 is more powerful but requires more code. Recharts covers our chart needs with declarative components.

- **Cytoscape.js instead of ReactFlow** — Cytoscape is more powerful for graph analysis but heavier. ReactFlow's DAG layout is sufficient for problem graphs.

## Consequences

### Positive

- Each library is best-in-class for its domain.
- Python backends are stateless — generate asset, return path.
- Frontend deps install in <30 s via npm (test 11: 29 s).
- All libraries are MIT/Apache/BSD licensed.
- The stack supports offline/air-gapped operation.

### Negative / accepted trade-offs

- Multiple libraries increase bundle size. We use `plotly.js-basic-dist` (smaller) instead of full Plotly.
- D-Wave inspector's offline mode produces static HTML, not live interaction. Acceptable for demos.
- 3D lattice rendering on CPU (no WebGPU) may be slow for d>17. Phase-1 consideration.

## References

- ReactFlow: https://reactflow.dev/
- react-three-fiber: https://docs.pmnd.rs/react-three-fiber
- deck.gl: https://deck.gl/
- Recharts: https://recharts.org/
- QuTiP Bloch: https://qutip.org/docs/latest/guide/guide-bloch.html
- D-Wave inspector: https://docs.ocean.dwavesys.com/en/stable/docs_inspector/
