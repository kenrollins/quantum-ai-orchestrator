"use client";

import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
} from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import * as dagre from "@dagrejs/dagre";

import type { DispatchRow, ProblemRow } from "@/lib/types";
import styles from "./AssignmentBipartite.module.css";

interface Props {
  problem: ProblemRow;
  dispatches: DispatchRow[];
}

const NODE_W = 140;
const NODE_H = 50;

/** Per-solver visual treatment. NVIDIA green is reserved for the winner. */
const SOLVER_PALETTE: Record<string, { color: string; dash: string }> = {
  classical_ortools: { color: "#a371f7", dash: "0" },           // purple
  neal:              { color: "#d29922", dash: "0" },           // amber
  cudaq_qaoa:        { color: "#db61a2", dash: "0" },           // pink
};

const FALLBACK_COLOR = "#bbb";
const WINNER_COLOR = "#76b900"; // NVIDIA green

interface AssetNodeData extends Record<string, unknown> {
  label: string;
  used: boolean;
}
interface TaskNodeData extends Record<string, unknown> {
  label: string;
  assigned: boolean;
  assignedTo?: number;
}

function AssetNode({ data }: NodeProps) {
  const d = data as AssetNodeData;
  return (
    <>
      <div className={`${styles.assetNode}${d.used ? "" : " " + styles.unused}`}>
        <div className={styles.label}>{d.label}</div>
      </div>
      <Handle type="source" position={Position.Right} />
    </>
  );
}

function TaskNode({ data }: NodeProps) {
  const d = data as TaskNodeData;
  return (
    <>
      <Handle type="target" position={Position.Left} />
      <div className={`${styles.taskNode}${d.assigned ? "" : " " + styles.unassigned}`}>
        <div className={styles.label}>{d.label}</div>
        {d.assigned ? (
          <div className={styles.sub}>via asset {d.assignedTo}</div>
        ) : (
          <div className={styles.sub}>unassigned</div>
        )}
      </div>
    </>
  );
}

const nodeTypes = { asset: AssetNode, task: TaskNode };

interface SolverAssignment {
  backend: string;
  isWinner: boolean;
  feasible: boolean;
  objective: number | null;
  /** task_idx -> asset_idx */
  assignment: Record<number, number>;
}

/**
 * Pull every solver's assignment out of the dispatch list. Solvers that
 * didn't return a feasible assignment (cudaq_qaoa on out-of-scope problems,
 * etc.) are dropped from the overlay but kept in the legend with a "no
 * solution" note.
 */
function extractSolverAssignments(dispatches: DispatchRow[]): {
  withAssignments: SolverAssignment[];
  withoutAssignments: { backend: string; reason: string }[];
} {
  const withAssignments: SolverAssignment[] = [];
  const withoutAssignments: { backend: string; reason: string }[] = [];

  for (const d of dispatches) {
    const m = (d.metric_payload ?? {}) as Record<string, unknown>;
    const assignmentRaw = m.assignment as unknown;
    if (!assignmentRaw || typeof assignmentRaw !== "object") {
      const err = typeof m.error === "string" ? m.error : "no assignment in payload";
      withoutAssignments.push({ backend: d.backend_name, reason: err });
      continue;
    }
    const assignment: Record<number, number> = {};
    for (const [k, v] of Object.entries(assignmentRaw as Record<string, unknown>)) {
      const ki = Number(k);
      const vi = Number(v);
      if (Number.isFinite(ki) && Number.isFinite(vi)) assignment[ki] = vi;
    }
    if (Object.keys(assignment).length === 0) {
      withoutAssignments.push({ backend: d.backend_name, reason: "empty assignment" });
      continue;
    }
    withAssignments.push({
      backend: d.backend_name,
      isWinner: !!d.is_winner,
      feasible: m.is_feasible === true,
      objective: typeof m.objective === "number" ? m.objective : null,
      assignment,
    });
  }
  return { withAssignments, withoutAssignments };
}

