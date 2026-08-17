import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceArea,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { WellnessPoint } from "../lib/types";

/* Sleep, readiness and load, measured by the watch rather than self-reported.

   Colour here is semantic, not categorical: bars are green when the night met the
   athlete's own sleep need and neutral when it fell short, so the chart answers
   "was that enough" without the reader decoding a legend. */

const axis = { fill: "var(--ink-faint)", fontSize: 10 };
const shortDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });

function Frame({ title, hint, children }: {
  title: string; hint: string; children: React.ReactNode;
}) {
  return (
    <div className="card static stack" style={{ gap: 8 }}>
      <div>
        <h2>{title}</h2>
        <p className="faint" style={{ marginTop: 2 }}>{hint}</p>
      </div>
      {children}
    </div>
  );
}

const Box = ({ children }: { children: React.ReactNode }) => (
  <div className="tooltip">{children}</div>
);

export function WellnessCharts({ wellness }: { wellness: WellnessPoint[] }) {
  if (wellness.length === 0) {
    return (
      <Frame
        title="Sleep, readiness and load"
        hint="Measured by your watch — sleep against your personal sleep need, Garmin's training readiness, and how fast your load is ramping."
      >
        <p className="faint">
          Nothing here yet. These fill in from your watch once Garmin is connected and
          you press Refresh — they are not something you can type in.
        </p>
      </Frame>
    );
  }

  const hasSleep = wellness.some((w) => w.sleep_hours != null);
  const hasReadiness = wellness.some((w) => w.training_readiness != null);
  const hasRhr = wellness.some((w) => w.resting_hr != null);
  const hasLoad = wellness.some((w) => w.load_ratio != null);

  return (
    <div className="grid-2">
      {hasSleep && (
        <Frame title="Sleep vs your sleep need"
               hint="Green nights met what Garmin says your body needed. The line is that need.">
          <ResponsiveContainer width="100%" height={155}>
            <ComposedChart data={wellness} margin={{ top: 6, right: 10, bottom: 2, left: -14 }}>
              <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={axis}
                     stroke="var(--rule)" tickLine={false} />
              <YAxis tick={axis} stroke="var(--rule)" tickLine={false} unit="h" />
              <Tooltip cursor={{ fill: "var(--surface-2)" }} content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const w = payload[0].payload as WellnessPoint;
                return (
                  <Box>
                    <div className="mono">{w.sleep_hours}h slept</div>
                    {w.sleep_need_hours != null && (
                      <div className="mono t-k">{w.sleep_need_hours}h needed</div>
                    )}
                    {w.sleep_score != null && <div className="mono t-k">score {w.sleep_score}</div>}
                  </Box>
                );
              }} />
              <Bar dataKey="sleep_hours" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {wellness.map((w, i) => (
                  <Cell key={i} fill={(w.sleep_deficit_hours ?? 0) <= 0 ? "var(--run)" : "var(--walk)"} />
                ))}
              </Bar>
              <Line type="monotone" dataKey="sleep_need_hours" stroke="var(--warn)"
                    strokeWidth={1.5} strokeDasharray="4 3" dot={false}
                    connectNulls isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Frame>
      )}

      {hasReadiness && (
        <Frame title="Training readiness"
               hint="Garmin's own 0–100 read on whether today is a day to push. Below 35 eases tomorrow's session automatically.">
          <ResponsiveContainer width="100%" height={155}>
            <ComposedChart data={wellness} margin={{ top: 6, right: 10, bottom: 2, left: -14 }}>
              <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
              <ReferenceArea y1={0} y2={35} fill="var(--warn-soft)" stroke="none" ifOverflow="hidden" />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={axis}
                     stroke="var(--rule)" tickLine={false} />
              <YAxis domain={[0, 100]} tick={axis} stroke="var(--rule)" tickLine={false} />
              <Tooltip content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const w = payload[0].payload as WellnessPoint;
                return <Box><div className="mono">{w.training_readiness}/100</div></Box>;
              }} />
              <Line type="monotone" dataKey="training_readiness" stroke="var(--run)"
                    strokeWidth={2} dot={{ r: 2.5, fill: "var(--run)" }}
                    connectNulls isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Frame>
      )}

      {hasLoad && (
        <Frame title="Training load ratio"
               hint="Recent load against your longer-term average. Above 1.5 means you are ramping faster than you are absorbing.">
          <ResponsiveContainer width="100%" height={155}>
            <ComposedChart data={wellness} margin={{ top: 6, right: 10, bottom: 2, left: -14 }}>
              <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
              <ReferenceArea y1={0.8} y2={1.5} fill="var(--band)" stroke="none" ifOverflow="hidden" />
              <ReferenceLine y={1.5} stroke="var(--warn)" strokeDasharray="4 3" ifOverflow="extendDomain" />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={axis}
                     stroke="var(--rule)" tickLine={false} />
              <YAxis tick={axis} stroke="var(--rule)" tickLine={false} />
              <Tooltip content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const w = payload[0].payload as WellnessPoint;
                return (
                  <Box>
                    <div className="mono">ratio {w.load_ratio}</div>
                    {w.training_status && <div className="mono t-k">{w.training_status}</div>}
                  </Box>
                );
              }} />
              <Line type="monotone" dataKey="load_ratio" stroke="var(--run)" strokeWidth={2}
                    dot={{ r: 2.5, fill: "var(--run)" }} connectNulls isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Frame>
      )}

      {hasRhr && (
        <Frame title="Resting heart rate"
               hint="A rise sustained over several days usually means fatigue or illness before you feel it.">
          <ResponsiveContainer width="100%" height={155}>
            <BarChart data={wellness} margin={{ top: 6, right: 10, bottom: 2, left: -14 }}>
              <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={axis}
                     stroke="var(--rule)" tickLine={false} />
              <YAxis domain={["dataMin - 4", "dataMax + 4"]} tick={axis}
                     stroke="var(--rule)" tickLine={false} />
              <Tooltip cursor={{ fill: "var(--surface-2)" }} content={({ active, payload }: any) =>
                active && payload?.length
                  ? <Box><div className="mono">{payload[0].value} bpm</div></Box> : null} />
              <Bar dataKey="resting_hr" fill="var(--walk)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Frame>
      )}
    </div>
  );
}
