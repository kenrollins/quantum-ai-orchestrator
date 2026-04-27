"use client";

/**
 * Interactive rotated surface-code widget.
 *
 * Click a data qubit to toggle an error on it; watch adjacent stabilizers
 * light up to form the syndrome. The takeaway in 15 seconds of clicking:
 * "syndromes only appear at the boundaries of error chains."
 *
 * Geometry, syndrome computation, and error-toggle algebra are reimplemented
 * here for SVG rendering, but the algorithm follows PanQEC's MIT-licensed
 * `topologicalCode.js` (https://github.com/panqec/panqec, BSD/MIT). The
 * full PanQEC GUI is THREE.js + Flask; we use SVG + hand-rolled bitmatmul
 * because a dashboard tile doesn't need a 3D camera.
 *
 * Distance-d rotated surface code conventions:
 *   - d^2 data qubits at half-integer positions (i + 0.5, j + 0.5), 0 <= i,j < d
 *   - X stabilizers (red squares) on north/south face-cells of the data lattice
 *   - Z stabilizers (blue squares) on east/west face-cells
 *   - Boundaries: north/south are X-rough (X stabilizers stick out top/bottom);
 *     east/west are Z-rough (Z stabilizers stick out left/right). This matches
 *     the rotated_memory_x convention used by Stim.
 *
 * Each stabilizer's parity check (a row of H) is the XOR of the X errors (for
 * Z stabs) or Z errors (for X stabs) on its adjacent data qubits.
 */

import { useMemo, useState } from "react";
import styles from "./SurfaceCodeWidget.module.css";

interface Props {
  distance?: number;
}

interface DataQubit {
  index: number;
  x: number;
  y: number;
}

interface Stabilizer {
  index: number;
  type: "X" | "Z";
  x: number;
  y: number;
  // Indices into DataQubit array of qubits this stabilizer measures
  neighbors: number[];
}

