/* Front/back body outline with highlightable muscle regions.

   Hand-authored SVG rather than an image so the regions are real elements: they take
   theme colours, animate, and carry accessible names. Anatomically simplified on
   purpose — the job is "which part of me does this work", not a medical illustration. */

interface Props {
  highlighted: string[];
  labels: Record<string, string>;
}

const SKIN = "var(--surface-2)";
const EDGE = "var(--rule)";

export function BodyDiagram({ highlighted, labels }: Props) {
  const on = (key: string) => highlighted.includes(key);
  const fill = (key: string) => (on(key) ? "var(--run)" : SKIN);
  const opacity = (key: string) => (on(key) ? 1 : 0.85);

  const region = (key: string, d: string) => (
    <path
      d={d}
      fill={fill(key)}
      stroke={EDGE}
      strokeWidth={0.8}
      opacity={opacity(key)}
      style={{ transition: "fill .28s var(--ease), opacity .28s var(--ease)" }}
    >
      <title>{labels[key] ?? key}</title>
    </path>
  );

  return (
    <svg viewBox="0 0 220 260" style={{ width: "100%", height: "auto", display: "block" }}
         role="img" aria-label={
           highlighted.length
             ? `Body diagram highlighting ${highlighted.map((m) => labels[m] ?? m).join(", ")}`
             : "Body diagram"
         }>
      <text x="52" y="12" textAnchor="middle" fill="var(--ink-faint)" fontSize="8">FRONT</text>
      <text x="168" y="12" textAnchor="middle" fill="var(--ink-faint)" fontSize="8">BACK</text>

      {/* ---------------- front ---------------- */}
      <g>
        <circle cx="52" cy="30" r="11" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M40 45 h24 v34 h-24 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        {region("core", "M42 79 h20 v22 h-20 z")}
        {region("hip_flexor", "M40 101 h24 v14 l-12 4 l-12 -4 z")}
        {region("quad", "M41 119 h9 v40 h-9 z")}
        {region("quad", "M54 119 h9 v40 h-9 z")}
        {region("adductor", "M50 119 h4 v34 h-4 z")}
        {region("shin", "M42 163 h7 v42 h-7 z")}
        {region("shin", "M55 163 h7 v42 h-7 z")}
        <path d="M40 207 h11 v7 h-11 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M53 207 h11 v7 h-11 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        {/* arms */}
        <path d="M30 46 h8 v50 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M66 46 h8 v50 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
      </g>

      {/* ---------------- back ---------------- */}
      <g>
        <circle cx="168" cy="30" r="11" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M156 45 h24 v34 h-24 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        {region("core", "M158 79 h20 v18 h-20 z")}
        {region("glute", "M156 99 h24 v22 a12 11 0 0 1 -24 0 z")}
        {region("hamstring", "M157 121 h9 v38 h-9 z")}
        {region("hamstring", "M170 121 h9 v38 h-9 z")}
        {region("calf", "M158 163 h7 v34 h-7 z")}
        {region("calf", "M171 163 h7 v34 h-7 z")}
        <path d="M157 199 h8 v9 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M170 199 h8 v9 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M146 46 h8 v50 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
        <path d="M182 46 h8 v50 h-8 z" fill={SKIN} stroke={EDGE} strokeWidth={0.8} />
      </g>

      {/* Labels only for what is currently highlighted, so the diagram stays quiet. */}
      {highlighted.map((key, i) => (
        <text key={key} x="110" y={228 + i * 11} textAnchor="middle"
              fill="var(--run)" fontSize="8.5" fontWeight="600">
          {labels[key] ?? key}
        </text>
      ))}
    </svg>
  );
}
