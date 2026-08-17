/* Animated demonstration per exercise.

   Same visual language as the muscle map: a filled body silhouette rather than stick
   lines, with the moving part drawn in the run colour so the movement reads at a
   glance. SVG + CSS keyframes rather than video or GIF — it takes theme colours,
   weighs nothing, and genuinely stops under prefers-reduced-motion.

   The loops are slow and eased on purpose. These are controlled movements, and a fast
   loop teaches the wrong tempo. */

const BODY = "var(--ink-faint)";
const MOVE = "var(--run)";
const HINT = { stroke: MOVE, strokeWidth: 1.6, fill: "none", strokeDasharray: "3 3", opacity: 0.5 };

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <svg viewBox="0 0 130 130" className="ex-anim" role="img" aria-label={label}>
      {children}
    </svg>
  );
}

/** Head + torso, shared by the upright figures. */
function Upright({ x = 60 }: { x?: number }) {
  return (
    <g>
      <circle cx={x} cy={22} r={8} fill={BODY} />
      <path d={`M${x - 9},32 C${x - 13},40 ${x - 13},52 ${x - 11},62
                L${x + 11},62 C${x + 13},52 ${x + 13},40 ${x + 9},32 Z`} fill={BODY} />
    </g>
  );
}

function AnkleCircles() {
  return (
    <Frame label="Ankle drawing slow circles, ten in each direction">
      <path d="M56,20 C52,34 52,52 54,68 L66,68 C68,52 68,34 64,20 Z" fill={BODY} opacity=".55" />
      <path d="M56,68 C54,80 54,90 56,98 L66,98 C67,88 67,78 66,68 Z" fill={BODY} />
      <circle cx="61" cy="99" r="3.5" fill={MOVE} />
      <g className="anim-ankle" style={{ transformOrigin: "61px 99px" }}>
        <path d="M61,99 C68,101 76,104 80,109 C76,113 66,112 61,108 Z" fill={MOVE} />
      </g>
      <circle cx="61" cy="99" r="19" {...HINT} />
      <path d="M78,92 l3.5 7 l-7.5 1 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function LegSwings() {
  return (
    <Frame label="Leg swinging forward and back from the hip">
      <rect x="12" y="10" width="5" height="112" rx="2" fill="var(--rule)" />
      <Upright x="52" />
      <path d="M43,38 L22,34 L21,40 L43,45 Z" fill={BODY} />
      <path d="M45,62 C42,80 42,98 44,112 L54,112 C55,96 55,78 55,62 Z" fill={BODY} opacity=".55" />
      <g className="anim-swing" style={{ transformOrigin: "58px 62px" }}>
        <path d="M56,62 C57,80 58,96 59,110 C63,112 68,112 70,110
                 C69,94 67,78 66,62 Z" fill={MOVE} />
        <path d="M59,110 C63,112 70,113 74,116 C70,119 62,118 59,116 Z" fill={MOVE} />
      </g>
      <path d="M78,104 h26" {...HINT} />
      <path d="M104,104 l-7,-3.5 v7 z" fill={MOVE} opacity=".75" />
      <path d="M78,104 l7,-3.5 v7 z" fill={MOVE} opacity=".75" />
    </Frame>
  );
}

function LateralSwings() {
  return (
    <Frame label="Leg swinging side to side across the body">
      <Upright x="62" />
      <path d="M53,38 L36,32 L34,38 L52,45 Z" fill={BODY} />
      <path d="M71,38 L88,32 L90,38 L72,45 Z" fill={BODY} />
      <path d="M53,62 C51,80 51,98 53,112 L62,112 C62,96 62,78 62,62 Z" fill={BODY} />
      <g className="anim-lateral" style={{ transformOrigin: "64px 62px" }}>
        <path d="M64,62 C65,80 66,96 67,110 L77,110 C76,94 74,78 73,62 Z" fill={MOVE} />
        <path d="M67,110 C72,112 79,112 82,115 C78,118 70,117 67,115 Z" fill={MOVE} />
      </g>
      <path d="M28,120 h74" {...HINT} />
      <path d="M102,120 l-7,-3.5 v7 z" fill={MOVE} opacity=".75" />
      <path d="M28,120 l7,-3.5 v7 z" fill={MOVE} opacity=".75" />
    </Frame>
  );
}

function GluteBridge() {
  return (
    <Frame label="Hips lifting off the floor into a bridge">
      <rect x="8" y="106" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="24" cy="94" r="8" fill={BODY} />
      <path d="M88,106 C90,92 90,80 88,72 L78,72 C79,84 79,96 79,106 Z" fill={BODY} />
      <g className="anim-bridge">
        <path d="M32,100 C46,94 60,88 74,78 L80,88 C66,98 48,104 34,108 Z" fill={MOVE} />
        <path d="M74,78 C80,74 85,72 89,71 L91,80 C87,82 83,84 80,88 Z" fill={MOVE} />
      </g>
      <path d="M56,64 v-18" {...HINT} strokeDasharray="3 3" />
      <path d="M56,44 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function CalfRaises() {
  return (
    <Frame label="Rising onto the toes and lowering under control">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-calf">
        <Upright x="60" />
        <path d="M51,62 C49,78 49,94 51,106 L59,106 C59,92 59,76 59,62 Z" fill={BODY} />
        <path d="M61,62 C61,76 61,92 61,106 L69,106 C71,94 71,78 69,62 Z" fill={MOVE} />
        <path d="M51,106 C48,109 46,111 45,113 L74,113 C73,110 71,108 69,106 Z" fill={MOVE} />
      </g>
      <path d="M96,102 v-26" {...HINT} />
      <path d="M96,74 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function WalkIn() {
  return (
    <Frame label="Walking briskly, arms and legs swinging">
      <rect x="8" y="116" width="114" height="4" rx="2" fill="var(--rule)" />
      <Upright x="62" />
      <g className="anim-walk-a" style={{ transformOrigin: "62px 62px" }}>
        <path d="M58,62 C55,80 52,98 50,114 L60,116 C62,98 63,80 64,62 Z" fill={MOVE} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "62px 62px" }}>
        <path d="M62,62 C64,80 67,98 70,114 L79,112 C76,96 72,78 69,62 Z" fill={BODY} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "62px 38px" }}>
        <path d="M55,36 L38,50 L42,56 L58,44 Z" fill={BODY} />
      </g>
      <g className="anim-walk-a" style={{ transformOrigin: "62px 38px" }}>
        <path d="M69,36 L86,50 L82,56 L66,44 Z" fill={BODY} />
      </g>
    </Frame>
  );
}

const BY_KEY: Record<string, () => React.ReactElement> = {
  ankle_circles: AnkleCircles,
  leg_swings: LegSwings,
  lateral_swings: LateralSwings,
  glute_bridge: GluteBridge,
  calf_raises: CalfRaises,
  walk_in: WalkIn,
};

export function ExerciseAnimation({ exerciseKey }: { exerciseKey: string }) {
  const Component = BY_KEY[exerciseKey];
  if (!Component) return null;
  return <Component />;
}
