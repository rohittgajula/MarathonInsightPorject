/* Anatomical muscle map, front and back.

   Drawn as a real silhouette with muscle-shaped regions rather than stacked
   rectangles — a blocky figure reads as a diagram of a robot, and the whole point is
   that you recognise your own body and know where to feel the work.

   Both views reuse one silhouette at an x-offset: a body seen from behind has the
   same outline, only the muscle groups differ. Regions carry <title> so hovering
   names them and screen readers can reach them. */

interface Props {
  highlighted: string[];
  labels: Record<string, string>;
}

const SKIN = "var(--surface-2)";
const EDGE = "var(--rule)";

/* Paths are authored around a figure centred on x = 0, then translated per view. */
const SILHOUETTE = `
  M -7,-96 C -14,-96 -19,-89 -19,-81 C -19,-74 -15,-68 -8,-67
  L -8,-60 C -20,-57 -30,-49 -33,-38
  C -36,-27 -37,-12 -36,2 L -30,2 C -30,-10 -28,-24 -25,-33
  L -24,-8 C -25,4 -26,18 -25,30 L 25,30 C 26,18 25,4 24,-8
  L 25,-33 C 28,-24 30,-10 30,2 L 36,2 C 37,-12 36,-27 33,-38
  C 30,-49 20,-57 8,-60 L 8,-67 C 15,-68 19,-74 19,-81
  C 19,-89 14,-96 7,-96 Z
`;

const LEGS = `
  M -25,32 C -29,52 -30,80 -27,102 C -26,112 -24,120 -23,126
  L -8,126 C -8,116 -7,104 -6,92 C -5,74 -4,52 -3,32 Z
  M 25,32 C 29,52 30,80 27,102 C 26,112 24,120 23,126
  L 8,126 C 8,116 7,104 6,92 C 5,74 4,52 3,32 Z
`;

/* key -> path. Front and back share a coordinate space; only membership differs. */
const REGIONS: Record<string, string> = {
  // ---- front ----
  core: "M -16,-30 C -8,-27 8,-27 16,-30 C 17,-14 15,4 12,14 C 4,18 -4,18 -12,14 C -15,4 -17,-14 -16,-30 Z",
  hip_flexor: "M -20,18 C -10,22 10,22 20,18 C 21,26 19,33 16,37 C 5,40 -5,40 -16,37 C -19,33 -21,26 -20,18 Z",
  quad: `M -24,40 C -27,58 -27,78 -24,94 C -20,96 -12,96 -9,94
         C -8,76 -8,56 -7,40 Z
         M 24,40 C 27,58 27,78 24,94 C 20,96 12,96 9,94
         C 8,76 8,56 7,40 Z`,
  adductor: "M -6,40 C -6,58 -5,74 -4,86 L 4,86 C 5,74 6,58 6,40 Z",
  shin: `M -22,104 C -24,116 -24,132 -22,144 L -12,144 C -11,130 -11,116 -10,104 Z
         M 22,104 C 24,116 24,132 22,144 L 12,144 C 11,130 11,116 10,104 Z`,
  // ---- back ----
  glute: "M -23,14 C -27,20 -27,32 -22,37 C -12,43 12,43 22,37 C 27,32 27,20 23,14 C 12,20 -12,20 -23,14 Z",
  hamstring: `M -24,40 C -27,58 -27,76 -24,92 C -20,94 -12,94 -9,92
              C -8,74 -8,56 -7,40 Z
              M 24,40 C 27,58 27,76 24,92 C 20,94 12,94 9,92
              C 8,74 8,56 7,40 Z`,
  calf: `M -22,102 C -25,112 -25,128 -21,138 L -11,138 C -10,124 -10,112 -9,102 Z
         M 22,102 C 25,112 25,128 21,138 L 11,138 C 10,124 10,112 9,102 Z`,
};

const FRONT = ["core", "hip_flexor", "quad", "adductor", "shin"];
const BACK = ["glute", "hamstring", "calf"];

export function BodyDiagram({ highlighted, labels }: Props) {
  const figure = (x: number, keys: string[], caption: string) => (
    <g transform={`translate(${x} 108) scale(0.86 1)`}>
      <path d={SILHOUETTE} fill={SKIN} stroke={EDGE} strokeWidth={1.4} strokeLinejoin="round" />
      <path d={LEGS} fill={SKIN} stroke={EDGE} strokeWidth={1.4} strokeLinejoin="round" />

      {keys.map((key) => {
        const on = highlighted.includes(key);
        return (
          <path
            key={key}
            d={REGIONS[key]}
            fill={on ? "var(--run)" : "var(--rule)"}
            stroke={on ? "var(--run)" : EDGE}
            strokeWidth={on ? 1.1 : 0.8}
            opacity={on ? 0.95 : 0.55}
            style={{ transition: "fill .3s var(--ease), opacity .3s var(--ease), stroke .3s var(--ease)" }}
          >
            <title>{labels[key] ?? key}</title>
          </path>
        );
      })}

      <text x="0" y="152" textAnchor="middle" fill="var(--ink-faint)"
            fontSize="10" letterSpacing="1.6"
            transform="scale(1.163 1)">{caption}</text>
    </g>
  );

  return (
    <svg viewBox="0 0 200 280" style={{ width: "100%", height: "auto", display: "block" }}
         role="img" aria-label={
           highlighted.length
             ? `Muscle map highlighting ${highlighted.map((m) => labels[m] ?? m).join(", ")}`
             : "Muscle map, front and back"
         }>
      {figure(52, FRONT, "FRONT")}
      {figure(148, BACK, "BACK")}
    </svg>
  );
}
