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
        Rotated surface-code memory circuit, T rounds of stabilizer measurement followed by
        data-qubit measurement. Generated server-side via{" "}
        <code>stim.Circuit.generated(&quot;surface_code:rotated_memory_{basis.toLowerCase()}&quot;, ...)</code>.
      </div>
    </div>
  );
}
