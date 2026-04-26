# ADR-0008: Circuit visualization via Stim SVG export, not standalone Crumble

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** rollik

## Context

Crumble is a browser-based circuit editor/visualizer for Stim circuits. The original plan considered two approaches:

1. **Embed Crumble as an iframe** pointing to a locally-served instance.
2. **Use Stim's built-in `circuit.diagram("svg")` method** to generate static SVGs.

The question: do we need interactive editing, or is static visualization sufficient for Phase-0?

## Decision

Use **Stim's native SVG export** for circuit visualization. No standalone Crumble instance.

```python
import stim
circuit = stim.Circuit(...)
svg_str = circuit.diagram("svg")
```

The dashboard renders the SVG inline. Smoke test 07 validates this path.

## Alternatives considered

- **Standalone Crumble server on a separate port** — Crumble is a client-side JS app that can load circuits. Running it locally would require:
  - Cloning the Stim repo and serving `glue/crumble/`
  - Handling CORS for the iframe embed
  - Passing circuit data via URL params or postMessage

  This adds operational complexity (another service to manage) for interactivity we don't need in Phase-0.

- **Quirk (Craig Gidney's other circuit editor)** — Quirk is for general quantum circuits, not Stim's detector-based error correction circuits. Wrong tool.

- **Qiskit/Cirq circuit drawers** — Neither understands Stim's detector/observable annotations. We'd lose the error-correction-specific visualization.

## Consequences

### Positive

- Zero additional services — Stim is already a pip dependency.
- SVGs are self-contained; no iframe security issues.
- The SVG includes detector annotations and measurement records — exactly what QEC debugging needs.
- Works offline and in air-gapped Federal environments.

### Negative / accepted trade-offs

- No interactive editing. Users cannot drag gates or modify circuits in the browser.
- Large circuits (d>13, many rounds) produce large SVGs. May need viewport clipping for dashboard display.
- If we later want interactivity, we'll need to add Crumble as a separate service.

## References

- Stim diagram documentation: https://github.com/quantumlib/Stim/blob/main/doc/python_api_reference_vDev.md#stim.Circuit.diagram
- Crumble source: https://github.com/quantumlib/Stim/tree/main/glue/crumble
