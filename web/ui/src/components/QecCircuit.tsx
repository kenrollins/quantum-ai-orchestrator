"use client";

import styles from "./QecCircuit.module.css";

interface Props {
  distance: number;
  rounds?: number;
  basis?: string;
}

/**
 * Thin SVG embed of `stim.Circuit.diagram("timeline-svg")`. The endpoint
 * (`/api/qec/circuit-svg`) renders server-side; we use <object> rather than
 * <img> so the SVG keeps its own scrolling viewport for wide circuits.
 *
 * The same circuit family is what `MemoryCircuit` and PyMatching consume in
 * the actual race; this is a faithful illustration of the workload, not a
 * stylized cartoon.
 */
export default function QecCircuit({ distance, rounds = 1, basis = "X" }: Props) {
  const params = new URLSearchParams({
    distance: String(distance),
    rounds: String(rounds),
    basis,
  });
  const src = `/api/qec/circuit-svg?${params}`;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>QEC Lab · Stim circuit (timeline)</h2>
        <span className={styles.subtitle}>
          d={distance} · T={rounds} · basis={basis}
        </span>
      </div>
      <div className={styles.svgWrap}>
        <object type="image/svg+xml" data={src} aria-label="surface code circuit">
          stim circuit
        </object>
      </div>
      <div className={styles.note}>
        <strong>What this shows.</strong> The actual quantum circuit being decoded — not a
        cartoon, not a paper figure. Each horizontal line is one qubit; gates flow left to
        right in time. The dark blocks are <em>stabilizer measurements</em>: they detect
        errors without disturbing the encoded data. A distance-d code uses d² data qubits
        arranged in a square lattice (so d=5 means 25 data qubits plus their stabilizers).
        T rounds of measurement give the decoder a 3D spacetime view of where errors happened.
        Stim generates this from the same circuit the backends actually decoded, so what you
        see is what they got.
      </div>
    </div>
  );
}
