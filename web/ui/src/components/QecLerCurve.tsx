"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchQecLerCurve } from "@/lib/api";
import type { LerCurve } from "@/lib/types";
import styles from "./QecLerCurve.module.css";

interface Props {
  distance?: number;
  rounds?: number;
  basis?: string;
}

// Stable color mapping per backend so the same line stays the same color
// across runs. Pymatching is the baseline (cool blue), the Ising decoders
// are the AI heroes (greens).
const COLORS: Record<string, string> = {
  pymatching: "#4493f8",
  ising_speed: "#76b900",
  ising_accuracy: "#2ea043",
  cudaq_qaoa: "#db61a2",
  classical_ortools: "#a371f7",
  neal: "#d29922",
};

function colorFor(name: string): string {
  return COLORS[name] ?? "#bbb";
}

function fmtP(p: number): string {
  // Render small probabilities readably.
  if (p === 0) return "0";
  if (p < 0.001) return p.toExponential(1);
  if (p < 0.1) return p.toPrecision(2);
  return p.toString();
}

export default function QecLerCurve({ distance, rounds, basis }: Props) {
  const [data, setData] = useState<LerCurve | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const fetcher = () =>
      fetchQecLerCurve({ distance, rounds, basis })
        .then((d) => {
          if (alive) setData(d);
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    fetcher();
    const id = setInterval(fetcher, 5_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [distance, rounds, basis]);

  const subtitle = [
    distance !== undefined ? `d=${distance}` : null,
    rounds !== undefined ? `T=${rounds}` : null,
    basis ? `basis=${basis}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>QEC Lab · LER vs noise rate</h2>
        {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
      </div>

      {error && <div className={styles.empty}>Error loading LER curve: {error}</div>}
      {!error && (!data || data.points.length === 0) && (
        <div className={styles.empty}>
          No QEC runs at this configuration yet. Try{" "}
          <code>qao run &quot;decode a distance-{distance ?? 5} surface code at p=0.005&quot;</code>{" "}
          and a few more at varying noise rates.
        </div>
      )}
      {data && data.points.length > 0 && (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height="100%">
              {/* Recharts log-scale axes can't render zeros. A backend that
                  observed zero logical errors at low p is "below detection
                  limit at this sample size" — replace with null so connectNulls
                  on each Line bridges the gap rather than dropping the run. */}
              <LineChart
                data={data.points.map((pt) => {
                  const out: typeof pt = { ...pt };
                  for (const k of data.series) {
                    if (out[k] === 0) out[k] = null;
                  }
                  return out;
                })}
                margin={{ top: 8, right: 24, left: 8, bottom: 24 }}
              >
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="noise_rate"
                  type="number"
                  scale="log"
                  domain={["auto", "auto"]}
                  tickFormatter={fmtP}
                  stroke="var(--text-dim)"
                  label={{
                    value: "physical error rate p",
                    position: "insideBottom",
                    offset: -16,
                    fill: "var(--text-dim)",
                    fontSize: 12,
                  }}
                />
                <YAxis
                  type="number"
                  scale="log"
                  domain={["auto", "auto"]}
                  tickFormatter={fmtP}
                  stroke="var(--text-dim)"
                  label={{
                    value: "logical error rate (LER)",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--text-dim)",
                    fontSize: 12,
                  }}
                />
                <Tooltip content={<CurveTooltip />} />
                <Legend wrapperStyle={{ color: "var(--text-dim)" }} />
                {data.series.map((name) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    name={name}
                    stroke={colorFor(name)}
                    strokeWidth={2}
                    dot={{ r: 3, strokeWidth: 1 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className={styles.note}>
            <strong>What this shows.</strong> Each line is a decoder. The y-axis is{" "}
            <em>logical error rate</em> — how often the encoded qubit ends up in the wrong
            state across many shots. Lower is better. <strong>PyMatching</strong> (blue) is
            the standard classical decoder used as the comparator everyone publishes against.
            The two green lines are NVIDIA&apos;s <strong>Ising predecoder</strong> paired
            with PyMatching as the global cleanup step. The two cooperate: the AI handles
            easy local errors quickly, PyMatching handles the rest. Each point is the most
            recent successful run for that backend at that noise rate.
          </div>
        </>
      )}
    </div>
  );
}

interface TooltipPayloadEntry {
  name?: string;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
}

function CurveTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: number | string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipP}>p = {fmtP(Number(label))}</div>
      {payload.map((entry) => {
        const name = entry.name ?? "";
        const v = entry.value;
        const row = entry.payload || {};
        const errs = row[`${name}_logical_errors`];
        const shots = row[`${name}_shots`];
        const errsLabel = typeof errs === "number" ? String(errs) : "—";
        const shotsLabel = typeof shots === "number" ? String(shots) : "—";
        return (
          <div key={name} className={styles.row}>
            <span className={styles.swatch} style={{ background: entry.color || "#888" }} />
            <span style={{ minWidth: 110 }}>{name}</span>
            <span style={{ minWidth: 70 }}>LER {typeof v === "number" ? v.toFixed(4) : "—"}</span>
            <span style={{ color: "var(--text-dim)" }}>
              {errsLabel} / {shotsLabel}
            </span>
          </div>
        );
      })}
    </div>
  );
}
