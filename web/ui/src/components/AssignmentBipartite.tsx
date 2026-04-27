"use client";

import { useMemo } from "react";
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

// Approximate node footprints — Dagre needs these to space nodes correctly.
const NODE_W = 140;
const NODE_H = 50;

interface AssetNodeData extends Record<string, unknown> {
  label: string;
  used: boolean;
  cost?: number | string;
}
interface TaskNodeData extends Record<string, unknown> {
  label: string;
  assigned: boolean;
  assignedTo?: number;
}

// Custom node renderers — plain divs with handles on the relevant side so React
// Flow draws edges cleanly between columns.
function AssetNode({ data }: NodeProps) {
  const d = data as AssetNodeData;
  return (
    <>
      <div className={`${styles.assetNode}${d.used ? "" : " " + styles.unused}`}>
        <div className={styles.label}>{d.label}</div>
        {d.cost !== undefined && <div className={styles.sub}>cost {String(d.cost)}</div>}
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

export default function AssignmentBipartite({ problem, dispatches }: Props) {
  const winner = useMemo(() => dispatches.find((d) => d.is_winner), [dispatches]);

  const params = problem.params as Record<string, unknown>;
  const numAssets = typeof params.assets === "number" ? params.assets : 0;
  const numTasks = typeof params.tasks === "number" ? params.tasks : 0;
  const capacity = typeof params.capacity === "number" ? params.capacity : null;

  const m = (winner?.metric_payload ?? {}) as Record<string, unknown>;
  const costMatrixRaw = m.cost_matrix as unknown;
  const assignmentRaw = m.assignment as unknown;

  // assignment is keyed as { task_idx: asset_idx } in the evaluator output
  const assignment: Record<number, number> = useMemo(() => {
    const out: Record<number, number> = {};
    if (assignmentRaw && typeof assignmentRaw === "object") {
      for (const [k, v] of Object.entries(assignmentRaw as Record<string, unknown>)) {
        const ki = Number(k);
        const vi = Number(v);
        if (Number.isFinite(ki) && Number.isFinite(vi)) out[ki] = vi;
      }
    }
    return out;
  }, [assignmentRaw]);

  const costMatrix: number[][] | null = useMemo(() => {
    if (!Array.isArray(costMatrixRaw)) return null;
    const rows = costMatrixRaw as unknown[];
    if (!rows.every((r) => Array.isArray(r))) return null;
    return rows.map((r) => (r as unknown[]).map(Number));
  }, [costMatrixRaw]);

  const { nodes, edges } = useMemo(() => {
    const usedAssets = new Set<number>(Object.values(assignment));

    // 1. Build the unposed nodes + edges for React Flow.
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
        assigned: assignment[j] !== undefined,
        assignedTo: assignment[j],
      },
    }));

    const rawEdges: Edge[] = [];
    for (const [taskStr, assetIdx] of Object.entries(assignment)) {
      const j = Number(taskStr);
      const i = assetIdx;
      const cost = costMatrix?.[i]?.[j];
      rawEdges.push({
        id: `e-a${i}-t${j}`,
        source: `a${i}`,
        target: `t${j}`,
        type: "default",
        animated: false,
        style: { stroke: "var(--accent)", strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#76b900" },
        label: cost !== undefined ? String(cost) : undefined,
        labelBgStyle: { fill: "var(--panel)", fillOpacity: 0.85 },
        labelStyle: { fill: "var(--text-dim)", fontSize: 11 },
      });
    }

    // 2. Dagre auto-layout (LR — left to right, asset column → task column).
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: "LR", nodesep: 16, ranksep: 90, marginx: 16, marginy: 16 });
    for (const n of [...rawAssetNodes, ...rawTaskNodes]) {
      g.setNode(n.id, { width: NODE_W, height: NODE_H });
    }
    for (const e of rawEdges) {
      g.setEdge(e.source, e.target);
    }
    dagre.layout(g);

    const positioned = (n: Node): Node => {
      const { x, y } = g.node(n.id);
      // Dagre returns center coordinates; React Flow expects top-left.
      return { ...n, position: { x: x - NODE_W / 2, y: y - NODE_H / 2 } };
    };

    return {
      nodes: [...rawAssetNodes.map(positioned), ...rawTaskNodes.map(positioned)],
      edges: rawEdges,
    };
  }, [assignment, costMatrix, numAssets, numTasks]);

  if (!winner || numAssets === 0 || numTasks === 0) {
    return null;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>Bipartite assignment · {winner.backend_name}</h2>
        <span className={styles.subtitle}>
          {numAssets} assets · {numTasks} tasks · capacity {capacity ?? "—"}
        </span>
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
        <strong>What this shows.</strong> {numAssets} assets on the left can perform any of{" "}
        {numTasks} tasks on the right. Each (asset, task) pair has a cost; the goal is to
        cover every task while minimizing the total. The green arrows are the winning
        solver&apos;s pick, with the cost-matrix entry as the edge label. Unassigned tasks
        render red and unused assets dim, so any constraint slack is visible at a glance.
        This is the classic combinatorial optimization the orchestrator hands to the
        QAOA / annealing / classical-exact race; same input, three solvers, one chosen
        assignment.
      </div>
    </div>
  );
}
