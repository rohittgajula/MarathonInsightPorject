import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { TrendPoint } from "../lib/types";
import { paceStr } from "../lib/format";

/* Four small charts rather than one dense one: each answers a single question, and
   none of them shares a y-axis with a measure of a different unit. */

const axis = { fill: "var(--ink-faint)", fontSize: 10 };
const shortDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });

function Frame({ title, hint, children }: {
  title: string; hint: string; children: React.ReactNode;
}) {
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div>
        <h2>{title}</h2>
        <p className="faint" style={{ marginTop: 2 }}>{hint}</p>
      </div>
      {children}
    </div>
  );
}

function Box({ children }: { children: React.ReactNode }) {
  return <div className="tooltip">{children}</div>;
}

export function TrendCharts({ trend }: { trend: TrendPoint[] }) {
  if (trend.length === 0) return null;

  if (trend.length < 3) {
    return (
      <Frame
        title="Trends"
        hint="Trend charts need at least three sessions before a line means anything."
      >
        <p className="faint">
          {trend.length} session{trend.length === 1 ? "" : "s"} recorded. Keep logging —
          these fill in from your fourth run.
        </p>
      </Frame>
    );
  }

  return (
    <div className="grid-2">
      <Frame title="Longest unbroken run" hint="The number that actually predicts finishing a 10K.">
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={trend} margin={{ top: 6, right: 10, bottom: 2, left: -12 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} stroke="var(--rule)" tickLine={false} />
            <YAxis tick={axis} stroke="var(--rule)" tickLine={false} unit="m" />
            <Tooltip content={({ active, payload }: any) =>
              active && payload?.length ? <Box><span className="mono">{payload[0].value} min</span></Box> : null} />
            <Line type="monotone" dataKey="longest_run_min" stroke="var(--run)" strokeWidth={2}
                  dot={{ r: 3, fill: "var(--run)" }} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </Frame>

      <Frame title="Pace discipline" hint="Share of running time inside your easy band. Aim above 60%.">
        <ResponsiveContainer width="100%" height={150}>
          <BarChart data={trend} margin={{ top: 6, right: 10, bottom: 2, left: -12 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <ReferenceArea y1={60} y2={100} fill="var(--band)" stroke="none" ifOverflow="hidden" />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} stroke="var(--rule)" tickLine={false} />
            <YAxis domain={[0, 100]} tick={axis} stroke="var(--rule)" tickLine={false} unit="%" />
            <Tooltip cursor={{ fill: "var(--surface-2)" }} content={({ active, payload }: any) =>
              active && payload?.length ? <Box><span className="mono">{payload[0].value}%</span></Box> : null} />
            {/* Colour encodes pass/fail against the target, not series identity. */}
            <Bar dataKey="discipline_pct" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {trend.map((p, i) => (
                <Cell key={i} fill={(p.discipline_pct ?? 0) >= 60 ? "var(--run)" : "var(--walk)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Frame>

      <Frame title="Average running pace" hint="Slower is the goal here — the axis is inverted so down is faster.">
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={trend} margin={{ top: 6, right: 10, bottom: 2, left: -4 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} stroke="var(--rule)" tickLine={false} />
            <YAxis tickFormatter={(v) => paceStr(v)} tick={axis} stroke="var(--rule)" tickLine={false} width={44} />
            <Tooltip content={({ active, payload }: any) =>
              active && payload?.length ? <Box><span className="mono">{paceStr(payload[0].value)}/km</span></Box> : null} />
            <Line type="monotone" dataKey="run_pace_s" stroke="var(--run)" strokeWidth={2}
                  dot={{ r: 3, fill: "var(--run)" }} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </Frame>

      <Frame title="Heart-rate recovery" hint="Drop in the first minute of a walk break. Should climb over the plan.">
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={trend} margin={{ top: 6, right: 10, bottom: 2, left: -12 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={axis} stroke="var(--rule)" tickLine={false} />
            <YAxis tick={axis} stroke="var(--rule)" tickLine={false} />
            <Tooltip content={({ active, payload }: any) =>
              active && payload?.length ? <Box><span className="mono">{payload[0].value} bpm</span></Box> : null} />
            <Line type="monotone" dataKey="hr_recovery" stroke="var(--run)" strokeWidth={2}
                  dot={{ r: 3, fill: "var(--run)" }} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </Frame>
    </div>
  );
}
