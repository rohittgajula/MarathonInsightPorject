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


/* ---------------------------------------------------------------- strength & rehab

   Same parts, same rules as the warm-up set above: one moving element in the run
   colour, everything static muted, a dashed hint showing the path. Where two
   exercises are the same motion at a different joint angle they share a keyframe
   rather than getting a near-duplicate of their own. */

function CalfRaiseDouble() {
  return (
    <Frame label="Both heels dropping below a step, then rising onto the toes">
      <path d="M8,100 h56 v22 h58" fill="none" stroke="var(--rule)" strokeWidth="4" />
      <g className="anim-calf">
        <Torso x={60} y={18} />
        <Arm x={53} y={34} dx={-10} dy={20} />
        <Arm x={67} y={34} dx={10} dy={20} />
        <Leg x={55} y={58} length={42} fill={MOVE} />
        <Leg x={66} y={58} length={42} fill={MOVE} />
      </g>
      <path d="M98,96 v-22" {...HINT} />
      <path d="M98,72 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
      <path d="M98,96 l-3.5,-7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function CalfRaiseSingle() {
  return (
    <Frame label="Rising onto the toes of one foot, the other lifted">
      <path d="M8,100 h56 v22 h58" fill="none" stroke="var(--rule)" strokeWidth="4" />
      <rect x="112" y="16" width="5" height="90" rx="2" fill="var(--rule)" />
      <g className="anim-calf">
        <Torso x={58} y={18} />
        <Arm x={65} y={34} dx={30} dy={-2} />
        {/* the free leg stays tucked; only the standing leg drives */}
        <path d="M52,58 C48,72 50,80 54,86 L61,84 C58,76 57,70 60,60 Z" fill={BODY} />
        <Leg x={64} y={58} length={42} fill={MOVE} />
      </g>
      <path d="M96,96 v-22" {...HINT} />
      <path d="M96,72 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function BentKneeCalf() {
  return (
    <Frame label="Calf raise with the knee held bent about twenty degrees">
      <rect x="8" y="114" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-calf">
        <Torso x={58} y={22} />
        <Arm x={51} y={38} dx={-10} dy={18} />
        <Arm x={65} y={38} dx={10} dy={18} />
        {/* bent knee: thigh angles back, shin drops forward */}
        <path d="M52,62 C50,74 54,80 58,86 L67,84 C63,76 61,70 63,62 Z" fill={MOVE} />
        <path d="M58,86 L66,84 L70,110 L60,112 Z" fill={MOVE} />
        <path d="M60,112 L74,114 L74,118 L60,118 Z" fill={MOVE} />
      </g>
      <path d="M92,110 v-18" {...HINT} />
      <path d="M92,90 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
      <text x="30" y="74" fontSize="9" fill={BODY}>20°</text>
    </Frame>
  );
}

function HeelWalk() {
  return (
    <Frame label="Walking on the heels with the toes lifted high">
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <Torso x={62} y={20} />
      <Arm x={55} y={36} dx={-12} dy={18} />
      <Arm x={69} y={36} dx={12} dy={18} />
      <g className="anim-walk-a" style={{ transformOrigin: "62px 60px" }}>
        <path d="M55,60 C53,80 54,96 55,110 L64,110 C65,96 66,80 64,60 Z" fill={MOVE} />
        {/* toes up, heel down */}
        <path d="M55,110 L69,102 L71,106 L57,118 Z" fill={MOVE} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "62px 60px" }}>
        <Leg x={66} y={60} length={50} fill={BODY} />
      </g>
      <path d="M92,112 l10,-9" {...HINT} />
      <path d="M102,103 l-1,8 l6,-4 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function ToeRaise() {
  return (
    <Frame label="Seated, lifting the toes and forefoot with the heel down">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <rect x="14" y="60" width="34" height="6" rx="2" fill="var(--rule)" />
      <circle cx="30" cy="46" r="7" fill={BODY} />
      <path d="M26,54 h10 v8 h-10 z" fill={BODY} />
      <path d="M40,60 L74,60 L74,68 L40,68 Z" fill={BODY} />
      <path d="M70,66 L78,66 L78,108 L70,108 Z" fill={BODY} />
      <g className="anim-toe-raise" style={{ transformOrigin: "74px 110px" }}>
        <path d="M70,106 L96,102 L97,108 L70,112 Z" fill={MOVE} />
      </g>
      <path d="M100,104 v-14" {...HINT} />
      <path d="M100,88 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function KneeToWall() {
  return (
    <Frame label="Driving the knee forward to a wall without lifting the heel">
      <rect x="104" y="10" width="6" height="112" rx="2" fill="var(--rule)" />
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <Torso x={44} y={20} />
      <Arm x={51} y={36} dx={22} dy={-6} />
      <g className="anim-knee-wall" style={{ transformOrigin: "56px 116px" }}>
        <path d="M50,60 C50,80 58,94 66,104 L76,98 C68,88 60,76 60,60 Z" fill={MOVE} />
        <path d="M66,104 L76,98 L82,110 L70,116 Z" fill={MOVE} />
      </g>
      {/* the heel that must stay down */}
      <path d="M48,112 L74,112 L74,118 L48,118 Z" fill={BODY} />
      <path d="M86,86 h16" {...HINT} />
      <path d="M102,86 l-7,-3.5 v7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function WallSit() {
  return (
    <Frame label="Back flat to a wall, knees bent about sixty degrees, holding">
      <rect x="16" y="8" width="6" height="114" rx="2" fill="var(--rule)" />
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="32" cy="34" r="7" fill={BODY} />
      <path d="M25,42 h14 v34 h-14 z" fill={BODY} />
      <g className="anim-hold">
        {/* thigh horizontal, shin vertical */}
        <path d="M28,72 L78,72 L78,84 L28,84 Z" fill={MOVE} />
        <path d="M68,80 L80,80 L80,118 L68,118 Z" fill={MOVE} />
      </g>
      <Arm x={40} y={56} dx={26} dy={6} />
      <text x="86" y="62" fontSize="9" fill={BODY}>hold</text>
    </Frame>
  );
}

function StepDown() {
  return (
    <Frame label="Standing on one leg on a step, lowering the other heel slowly">
      <path d="M8,120 h50 v-30 h64" fill="none" stroke="var(--rule)" strokeWidth="4" />
      <Torso x={80} y={16} />
      <Arm x={73} y={32} dx={-14} dy={10} />
      <Arm x={87} y={32} dx={14} dy={10} />
      <Leg x={82} y={56} length={32} fill={BODY} />
      <g className="anim-stepdown" style={{ transformOrigin: "70px 56px" }}>
        <Leg x={68} y={56} length={32} fill={MOVE} />
      </g>
      <path d="M50,92 v22" {...HINT} />
      <path d="M50,114 l-3.5,-7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function TerminalKneeExt() {
  return (
    <Frame label="Straightening the knee against a band looped behind it">
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <rect x="112" y="20" width="6" height="70" rx="2" fill="var(--rule)" />
      <Torso x={44} y={18} />
      <Arm x={37} y={34} dx={-12} dy={14} />
      <Arm x={51} y={34} dx={12} dy={14} />
      <path d="M39,58 C38,74 40,86 42,100 L52,100 C53,86 54,74 52,58 Z" fill={BODY} />
      <path d="M38,100 L56,100 L56,118 L38,118 Z" fill={BODY} opacity=".5" />
      <g className="anim-knee-ext" style={{ transformOrigin: "58px 76px" }}>
        <path d="M53,58 C52,68 54,74 58,80 L68,76 C64,70 63,64 64,58 Z" fill={MOVE} />
        <path d="M58,80 L68,76 L76,104 L64,108 Z" fill={MOVE} />
      </g>
      {/* band from wall to the back of the knee */}
      <path d="M112,74 C96,74 76,74 62,76" {...HINT} strokeDasharray="5 4" />
    </Frame>
  );
}

function Clamshell() {
  return (
    <Frame label="Side lying with knees bent, lifting the top knee, feet together">
      <rect x="8" y="106" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="22" cy="76" r="7" fill={BODY} />
      <path d="M30,70 L66,70 L66,88 L30,88 Z" fill={BODY} />
      {/* bottom leg stays put */}
      <path d="M64,80 L88,88 L104,80 L106,88 L88,98 L62,88 Z" fill={BODY} />
      <g className="anim-clam" style={{ transformOrigin: "66px 80px" }}>
        <path d="M64,74 L90,84 L88,92 L62,82 Z" fill={MOVE} />
        <path d="M88,84 L106,76 L108,84 L90,92 Z" fill={MOVE} />
      </g>
      <path d="M96,66 a24,24 0 0 1 -6,-14" {...HINT} />
      <path d="M90,52 l6,4 l-7,3 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function SideLegRaise() {
  return (
    <Frame label="Side lying with legs straight, raising the top leg">
      <rect x="8" y="106" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="20" cy="82" r="7" fill={BODY} />
      <path d="M28,76 L58,76 L58,94 L28,94 Z" fill={BODY} />
      <path d="M56,86 L110,92 L110,100 L56,96 Z" fill={BODY} />
      <g className="anim-abduct" style={{ transformOrigin: "58px 86px" }}>
        <path d="M56,80 L110,84 L110,92 L56,88 Z" fill={MOVE} />
      </g>
      <path d="M100,74 a34,34 0 0 0 -2,-16" {...HINT} />
      <path d="M98,58 l5,6 l-8,2 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function SingleLegBridge() {
  return (
    <Frame label="Bridging on one foot with the other knee hugged in">
      <rect x="8" y="108" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="24" cy="96" r="7" fill={BODY} />
      <path d="M84,108 L84,74 L92,74 L92,108 Z" fill={BODY} />
      <g className="anim-bridge">
        <path d="M31,92 L74,74 L79,83 L36,101 Z" fill={MOVE} />
        <circle cx="76" cy="78" r="5" fill={MOVE} />
        {/* the free leg, tucked toward the chest */}
        <path d="M54,84 L64,58 L72,61 L62,87 Z" fill={MOVE} opacity=".85" />
      </g>
      <path d="M46,64 v-16" {...HINT} />
      <path d="M46,46 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function HipHike() {
  return (
    <Frame label="Standing on a step, dropping and lifting the free hip">
      <path d="M8,122 h54 v-34 h60" fill="none" stroke="var(--rule)" strokeWidth="4" />
      <Torso x={82} y={16} />
      <Arm x={89} y={32} dx={14} dy={12} />
      <Leg x={84} y={56} length={30} fill={BODY} />
      <g className="anim-hike">
        <Leg x={70} y={58} length={30} fill={MOVE} />
      </g>
      <path d="M52,80 v18" {...HINT} />
      <path d="M52,98 l-3.5,-7 h7 z" fill={MOVE} opacity=".85" />
      <path d="M52,80 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function GluteMedWall() {
  return (
    <Frame label="Standing side on to a wall, pressing the inside knee into it">
      <rect x="8" y="8" width="6" height="114" rx="2" fill="var(--rule)" />
      <rect x="20" y="118" width="102" height="4" rx="2" fill="var(--rule)" />
      <Torso x={64} y={18} />
      <Arm x={71} y={34} dx={12} dy={14} />
      <Leg x={66} y={56} length={58} fill={BODY} />
      <g className="anim-press">
        {/* thigh to the wall, shin hanging */}
        <path d="M58,58 L22,66 L22,76 L58,70 Z" fill={MOVE} />
        <path d="M22,66 L32,66 L34,94 L24,94 Z" fill={MOVE} />
      </g>
      <path d="M40,50 h-14" {...HINT} />
      <path d="M26,50 l7,-3.5 v7 z" fill={MOVE} opacity=".85" />
      <text x="44" y="40" fontSize="9" fill={BODY}>press</text>
    </Frame>
  );
}

function SidePlank() {
  return (
    <Frame label="Side plank on the forearm, hips lifted in a straight line">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-hold">
        <circle cx="26" cy="60" r="7" fill={MOVE} />
        <path d="M32,64 L104,96 L102,106 L30,74 Z" fill={MOVE} />
        <path d="M24,68 L20,110 L30,110 L34,72 Z" fill={BODY} />
        <path d="M100,98 L118,106 L118,112 L98,106 Z" fill={MOVE} />
      </g>
      <path d="M62,74 v-16" {...HINT} />
      <path d="M62,56 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function DeadBug() {
  return (
    <Frame label="On your back, lowering one arm and the opposite leg">
      <rect x="8" y="100" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="24" cy="86" r="7" fill={BODY} />
      <path d="M32,80 L74,80 L74,96 L32,96 Z" fill={BODY} />
      <g className="anim-deadbug-a" style={{ transformOrigin: "36px 82px" }}>
        <Arm x={36} y={82} dx={-2} dy={-32} fill={MOVE} />
      </g>
      <g className="anim-deadbug-b" style={{ transformOrigin: "72px 86px" }}>
        <path d="M70,80 L74,50 L84,52 L80,82 Z" fill={MOVE} />
        <path d="M74,50 L96,44 L98,52 L76,58 Z" fill={MOVE} />
      </g>
      <g className="anim-deadbug-b" style={{ transformOrigin: "36px 82px" }}>
        <Arm x={36} y={82} dx={-4} dy={-30} />
      </g>
      <text x="90" y="94" fontSize="9" fill={BODY}>back flat</text>
    </Frame>
  );
}

function BirdDog() {
  return (
    <Frame label="On hands and knees, extending one arm and the opposite leg">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <path d="M40,62 L84,62 L84,74 L40,74 Z" fill={BODY} />
      <circle cx="34" cy="64" r="7" fill={BODY} />
      <path d="M44,70 L50,112 L58,112 L52,70 Z" fill={BODY} />
      <path d="M78,70 L84,112 L92,112 L86,70 Z" fill={BODY} />
      <g className="anim-deadbug-a" style={{ transformOrigin: "44px 66px" }}>
        <path d="M42,60 L14,50 L12,58 L40,68 Z" fill={MOVE} />
      </g>
      <g className="anim-deadbug-a" style={{ transformOrigin: "84px 68px" }}>
        <path d="M82,64 L114,56 L116,64 L84,72 Z" fill={MOVE} />
      </g>
      <path d="M60,46 h20" {...HINT} />
      <text x="52" y="40" fontSize="9" fill={BODY}>hips level</text>
    </Frame>
  );
}

function CatCow() {
  return (
    <Frame label="On hands and knees, slowly rounding then arching the back">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="30" cy="64" r="7" fill={BODY} />
      <path d="M38,70 L44,112 L52,112 L46,70 Z" fill={BODY} />
      <path d="M84,70 L90,112 L98,112 L92,70 Z" fill={BODY} />
      <g className="anim-catcow">
        <path d="M36,66 C52,54 74,54 90,66 L90,76 C74,64 52,64 36,76 Z" fill={MOVE} />
      </g>
      <path d="M62,46 v-12" {...HINT} />
      <path d="M62,32 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
      <path d="M62,86 v10" {...HINT} />
      <path d="M62,98 l-3.5,-7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function HipFlexorStretch() {
  return (
    <Frame label="Half kneeling, squeezing the glute and shifting weight forward">
      <rect x="8" y="114" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-lunge">
        <Torso x={58} y={18} />
        <Arm x={51} y={34} dx={-8} dy={20} />
        <Arm x={65} y={34} dx={8} dy={20} />
        {/* front leg, foot planted ahead */}
        <path d="M62,58 L92,80 L84,90 L56,68 Z" fill={BODY} />
        <path d="M92,80 L94,112 L84,112 L82,86 Z" fill={BODY} />
        {/* back leg, knee down — this is the side being stretched */}
        <path d="M54,58 L40,96 L50,100 L62,66 Z" fill={MOVE} />
        <path d="M40,96 L24,110 L28,114 L48,104 Z" fill={MOVE} />
      </g>
      <path d="M74,44 h18" {...HINT} />
      <path d="M92,44 l-7,-3.5 v7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function RdlSingle() {
  return (
    <Frame label="Standing on one leg, hinging at the hip with a flat back">
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <g className="anim-hinge" style={{ transformOrigin: "64px 60px" }}>
        <Torso x={64} y={18} />
        <Arm x={57} y={34} dx={-6} dy={22} />
        <Arm x={71} y={34} dx={6} dy={22} />
        {/* free leg travels back as a counterweight */}
        <path d="M66,56 L112,44 L114,54 L68,66 Z" fill={MOVE} />
      </g>
      <Leg x={60} y={60} length={54} fill={BODY} />
      <path d="M34,54 a30,30 0 0 1 14,22" {...HINT} />
      <path d="M48,76 l-7,-1 l3,-6 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function AdductorSqueeze() {
  return (
    <Frame label="On your back with a ball between the knees, squeezing gently">
      <rect x="8" y="104" width="114" height="4" rx="2" fill="var(--rule)" />
      <circle cx="22" cy="84" r="7" fill={BODY} />
      <path d="M30,78 L62,78 L62,94 L30,94 Z" fill={BODY} />
      <g className="anim-squeeze">
        <path d="M60,78 L86,58 L94,66 L68,86 Z" fill={MOVE} />
        <path d="M86,58 L92,96 L82,98 L78,64 Z" fill={MOVE} />
      </g>
      <g className="anim-squeeze-b">
        <path d="M60,88 L86,70 L94,78 L68,96 Z" fill={BODY} />
      </g>
      <circle cx="90" cy="72" r="8" fill="none" stroke={MOVE} strokeWidth="2" strokeDasharray="3 3" />
      <path d="M104,60 h-8" {...HINT} />
      <path d="M96,60 l7,-3.5 v7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function Copenhagen() {
  return (
    <Frame label="Side plank with the top knee on a bench, lifting the bottom leg">
      <rect x="8" y="112" width="114" height="4" rx="2" fill="var(--rule)" />
      <rect x="76" y="82" width="46" height="6" rx="2" fill="var(--rule)" />
      <circle cx="24" cy="62" r="7" fill={MOVE} />
      <path d="M30,66 L92,80 L90,90 L28,76 Z" fill={MOVE} />
      <path d="M22,70 L18,108 L28,108 L32,74 Z" fill={BODY} />
      <g className="anim-abduct" style={{ transformOrigin: "40px 76px" }}>
        <path d="M38,80 L96,94 L94,102 L36,88 Z" fill={MOVE} />
      </g>
      <path d="M66,104 v-12" {...HINT} />
      <path d="M66,90 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function ArchDoming() {
  return (
    <Frame label="Lifting the arch without curling the toes, heel and ball planted">
      <rect x="8" y="100" width="114" height="4" rx="2" fill="var(--rule)" />
      <path d="M30,66 L46,66 L48,96 L32,96 Z" fill={BODY} />
      <g className="anim-dome">
        {/* heel and forefoot stay down; the middle lifts */}
        <path d="M30,92 C50,78 76,78 104,92 L104,100 L30,100 Z" fill={MOVE} />
      </g>
      <path d="M66,72 v-14" {...HINT} />
      <path d="M66,56 l-3.5,7 h7 z" fill={MOVE} opacity=".85" />
      <text x="20" y="118" fontSize="8.5" fill={BODY}>heel down</text>
      <text x="84" y="118" fontSize="8.5" fill={BODY}>toes flat</text>
    </Frame>
  );
}

function TowelScrunch() {
  return (
    <Frame label="Scrunching a towel toward you using only the toes">
      <rect x="8" y="102" width="114" height="4" rx="2" fill="var(--rule)" />
      <path d="M28,60 L44,60 L46,94 L30,94 Z" fill={BODY} />
      <path d="M28,90 L74,90 L74,102 L28,102 Z" fill={MOVE} />
      <g className="anim-scrunch" style={{ transformOrigin: "74px 96px" }}>
        <path d="M72,90 L92,90 L92,102 L72,102 Z" fill={MOVE} />
      </g>
      {/* the towel gathering up */}
      <path d="M92,96 c6,-5 10,5 16,0 c6,-5 10,5 14,0" fill="none"
            stroke="var(--rule)" strokeWidth="5" strokeLinecap="round" />
      <path d="M104,76 h-16" {...HINT} />
      <path d="M88,76 l7,-3.5 v7 z" fill={MOVE} opacity=".85" />
    </Frame>
  );
}

function PlantarRoll() {
  return (
    <Frame label="Rolling the sole of the foot slowly over a ball">
      <rect x="8" y="108" width="114" height="4" rx="2" fill="var(--rule)" />
      <path d="M26,50 L44,50 L48,86 L30,86 Z" fill={BODY} />
      <path d="M28,84 L86,84 L86,94 L28,94 Z" fill={BODY} />
      <g className="anim-roll">
        <circle cx="60" cy="100" r="9" fill={MOVE} />
        <path d="M55,96 l10,8 M65,96 l-10,8" stroke="var(--surface)" strokeWidth="1.6" />
      </g>
      <path d="M34,116 h56" {...HINT} />
      <path d="M90,116 l-7,-3.5 v7 z" fill={MOVE} opacity=".75" />
      <path d="M34,116 l7,-3.5 v7 z" fill={MOVE} opacity=".75" />
    </Frame>
  );
}

function CadenceSteps() {
  return (
    <Frame label="Quicker, shorter steps landing under the body">
      <rect x="8" y="118" width="114" height="4" rx="2" fill="var(--rule)" />
      <Torso x={62} y={20} />
      <g className="anim-cadence-a" style={{ transformOrigin: "62px 60px" }}>
        <Leg x={60} y={60} length={48} fill={MOVE} />
      </g>
      <g className="anim-cadence-b" style={{ transformOrigin: "62px 60px" }}>
        <Leg x={64} y={60} length={48} fill={BODY} />
      </g>
      <g className="anim-cadence-b" style={{ transformOrigin: "62px 36px" }}>
        <Arm x={55} y={36} dx={-12} dy={16} />
      </g>
      <g className="anim-cadence-a" style={{ transformOrigin: "62px 36px" }}>
        <Arm x={69} y={36} dx={12} dy={16} />
      </g>
      {/* the point of the drill: the foot lands under you, not ahead */}
      <path d="M62,112 v10" {...HINT} />
      <text x="76" y="112" fontSize="8.5" fill={BODY}>land under</text>
    </Frame>
  );
}

function AnkleAlphabet() {
  return (
    <Frame label="Drawing the alphabet with the big toe, foot off the floor">
      <rect x="14" y="60" width="30" height="6" rx="2" fill="var(--rule)" />
      <circle cx="28" cy="46" r="7" fill={BODY} />
      <path d="M40,60 L74,62 L74,70 L40,68 Z" fill={BODY} />
      <path d="M70,64 L80,64 L86,92 L76,94 Z" fill={BODY} />
      <circle cx="82" cy="94" r="3.5" fill={MOVE} />
      <g className="anim-ankle" style={{ transformOrigin: "82px 94px" }}>
        <path d="M78,94 L94,98 L94,102 L78,102 Z" fill={MOVE} />
      </g>
      <text x="96" y="74" fontSize="13" fill={MOVE} opacity=".7">A</text>
      <text x="104" y="88" fontSize="10" fill={MOVE} opacity=".5">B</text>
      <circle cx="82" cy="94" r="18" {...HINT} />
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

  // Strength & rehab. Keys match `plans/exercises.py`, so an exercise gains a
  // demonstration by name alone — nothing else has to be wired up.
  calf_raise_double: CalfRaiseDouble,
  calf_raise_single: CalfRaiseSingle,
  bent_knee_calf: BentKneeCalf,
  heel_walk: HeelWalk,
  toe_raise: ToeRaise,
  knee_to_wall: KneeToWall,
  ankle_alphabet: AnkleAlphabet,
  wall_sit: WallSit,
  step_down: StepDown,
  terminal_knee_ext: TerminalKneeExt,
  clamshell: Clamshell,
  side_leg_raise: SideLegRaise,
  single_leg_bridge: SingleLegBridge,
  it_band_hip_hike: HipHike,
  glute_med_wall: GluteMedWall,
  side_plank: SidePlank,
  dead_bug: DeadBug,
  bird_dog: BirdDog,
  cat_cow: CatCow,
  hip_flexor_stretch: HipFlexorStretch,
  rdl_single: RdlSingle,
  adductor_squeeze: AdductorSqueeze,
  copenhagen: Copenhagen,
  arch_doming: ArchDoming,
  towel_scrunch: TowelScrunch,
  plantar_roll: PlantarRoll,
  cadence_drill: CadenceSteps,
};

export function ExerciseAnimation({ exerciseKey }: { exerciseKey: string }) {
  const Component = BY_KEY[exerciseKey];
  if (!Component) return null;
  return <Component />;
}
