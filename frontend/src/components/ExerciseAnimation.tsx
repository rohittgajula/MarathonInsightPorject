/* Animated demonstration per exercise.

   Hand-authored SVG with CSS keyframes rather than a video or GIF: it inherits theme
   colours, scales without artefacts, weighs nothing, and stops dead under
   prefers-reduced-motion (where a looping GIF would keep going).

   Each figure is deliberately schematic — a stick figure showing the *movement* and
   its direction, since that is the thing a description struggles to convey. The moving
   part is drawn in the run colour so it reads instantly against the static body. */

const LIMB = { stroke: "var(--ink-faint)", strokeWidth: 4, strokeLinecap: "round" as const, fill: "none" };
const MOVE = { stroke: "var(--run)", strokeWidth: 4.5, strokeLinecap: "round" as const, fill: "none" };

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <svg viewBox="0 0 120 120" className="ex-anim" role="img" aria-label={label}>
      {children}
    </svg>
  );
}

function AnkleCircles() {
  return (
    <Frame label="Ankle drawing slow circles, ten in each direction">
      {/* lower leg, fixed */}
      <line x1="60" y1="18" x2="60" y2="66" {...LIMB} />
      <circle cx="60" cy="14" r="5" fill="var(--ink-faint)" />
      {/* foot orbits the ankle */}
      <g className="anim-ankle" style={{ transformOrigin: "60px 66px" }}>
        <line x1="60" y1="66" x2="76" y2="76" {...MOVE} />
      </g>
      {/* direction hint */}
      <path d="M84 66 a18 18 0 1 1 -6 -13" fill="none" stroke="var(--run)"
            strokeWidth="1.6" strokeDasharray="3 3" opacity=".55" />
      <path d="M78 50 l2 6 l-6 1 z" fill="var(--run)" opacity=".8" />
    </Frame>
  );
}

function LegSwings() {
  return (
    <Frame label="Leg swinging forward and back from the hip">
      <line x1="42" y1="26" x2="42" y2="60" {...LIMB} />
      <circle cx="42" cy="20" r="5" fill="var(--ink-faint)" />
      <line x1="42" y1="60" x2="42" y2="100" {...LIMB} />
      {/* wall */}
      <line x1="16" y1="14" x2="16" y2="106" stroke="var(--rule)" strokeWidth="3" />
      <line x1="42" y1="34" x2="20" y2="30" {...LIMB} />
      {/* swinging leg */}
      <g className="anim-swing" style={{ transformOrigin: "42px 60px" }}>
        <line x1="42" y1="60" x2="42" y2="100" {...MOVE} />
        <line x1="42" y1="100" x2="52" y2="103" {...MOVE} />
      </g>
      <path d="M70 92 h18" stroke="var(--run)" strokeWidth="1.6" strokeDasharray="3 3" opacity=".5" />
      <path d="M88 92 l-6 -3 v6 z" fill="var(--run)" opacity=".7" />
      <path d="M70 92 l6 -3 v6 z" fill="var(--run)" opacity=".7" />
    </Frame>
  );
}

function LateralSwings() {
  return (
    <Frame label="Leg swinging side to side across the body">
      <circle cx="60" cy="20" r="5" fill="var(--ink-faint)" />
      <line x1="60" y1="26" x2="60" y2="60" {...LIMB} />
      <line x1="60" y1="34" x2="40" y2="30" {...LIMB} />
      <line x1="60" y1="34" x2="80" y2="30" {...LIMB} />
      <line x1="60" y1="60" x2="54" y2="100" {...LIMB} />
      <g className="anim-lateral" style={{ transformOrigin: "60px 60px" }}>
        <line x1="60" y1="60" x2="66" y2="100" {...MOVE} />
        <line x1="66" y1="100" x2="72" y2="102" {...MOVE} />
      </g>
      <path d="M34 106 h52" stroke="var(--run)" strokeWidth="1.6" strokeDasharray="3 3" opacity=".5" />
      <path d="M86 106 l-6 -3 v6 z" fill="var(--run)" opacity=".7" />
      <path d="M34 106 l6 -3 v6 z" fill="var(--run)" opacity=".7" />
    </Frame>
  );
}

function GluteBridge() {
  return (
    <Frame label="Hips lifting off the floor into a bridge">
      {/* floor */}
      <line x1="10" y1="96" x2="110" y2="96" stroke="var(--rule)" strokeWidth="3" />
      {/* head + shoulders stay down */}
      <circle cx="24" cy="86" r="6" fill="var(--ink-faint)" />
      {/* knees / lower legs fixed */}
      <line x1="86" y1="96" x2="86" y2="66" {...LIMB} />
      {/* torso + thigh lift together */}
      <g className="anim-bridge">
        <line x1="32" y1="88" x2="62" y2="80" {...MOVE} />
        <line x1="62" y1="80" x2="86" y2="66" {...MOVE} />
      </g>
      <path d="M60 56 v-16" stroke="var(--run)" strokeWidth="1.6" strokeDasharray="3 3" opacity=".55" />
      <path d="M60 38 l-3 6 h6 z" fill="var(--run)" opacity=".8" />
    </Frame>
  );
}

function CalfRaises() {
  return (
    <Frame label="Rising onto the toes and lowering under control">
      <line x1="10" y1="104" x2="110" y2="104" stroke="var(--rule)" strokeWidth="3" />
      <g className="anim-calf">
        <circle cx="60" cy="26" r="6" fill="var(--ink-faint)" />
        <line x1="60" y1="32" x2="60" y2="62" {...LIMB} />
        <line x1="60" y1="62" x2="60" y2="96" {...MOVE} />
        <line x1="60" y1="96" x2="74" y2="102" {...MOVE} />
      </g>
      <path d="M92 88 v-22" stroke="var(--run)" strokeWidth="1.6" strokeDasharray="3 3" opacity=".55" />
      <path d="M92 64 l-3 6 h6 z" fill="var(--run)" opacity=".8" />
    </Frame>
  );
}

function WalkIn() {
  return (
    <Frame label="Walking briskly, arms and legs swinging">
      <line x1="10" y1="106" x2="110" y2="106" stroke="var(--rule)" strokeWidth="3" />
      <circle cx="60" cy="24" r="6" fill="var(--ink-faint)" />
      <line x1="60" y1="30" x2="60" y2="64" {...LIMB} />
      <g className="anim-walk-a" style={{ transformOrigin: "60px 64px" }}>
        <line x1="60" y1="64" x2="52" y2="104" {...MOVE} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "60px 64px" }}>
        <line x1="60" y1="64" x2="68" y2="104" {...LIMB} />
      </g>
      <g className="anim-walk-b" style={{ transformOrigin: "60px 38px" }}>
        <line x1="60" y1="38" x2="48" y2="58" {...LIMB} />
      </g>
      <g className="anim-walk-a" style={{ transformOrigin: "60px 38px" }}>
        <line x1="60" y1="38" x2="72" y2="58" {...LIMB} />
      </g>
    </Frame>
  );
}

const BY_KEY: Record<string, () => JSX.Element> = {
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
