/* Animated demonstration per exercise.

   Figures are built from one shared set of parts — head, tapered torso, arm with a
   hand, leg with a foot — so proportions stay consistent between exercises. The
   moving limb is drawn in the run colour; everything static is muted, so the movement
   is what your eye lands on.

   SVG + CSS keyframes rather than video or GIF: takes theme colours, weighs nothing,
   and genuinely stops under prefers-reduced-motion. Loops are slow and eased because
   these are controlled movements and a fast loop teaches the wrong tempo. */

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

/** Head, neck and a torso that tapers to the waist. */
function Torso({ x, y = 20, fill = BODY }: { x: number; y?: number; fill?: string }) {
  return (
    <g>
      <circle cx={x} cy={y} r={7} fill={fill} />
      <rect x={x - 2} y={y + 6} width={4} height={4} fill={fill} />
      <path
        d={`M${x - 9},${y + 10} C${x - 10},${y + 20} ${x - 8},${y + 32} ${x - 7},${y + 40}
            L${x + 7},${y + 40} C${x + 8},${y + 32} ${x + 10},${y + 20} ${x + 9},${y + 10} Z`}
        fill={fill}
      />
    </g>
  );
}

/** Upper arm + forearm + hand, as one shape ending in a round hand. */
function Arm({ x, y, dx, dy, fill = BODY }: {
  x: number; y: number; dx: number; dy: number; fill?: string;
}) {
  const midX = x + dx * 0.55;
  const midY = y + dy * 0.55;
  return (
    <g>
      <path
        d={`M${x},${y - 3} L${midX},${midY - 3} L${x + dx},${y + dy - 3}
            L${x + dx},${y + dy + 3} L${midX},${midY + 3} L${x},${y + 3} Z`}
        fill={fill}
      />
      <circle cx={x + dx} cy={y + dy} r={3.6} fill={fill} />
    </g>
  );
}

/** Thigh + shin tapering to a foot. */
function Leg({ x, y, fill = BODY, length = 48 }: {
  x: number; y: number; fill?: string; length?: number;
}) {
  return (
    <g>
      <path
        d={`M${x - 5},${y} C${x - 6},${y + length * 0.5} ${x - 5},${y + length * 0.8} ${x - 4},${y + length}
            L${x + 4},${y + length} C${x + 5},${y + length * 0.8} ${x + 6},${y + length * 0.5} ${x + 5},${y} Z`}
        fill={fill}
      />
      <path d={`M${x - 4},${y + length} L${x + 9},${y + length + 4} L${x + 9},${y + length + 7}
                L${x - 4},${y + length + 7} Z`} fill={fill} />
    </g>
  );
}

function AnkleCircles() {
  return (
    <Frame label="Ankle drawing slow circles, ten in each direction">
      <Leg x={61} y={16} length={60} fill={BODY} />
      <circle cx="61" cy="82" r="3.5" fill={MOVE} />
      <g className="anim-ankle" style={{ transformOrigin: "61px 82px" }}>
        <path d="M57,82 L70,86 L70,90 L57,90 Z" fill={MOVE} />
      </g>
      <circle cx="61" cy="82" r="20" {...HINT} />
      <path d="M77,74 l4,7 l-8,1 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function LegSwings() {
  return (
    <Frame label="Leg swinging forward and back from the hip, holding a wall">
      <rect x="10" y="8" width="5" height="114" rx="2" fill="var(--rule)" />
      <Torso x={54} y={22} />
      {/* hand actually reaches the wall */}
      <Arm x={47} y={38} dx={-27} dy={-2} />
      <Arm x={61} y={38} dx={7} dy={16} />
      <Leg x={49} y={62} length={46} fill={BODY} />
      <g className="anim-swing" style={{ transformOrigin: "58px 62px" }}>
        <Leg x={58} y={62} length={46} fill={MOVE} />
      </g>
      <path d="M80,104 h26" {...HINT} />
      <path d="M106,104 l-7,-3.5 v7 z" fill={MOVE} opacity=".75" />
      <path d="M80,104 l7,-3.5 v7 z" fill={MOVE} opacity=".75" />
    </Frame>
  );
}

function LateralSwings() {
  return (
    <Frame label="Leg swinging side to side across the body, facing a wall">
      <Torso x={62} y={22} />
      <Arm x={55} y={38} dx={-20} dy={-8} />
      <Arm x={69} y={38} dx={20} dy={-8} />
      <Leg x={56} y={62} length={46} fill={BODY} />
      <g className="anim-lateral" style={{ transformOrigin: "66px 62px" }}>
        <Leg x={66} y={62} length={46} fill={MOVE} />
      </g>
      <path d="M30,120 h70" {...HINT} />
      <path d="M100,120 l-7,-3.5 v7 z" fill={MOVE} opacity=".75" />
      <path d="M30,120 l7,-3.5 v7 z" fill={MOVE} opacity=".75" />
    </Frame>
  );
}

function GluteBridge() {
  return (
    <Frame label="Hips lifting off the floor into a bridge">
      <rect x="8" y="108" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="24" cy="96" r="7" fill={BODY} />
      {/* shin stays planted */}
      <path d="M84,108 L84,74 L92,74 L92,108 Z" fill={BODY} />
      <g className="anim-bridge">
        {/* torso and thigh lift as one line from shoulder to knee */}
        <path d="M31,92 L74,74 L79,83 L36,101 Z" fill={MOVE} />
        <circle cx="76" cy="78" r="5" fill={MOVE} />
      </g>
      <path d="M54,62 v-18" {...HINT} />
      <path d="M54,42 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function CalfRaises() {
  return (
    <Frame label="Rising onto the toes and lowering under control">
      <rect x="8" y="114" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-calf">
        <Torso x={60} y={20} />
        <Arm x={53} y={36} dx={-9} dy={20} />
        <Arm x={67} y={36} dx={9} dy={20} />
        <Leg x={55} y={60} length={48} fill={BODY} />
        <Leg x={66} y={60} length={48} fill={MOVE} />
      </g>
      <path d="M96,104 v-26" {...HINT} />
      <path d="M96,76 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function WalkIn() {
  return (
    <Frame label="Walking briskly, arms and legs swinging">
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <Torso x={62} y={20} />
      <g className="anim-walk-a" style={{ transformOrigin: "62px 60px" }}>
        <Leg x={60} y={60} length={48} fill={MOVE} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "62px 60px" }}>
        <Leg x={64} y={60} length={48} fill={BODY} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "62px 36px" }}>
        <Arm x={55} y={36} dx={-13} dy={19} />
      </g>
      <g className="anim-walk-a" style={{ transformOrigin: "62px 36px" }}>
        <Arm x={69} y={36} dx={13} dy={19} />
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