export default function AssignmentBipartite({ problem, dispatches }: Props) {
  const params = problem.params as Record<string, unknown>;
  const numAssets = typeof params.assets === "number" ? params.assets : 0;
  const numTasks = typeof params.tasks === "number" ? params.tasks : 0;
  const capacity = typeof params.capacity === "number" ? params.capacity : null;

  const { withAssignments, withoutAssignments } = useMemo(
    () => extractSolverAssignments(dispatches),
    [dispatches],
  );

  const [showLosers, setShowLosers] = useState(true);

  const winner = useMemo(
    () => withAssignments.find((a) => a.isWinner) ?? withAssignments[0],
    [withAssignments],
  );

  const winnerCostMatrix: number[][] | null = useMemo(() => {
    if (!winner) return null;
    const dispatch = dispatches.find((d) => d.backend_name === winner.backend);
    const cm = (dispatch?.metric_payload as Record<string, unknown> | null)?.cost_matrix;
    if (!Array.isArray(cm)) return null;
    return (cm as unknown[]).map((r) => (r as unknown[]).map(Number));
  }, [dispatches, winner]);

  const { nodes, edges } = useMemo(() => {
    if (!winner || numAssets === 0 || numTasks === 0) {
      return { nodes: [] as Node[], edges: [] as Edge[] };
    }

    // Union of assets touched by any solver — keeps unused assets dim
    const usedAssets = new Set<number>();
    for (const sa of withAssignments) {
      for (const ai of Object.values(sa.assignment)) usedAssets.add(ai);
    }

    const rawAssetNodes: Node[] = Array.from({ length: numAssets }, (_, i) => ({
      id: `a${i}`,
      type: "asset",
      position: { x: 0, y: 0 },
      data: { label: `asset ${i}`, used: usedAssets.has(i) },
    }));

    const rawTaskNodes: Node[] = Array.from({ length: numTasks }, (_, j) => ({
      id: `t${j}`,
      type: "task",
      position: { x: 0, y: 0 },
      data: {
        label: `task ${j}`,
        assigned: winner.assignment[j] !== undefined,
        assignedTo: winner.assignment[j],
      },
    }));

    // Build edges per solver. Winner first conceptually, but we render
    // losers FIRST so the winner draws on top.
    const losers = withAssignments.filter((s) => !s.isWinner);
    const winnerEdges: Edge[] = [];
    const loserEdges: Edge[] = [];

    for (const sa of losers) {
      if (!showLosers) break;
      const palette = SOLVER_PALETTE[sa.backend] ?? { color: FALLBACK_COLOR, dash: "4 4" };
      for (const [taskStr, assetIdx] of Object.entries(sa.assignment)) {
        const j = Number(taskStr);
        const i = assetIdx;
        loserEdges.push({
          id: `e-${sa.backend}-a${i}-t${j}`,
          source: `a${i}`,
          target: `t${j}`,
          type: "default",
          style: {
            stroke: palette.color,
            strokeWidth: 1.4,
            strokeDasharray: "5 4",
            opacity: 0.55,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: palette.color, width: 14, height: 14 },
        });
      }
    }

    for (const [taskStr, assetIdx] of Object.entries(winner.assignment)) {
      const j = Number(taskStr);
      const i = assetIdx;
      const cost = winnerCostMatrix?.[i]?.[j];
      winnerEdges.push({
        id: `e-winner-a${i}-t${j}`,
        source: `a${i}`,
        target: `t${j}`,
        type: "default",
        style: { stroke: WINNER_COLOR, strokeWidth: 2.5, opacity: 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: WINNER_COLOR, width: 18, height: 18 },
        label: cost !== undefined ? String(cost) : undefined,
        labelBgStyle: { fill: "var(--panel)", fillOpacity: 0.9 },
        labelStyle: { fill: "var(--text)", fontSize: 11, fontWeight: 600 },
      });
    }

    // Dagre layout — feed winner edges only so the layout is stable;
    // overlay loser edges between the same node pairs.
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: "LR", nodesep: 16, ranksep: 110, marginx: 16, marginy: 16 });
    for (const n of [...rawAssetNodes, ...rawTaskNodes]) {
      g.setNode(n.id, { width: NODE_W, height: NODE_H });
    }
    for (const e of winnerEdges) g.setEdge(e.source, e.target);
    dagre.layout(g);

    const positioned = (n: Node): Node => {
      const { x, y } = g.node(n.id);
      return { ...n, position: { x: x - NODE_W / 2, y: y - NODE_H / 2 } };
    };

    return {
      nodes: [...rawAssetNodes.map(positioned), ...rawTaskNodes.map(positioned)],
      edges: [...loserEdges, ...winnerEdges],
    };
  }, [winner, withAssignments, winnerCostMatrix, numAssets, numTasks, showLosers]);

  if (!winner || numAssets === 0 || numTasks === 0) {
    return null;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>Bipartite assignment · all solvers overlaid</h2>
        <span className={styles.subtitle}>
          {numAssets} assets · {numTasks} tasks · capacity {capacity ?? "—"}
        </span>
      </div>

      <div className={styles.solverLegend}>
        <div className={styles.legendRow}>
          <span className={styles.swatch} style={{ background: WINNER_COLOR, height: 3 }} />
          <strong>{winner.backend}</strong>
          {" "}<span className={styles.legendNote}>winner · obj {winner.objective ?? "—"}</span>
        </div>
        {withAssignments
          .filter((s) => !s.isWinner)
          .map((s) => {
            const palette = SOLVER_PALETTE[s.backend] ?? { color: FALLBACK_COLOR, dash: "4 4" };
            return (
              <div key={s.backend} className={styles.legendRow}>
                <span
                  className={styles.swatch}
                  style={{
                    background: `repeating-linear-gradient(90deg, ${palette.color} 0 5px, transparent 5px 9px)`,
                    height: 2,
                  }}
                />
                {s.backend}
                {" "}
                <span className={styles.legendNote}>
                  {s.feasible ? "feasible" : "infeasible"}
                  {s.objective !== null ? ` · obj ${s.objective}` : ""}
                </span>
              </div>
            );
          })}
        {withoutAssignments.map((w) => (
          <div key={w.backend} className={`${styles.legendRow} ${styles.legendDimmed}`}>
            <span className={styles.swatch} style={{ background: "transparent", border: "1px dashed var(--text-dim)" }} />
            {w.backend}
            {" "}<span className={styles.legendNote}>no assignment ({w.reason.slice(0, 40)})</span>
          </div>
        ))}
        <button
          className={styles.toggleButton}
          onClick={() => setShowLosers((v) => !v)}
        >
          {showLosers ? "Winner only" : "Show all solvers"}
        </button>
      </div>

      <div className={styles.flowWrap}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Background color="var(--border)" gap={24} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className={styles.note}>
        <strong>What this shows.</strong> {numAssets} assets on the left, {numTasks} tasks on the
        right, and every solver&apos;s assignment overlaid on the same lattice. The{" "}
        <strong style={{ color: WINNER_COLOR }}>solid green</strong> arrows are the winner;
        dashed arrows are the losers, color-coded per solver. Where solvers agree, the lines
        stack. Where they diverge, you see <em>which</em> solver chose <em>which</em> trade-off.
        Toggle &ldquo;Winner only&rdquo; to read the chosen assignment cleanly. The orchestration
        thesis lives in this panel: same input, multiple substrates, different (sometimes
        identical, sometimes not) answers.
      </div>
    </div>
  );
}
