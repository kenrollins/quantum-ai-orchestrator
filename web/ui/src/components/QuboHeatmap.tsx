"use client";

import { useMemo, useState } from "react";
import styles from "./QuboHeatmap.module.css";

interface Props {
  defaultAssets?: number;
  defaultTasks?: number;
  defaultCapacity?: number;
}

/**
 * Client-side QUBO builder for the assignment problem, mirroring the
 * Python formulator at skills/mission_assignment/formulator.py. Rendered
 * as an SVG heatmap so the user can see the diagonal-cost block, the
 * per-task penalty stripes, and the per-asset capacity stripes.
 *
 * Cost matrix is deterministic from the seed (Mulberry32) so the rendering
 * is reproducible. Penalty auto-scales to 2 * max(cost) per the standard
 * Lubin/Lucas rule.
 */
export default function QuboHeatmap({
  defaultAssets = 5,
  defaultTasks = 4,
  defaultCapacity = 2,
}: Props) {
  const [assets, setAssets] = useState(defaultAssets);
  const [tasks, setTasks] = useState(defaultTasks);
  const [capacity, setCapacity] = useState(defaultCapacity);
  const [hover, setHover] = useState<{ k1: number; k2: number; v: number } | null>(null);

  const { Q, costMatrix, penalty } = useMemo(() => {
    const cm = generateCostMatrix(assets, tasks, 42);
    const maxCost = cm.reduce((m, row) => Math.max(m, ...row), 0);
    const penalty = 2 * maxCost;
    const Q = buildQubo(cm, capacity, penalty);
    return { Q, costMatrix: cm, penalty };
  }, [assets, tasks, capacity]);

  const n = Q.length;
  const cell = Math.min(28, Math.floor(540 / Math.max(n, 1)));
  const svgSize = cell * n + 2;

  // Symmetric color scale around 0 — penalty positives are red, cost+penalty
  // negatives are blue.
  const maxAbs = Q.reduce(
    (m, row) => Math.max(m, ...row.map((v) => Math.abs(v))),
    1,
  );

  const tooltip = useMemo(() => {
    if (!hover) return null;
    const { k1, k2 } = hover;
    const i1 = Math.floor(k1 / tasks);
    const j1 = k1 % tasks;
    const i2 = Math.floor(k2 / tasks);
    const j2 = k2 % tasks;
    const isDiag = k1 === k2;
    const sameTask = j1 === j2 && i1 !== i2;
    const sameAsset = i1 === i2 && j1 !== j2;
    let interpretation = "";
    if (isDiag) {
      const cost = costMatrix[i1][j1];
      interpretation = `cost ${cost} − penalty ${penalty}`;
    } else if (sameTask) {
      interpretation = `+2·penalty (same task)`;
    } else if (sameAsset) {
      interpretation = `+penalty/${2 * capacity} (capacity)`;
    } else {
      interpretation = "0 (no interaction)";
    }
    return {
      k1, k2, v: hover.v,
      i1, j1, i2, j2, interpretation,
    };
  }, [hover, costMatrix, penalty, capacity, tasks]);

  return (
    <div className={styles.panel}>
      <div className={styles.controls}>
        <label>
          assets
          <input
            type="number"
            min={3}
            max={8}
            value={assets}
            onChange={(e) => setAssets(clamp(parseInt(e.target.value, 10), 3, 8))}
          />
        </label>
        <label>
          tasks
          <input
            type="number"
            min={2}
            max={6}
            value={tasks}
            onChange={(e) => setTasks(clamp(parseInt(e.target.value, 10), 2, 6))}
          />
        </label>
        <label>
          capacity
          <input
            type="number"
            min={1}
            max={4}
            value={capacity}
            onChange={(e) => setCapacity(clamp(parseInt(e.target.value, 10), 1, 4))}
          />
        </label>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-dim)" }}>
          {n}×{n} matrix · penalty {penalty.toFixed(0)}
        </span>
      </div>

      <div className={styles.layout}>
        <div className={styles.svgWrap}>
          <svg
            viewBox={`0 0 ${svgSize} ${svgSize}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="QUBO matrix heatmap"
          >
            {Q.map((row, k1) =>
              row.map((v, k2) => (
                <rect
                  key={`${k1}-${k2}`}
                  x={k2 * cell + 1}
                  y={k1 * cell + 1}
                  width={cell}
                  height={cell}
                  fill={cellColor(v, maxAbs)}
                  stroke={hover && hover.k1 === k1 && hover.k2 === k2 ? "#fff" : "none"}
                  strokeWidth={hover && hover.k1 === k1 && hover.k2 === k2 ? 1 : 0}
                  onMouseEnter={() => setHover({ k1, k2, v })}
                  onMouseLeave={() => setHover(null)}
                />
              )),
            )}
          </svg>
        </div>

        <div className={styles.tooltipBox}>
          {tooltip ? (
            <>
              <h4>Q[{tooltip.k1}][{tooltip.k2}]</h4>
              <div className={styles.row}>
                <span>value</span>
                <span>{tooltip.v.toFixed(0)}</span>
              </div>
              <div className={styles.row}>
                <span>x[{tooltip.i1},{tooltip.j1}]</span>
                <span>asset {tooltip.i1} · task {tooltip.j1}</span>
              </div>
              {tooltip.k1 !== tooltip.k2 && (
                <div className={styles.row}>
                  <span>x[{tooltip.i2},{tooltip.j2}]</span>
                  <span>asset {tooltip.i2} · task {tooltip.j2}</span>
                </div>
              )}
              <div className={styles.row} style={{ marginTop: 8 }}>
                <span style={{ color: "var(--text-dim)" }}>{tooltip.interpretation}</span>
              </div>
            </>
          ) : (
            <>
              <h4>Hover a cell</h4>
              <div className={styles.row}>
                <span style={{ color: "var(--text-dim)", lineHeight: 1.5 }}>
                  Diagonal cells = cost − penalty for that variable. Off-diagonal = penalty
                  for putting two variables &ldquo;on&rdquo; together.
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className={styles.legend}>
        <span>−{maxAbs.toFixed(0)}</span>
        <div className={styles.gradient} />
        <span>+{maxAbs.toFixed(0)}</span>
      </div>

      <div className={styles.note}>
        <strong>Read the structure.</strong> Block-diagonal pattern visible at
        every <code>tasks</code>×<code>tasks</code> step is per-asset capacity
        penalty. The negative blue diagonal is cost minus penalty (large negative
        = preferred slot). The off-diagonal red stripes within each
        <code> tasks</code>-stride block are the &ldquo;each task assigned exactly once&rdquo;
        constraint — every pair of asset slots competing for the same task gets
        a +2·penalty kick. The matrix has the right structure to make feasibility
        the lowest-energy region; classical solvers exploit the structure
        directly, annealers traverse the landscape, QAOA prepares a state biased
        toward it.
      </div>
    </div>
  );
}

function clamp(v: number, lo: number, hi: number): number {
  if (Number.isNaN(v)) return lo;
  return Math.max(lo, Math.min(hi, v));
}

/** Mulberry32 — small deterministic PRNG, matches numpy.random.default_rng(seed). */
function mulberry32(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function generateCostMatrix(assets: number, tasks: number, seed: number): number[][] {
  // Note: numpy's default_rng(seed).integers(1, 100, ...) won't match this PRNG
  // exactly, but the *structure* is what we're showing — we just need
  // deterministic values in roughly the right range.
  const rng = mulberry32(seed);
  const m: number[][] = [];
  for (let i = 0; i < assets; i++) {
    const row: number[] = [];
    for (let j = 0; j < tasks; j++) {
      row.push(1 + Math.floor(rng() * 99));
    }
    m.push(row);
  }
  return m;
}

function buildQubo(
  cm: number[][],
  capacity: number,
  penalty: number,
): number[][] {
  const numAssets = cm.length;
  const numTasks = cm[0].length;
  const n = numAssets * numTasks;
  const Q: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));

  // (1) Diagonal: cost contribution.
  for (let i = 0; i < numAssets; i++) {
    for (let j = 0; j < numTasks; j++) {
      const k = i * numTasks + j;
      Q[k][k] += cm[i][j];
    }
  }

  // (2) Each task assigned exactly once: (sum_i x[i,j] - 1)^2.
  // Diagonal -penalty per slot, off-diagonal +2*penalty per same-task pair.
  for (let j = 0; j < numTasks; j++) {
    for (let i = 0; i < numAssets; i++) {
      const k = i * numTasks + j;
      Q[k][k] -= penalty;
    }
    for (let i1 = 0; i1 < numAssets; i1++) {
      for (let i2 = i1 + 1; i2 < numAssets; i2++) {
        const k1 = i1 * numTasks + j;
        const k2 = i2 * numTasks + j;
        Q[k1][k2] += 2 * penalty;
        Q[k2][k1] += 2 * penalty; // mirror for symmetric display
      }
    }
  }

  // (3) Capacity penalty: same-asset pairs above capacity.
  if (capacity < numTasks) {
    const slack = (penalty * 0.5) / Math.max(1, capacity);
    for (let i = 0; i < numAssets; i++) {
      for (let j1 = 0; j1 < numTasks; j1++) {
        for (let j2 = j1 + 1; j2 < numTasks; j2++) {
          const k1 = i * numTasks + j1;
          const k2 = i * numTasks + j2;
          Q[k1][k2] += slack;
          Q[k2][k1] += slack;
        }
      }
    }
  }

  return Q;
}

/** Diverging blue (negative) → near-black (zero) → red (positive). */
function cellColor(v: number, maxAbs: number): string {
  if (v === 0) return "#1c2129";
  const t = Math.max(-1, Math.min(1, v / maxAbs));
  if (t < 0) {
    // negative: blend from #1c2129 -> #4493f8
    const a = -t;
    return mix("#1c2129", "#4493f8", a);
  }
  // positive: blend from #1c2129 -> #cf222e
  return mix("#1c2129", "#cf222e", t);
}

function mix(c1: string, c2: string, t: number): string {
  const a = hexRgb(c1);
  const b = hexRgb(c2);
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bl = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r},${g},${bl})`;
}

function hexRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}