interface Lattice {
  data: DataQubit[];
  stabs: Stabilizer[];
  // Bounding box for the SVG viewBox
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

/** Build a distance-d rotated surface code lattice. */
function buildLattice(d: number): Lattice {
  const data: DataQubit[] = [];
  const stabs: Stabilizer[] = [];

  // Data qubits in a d×d grid, integer coordinates (i, j) with 0 <= i,j < d.
  // We render at (i + 0.5, j + 0.5) so stabilizers sit at integer corners.
  for (let i = 0; i < d; i++) {
    for (let j = 0; j < d; j++) {
      data.push({ index: i * d + j, x: i + 0.5, y: j + 0.5 });
    }
  }

  // Stabilizers at integer (i, j) corners between data qubits.
  // i ranges [0, d], j ranges [0, d]. Each stab connects to up to 4 data qubits
  // at (i-1, j-1), (i, j-1), (i-1, j), (i, j) — clamped to lattice bounds.
  // Type alternates by (i+j) parity; boundary stabs only exist on the rough
  // edges (top/bottom for X, left/right for Z).
  let stabIdx = 0;
  for (let i = 0; i <= d; i++) {
    for (let j = 0; j <= d; j++) {
      const isX = (i + j) % 2 === 0;
      const isInterior = i > 0 && i < d && j > 0 && j < d;
      // Boundaries: X-stabs only on top (j=0) and bottom (j=d) rough edges
      //             Z-stabs only on left (i=0) and right (i=d) rough edges
      const onXRough = isX && (j === 0 || j === d) && i > 0 && i < d;
      const onZRough = !isX && (i === 0 || i === d) && j > 0 && j < d;
      if (!isInterior && !onXRough && !onZRough) continue;

      const neighbors: number[] = [];
      for (const [di, dj] of [[-1, -1], [0, -1], [-1, 0], [0, 0]] as const) {
        const ii = i + di;
        const jj = j + dj;
        if (ii >= 0 && ii < d && jj >= 0 && jj < d) {
          neighbors.push(ii * d + jj);
        }
      }
      stabs.push({
        index: stabIdx++,
        type: isX ? "X" : "Z",
        x: i,
        y: j,
        neighbors,
      });
    }
  }

  // Bounding box with a little padding
  const pad = 0.5;
  return {
    data,
    stabs,
    minX: -pad,
    maxX: d + pad,
    minY: -pad,
    maxY: d + pad,
  };
}

type ErrorMap = Record<number, "I" | "X" | "Z" | "Y">;

/** Toggle a Pauli on a data qubit (X xor X = I, X compose Z = Y, etc.) */
function toggleError(current: "I" | "X" | "Z" | "Y", pauli: "X" | "Z"): "I" | "X" | "Z" | "Y" {
  // X ^ X = I; Z ^ Z = I; X ^ Z = Y; Y ^ X = Z; Y ^ Z = X.
  const tableX: Record<string, "I" | "X" | "Z" | "Y"> = { I: "X", X: "I", Z: "Y", Y: "Z" };
  const tableZ: Record<string, "I" | "X" | "Z" | "Y"> = { I: "Z", X: "Y", Z: "I", Y: "X" };
  return pauli === "X" ? tableX[current] : tableZ[current];
}

/**
 * Compute syndrome: an X-stabilizer fires if any neighboring data qubit has
 * a Z error (or Y, which contains Z); a Z-stabilizer fires for X errors (or Y).
 */
function computeSyndrome(lattice: Lattice, errors: ErrorMap): Set<number> {
  const lit = new Set<number>();
  for (const s of lattice.stabs) {
    let parity = 0;
    for (const ni of s.neighbors) {
      const err = errors[ni] || "I";
      if (s.type === "X" && (err === "Z" || err === "Y")) parity ^= 1;
      if (s.type === "Z" && (err === "X" || err === "Y")) parity ^= 1;
    }
    if (parity) lit.add(s.index);
  }
  return lit;
}

const COLORS = {
  data: "#d0d6e2",
  dataX: "#cf222e",
  dataZ: "#4493f8",
  dataY: "#a371f7",
  stabXOff: "#3a1818",
  stabXOn: "#cf222e",
  stabZOff: "#152a3d",
  stabZOn: "#4493f8",
  edge: "#2a313c",
};

export default function SurfaceCodeWidget({ distance = 5 }: Props) {
  const lattice = useMemo(() => buildLattice(distance), [distance]);
  const [errors, setErrors] = useState<ErrorMap>({});
  const [mode, setMode] = useState<"X" | "Z">("X");

  const lit = useMemo(() => computeSyndrome(lattice, errors), [lattice, errors]);
  const dataErrorCount = Object.values(errors).filter((p) => p !== "I").length;

  const onClickData = (idx: number) => {
    setErrors((prev) => {
      const cur = prev[idx] || "I";
      const next = toggleError(cur, mode);
      const out = { ...prev };
      if (next === "I") delete out[idx];
      else out[idx] = next;
      return out;
    });
  };

  const reset = () => setErrors({});

  // Add a small lattice grid (helpful visual structure)
  const gridLines: { x1: number; y1: number; x2: number; y2: number }[] = [];
  for (let i = 0; i < distance; i++) {
    for (let j = 0; j < distance; j++) {
      const x = i + 0.5;
      const y = j + 0.5;
      if (i + 1 < distance) gridLines.push({ x1: x, y1: y, x2: x + 1, y2: y });
      if (j + 1 < distance) gridLines.push({ x1: x, y1: y, x2: x, y2: y + 1 });
    }
  }

  const { minX, maxX, minY, maxY } = lattice;
  const vbW = maxX - minX;
  const vbH = maxY - minY;

  return (
    <div className={styles.widget}>
      <div className={styles.toolbar}>
        <span className={styles.label}>Click a data qubit to toggle an</span>
        <button
          className={mode === "X" ? styles.active : ""}
          onClick={() => setMode("X")}
          aria-pressed={mode === "X"}
        >
          X error
        </button>
        <button
          className={mode === "Z" ? styles.active : ""}
          onClick={() => setMode("Z")}
          aria-pressed={mode === "Z"}
        >
          Z error
        </button>
        <button onClick={reset}>Clear</button>
        <span className={styles.right}>
          d={distance} · {dataErrorCount} error{dataErrorCount === 1 ? "" : "s"} ·{" "}
          {lit.size} syndrome{lit.size === 1 ? "" : "s"} lit
        </span>
      </div>

      <svg
        className={styles.lattice}
        viewBox={`${minX} ${minY} ${vbW} ${vbH}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Interactive distance-d rotated surface code lattice"
      >
        {/* Grid lines connecting data qubits — purely visual scaffold */}
        {gridLines.map((l, i) => (
          <line
            key={`g${i}`}
            x1={l.x1}
            y1={l.y1}
            x2={l.x2}
            y2={l.y2}
            stroke={COLORS.edge}
            strokeWidth={0.02}
          />
        ))}

        {/* Stabilizers — squares at lattice corners. Drawn before data so data
            circles paint on top. */}
        {lattice.stabs.map((s) => {
          const isLit = lit.has(s.index);
          const fill =
            s.type === "X"
              ? isLit
                ? COLORS.stabXOn
                : COLORS.stabXOff
              : isLit
                ? COLORS.stabZOn
                : COLORS.stabZOff;
          return (
            <rect
              key={`s${s.index}`}
              x={s.x - 0.18}
              y={s.y - 0.18}
              width={0.36}
              height={0.36}
              fill={fill}
              stroke={isLit ? "#fff" : COLORS.edge}
              strokeWidth={isLit ? 0.04 : 0.02}
              opacity={isLit ? 1 : 0.85}
              rx={0.04}
              ry={0.04}
            />
          );
        })}

        {/* Data qubits — circles, click to toggle error */}
        {lattice.data.map((q) => {
          const err = errors[q.index] || "I";
          const fill =
            err === "I" ? COLORS.data
              : err === "X" ? COLORS.dataX
                : err === "Z" ? COLORS.dataZ
                  : COLORS.dataY;
          return (
            <circle
              key={`d${q.index}`}
              className={styles.dataQubit}
              cx={q.x}
              cy={q.y}
              r={0.18}
              fill={fill}
              stroke={err === "I" ? COLORS.edge : "#fff"}
              strokeWidth={err === "I" ? 0.02 : 0.05}
              onClick={() => onClickData(q.index)}
            >
              <title>
                Data qubit ({Math.floor(q.x)}, {Math.floor(q.y)}) — error: {err}
              </title>
            </circle>
          );
        })}
      </svg>

      <div className={styles.legend}>
        <span>
          <span className={styles.swatch} style={{ background: COLORS.data }} />
          data qubit (no error)
        </span>
        <span>
          <span className={styles.swatch} style={{ background: COLORS.dataX }} />
          X error
        </span>
        <span>
          <span className={styles.swatch} style={{ background: COLORS.dataZ }} />
          Z error
        </span>
        <span>
          <span className={styles.swatch} style={{ background: COLORS.dataY }} />
          Y = X &amp; Z
        </span>
        <span>
          <span className={styles.swatchSquare} style={{ background: COLORS.stabXOn }} />
          X stab fired
        </span>
        <span>
          <span className={styles.swatchSquare} style={{ background: COLORS.stabZOn }} />
          Z stab fired
        </span>
      </div>

      <div className={styles.note}>
        <strong>What to look for.</strong> An X error on a data qubit fires the{" "}
        Z stabilizers (blue squares) at its corners. A Z error fires the X
        stabilizers (red squares). Try placing several errors in a row — notice
        that the syndrome only lights up at the <em>endpoints</em> of the chain;
        the interior stabilizers cancel because each one sees an even number of
        errors. That&apos;s the single most important property a decoder
        exploits: <em>find the minimum-weight set of error chains that explain
        the lit syndromes</em>. PyMatching does this exactly via min-weight
        perfect matching on a graph of syndrome vertices.
      </div>

      <div className={styles.attribution}>
        Lattice algebra adapted from{" "}
        <a href="https://github.com/panqec/panqec" target="_blank" rel="noopener noreferrer">
          PanQEC
        </a>{" "}
        (MIT, Pesah &amp; Huang). Reimplemented in SVG + TypeScript for this dashboard.
      </div>
    </div>
  );
}
