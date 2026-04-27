"use client";

/**
 * The single most important explainer for the QEC race: the AI predecoder
 * does NOT replace the classical decoder. They cooperate.
 *
 * Pattern adapted from NVIDIA's CUDA-Q QEC 0.6 blog (2026-04-14) which shows
 * the predecoder + global-decoder pipeline as two stacked stages. This
 * version restyles into our dark theme and labels each arrow with the data
 * shape so the reader can see what flows where.
 *
 * Static SVG — no interactivity yet. Phase 1.C may add a click-to-expand
 * each box for the role-by-role explanation.
 */
export default function PredecoderPipelineDiagram() {
  // Layout in viewBox space — easy to restyle without recomputing positions.
  const W = 800;
  const H = 280;

  // Colors mapped to CSS variables so the diagram inherits the theme.
  const accent = "var(--accent)";
  const blue = "#4493f8";
  const dim = "var(--text-dim)";
  const text = "var(--text)";
  const panel = "var(--panel-2)";
  const border = "var(--border)";

  // Box geometry helper
  const Box = ({
    x, y, w, h, fill = panel, stroke = border, accent: a, children,
  }: {
    x: number; y: number; w: number; h: number;
    fill?: string; stroke?: string; accent?: string; children: React.ReactNode;
  }) => (
    <g transform={`translate(${x},${y})`}>
      <rect
        width={w} height={h} rx={6} ry={6}
        fill={fill} stroke={a ?? stroke} strokeWidth={a ? 2 : 1}
      />
      {children}
    </g>
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: "auto", maxHeight: 320 }}
      role="img"
      aria-label="AI predecoder cooperating with classical decoder"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 -5 10 10"
          refX="8"
          refY="0"
          markerWidth="8"
          markerHeight="8"
          orient="auto"
        >
          <path d="M0,-5L10,0L0,5" fill={dim} />
        </marker>
        <marker
          id="arrow-accent"
          viewBox="0 -5 10 10"
          refX="8"
          refY="0"
          markerWidth="8"
          markerHeight="8"
          orient="auto"
        >
          <path d="M0,-5L10,0L0,5" fill={accent} />
        </marker>
      </defs>

      {/* Stage 1: Stim circuit -> noisy syndromes */}
      <Box x={20} y={100} w={140} h={70}>
        <text x={70} y={28} textAnchor="middle" fill={text} fontSize="13" fontWeight="500">
          Stim circuit
        </text>
        <text x={70} y={48} textAnchor="middle" fill={dim} fontSize="11">
          surface code
        </text>
        <text x={70} y={62} textAnchor="middle" fill={dim} fontSize="11">
          d=5, T rounds
        </text>
      </Box>
      <text x={90} y={195} textAnchor="middle" fill={dim} fontSize="11">
        physics simulation
      </text>

      {/* Arrow: circuit -> raw syndromes */}
      <line x1={160} y1={135} x2={195} y2={135} stroke={dim} strokeWidth={1.5} markerEnd="url(#arrow)" />
      <text x={177} y={125} textAnchor="middle" fill={dim} fontSize="10">
        shots
      </text>

      {/* Stage 2: Raw syndromes (data shape callout) */}
      <Box x={195} y={100} w={120} h={70}>
        <text x={60} y={28} textAnchor="middle" fill={text} fontSize="13" fontWeight="500">
          Detection
        </text>
        <text x={60} y={42} textAnchor="middle" fill={text} fontSize="13" fontWeight="500">
          events
        </text>
        <text x={60} y={60} textAnchor="middle" fill={dim} fontSize="10" fontFamily="monospace">
          (N, num_dets)
        </text>
      </Box>
      <text x={255} y={195} textAnchor="middle" fill={dim} fontSize="11">
        noisy syndrome
      </text>

      {/* Branch — top to AI predecoder, bottom direct to classical */}
      <line x1={315} y1={135} x2={350} y2={135} stroke={dim} strokeWidth={1.5} />
      <line x1={350} y1={135} x2={350} y2={50} stroke={accent} strokeWidth={1.5} />
      <line x1={350} y1={50} x2={415} y2={50} stroke={accent} strokeWidth={1.5} markerEnd="url(#arrow-accent)" />
      <line x1={350} y1={135} x2={350} y2={220} stroke={blue} strokeWidth={1.5} />
      <line x1={350} y1={220} x2={415} y2={220} stroke={blue} strokeWidth={1.5} markerEnd="url(#arrow)" />

      {/* Top branch: AI predecoder */}
      <Box x={415} y={20} w={170} h={60} accent={accent}>
        <text x={85} y={26} textAnchor="middle" fill={accent} fontSize="13" fontWeight="600">
          AI predecoder
        </text>
        <text x={85} y={42} textAnchor="middle" fill={dim} fontSize="11">
          NVIDIA Ising
        </text>
        <text x={85} y={56} textAnchor="middle" fill={dim} fontSize="10">
          3D-CNN on GPU
        </text>
      </Box>

      {/* Top arrow + label */}
      <line x1={585} y1={50} x2={620} y2={50} stroke={accent} strokeWidth={1.5} />
      <line x1={620} y1={50} x2={620} y2={120} stroke={accent} strokeWidth={1.5} />
      <line x1={620} y1={120} x2={650} y2={120} stroke={accent} strokeWidth={1.5} markerEnd="url(#arrow-accent)" />
      <text x={602} y={92} fill={accent} fontSize="10">
        modified
      </text>
      <text x={602} y={104} fill={accent} fontSize="10">
        syndrome
      </text>

      {/* Bottom branch: bypass arrow goes straight to classical */}
      <Box x={415} y={190} w={170} h={60}>
        <text x={85} y={26} textAnchor="middle" fill={blue} fontSize="13" fontWeight="600">
          (or skip)
        </text>
        <text x={85} y={42} textAnchor="middle" fill={dim} fontSize="11">
          baseline path
        </text>
        <text x={85} y={56} textAnchor="middle" fill={dim} fontSize="10">
          PyMatching alone
        </text>
      </Box>
      <line x1={585} y1={220} x2={620} y2={220} stroke={blue} strokeWidth={1.5} />
      <line x1={620} y1={220} x2={620} y2={150} stroke={blue} strokeWidth={1.5} />
      <line x1={620} y1={150} x2={650} y2={150} stroke={blue} strokeWidth={1.5} markerEnd="url(#arrow)" />
      <text x={602} y={188} fill={blue} fontSize="10">
        raw
      </text>
      <text x={602} y={176} fill={blue} fontSize="10">
        syndrome
      </text>

      {/* Convergence: PyMatching */}
      <Box x={650} y={100} w={130} h={70}>
        <text x={65} y={28} textAnchor="middle" fill={text} fontSize="13" fontWeight="500">
          PyMatching
        </text>
        <text x={65} y={44} textAnchor="middle" fill={dim} fontSize="11">
          MWPM decoder
        </text>
        <text x={65} y={58} textAnchor="middle" fill={dim} fontSize="10">
          on CPU
        </text>
      </Box>

      {/* Final output label */}
      <text x={715} y={195} textAnchor="middle" fill={dim} fontSize="11">
        logical
      </text>
      <text x={715} y={207} textAnchor="middle" fill={dim} fontSize="11">
        prediction
      </text>
    </svg>
  );
}
