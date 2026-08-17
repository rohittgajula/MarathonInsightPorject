import { useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Athlete, Segment, StreamPoint } from "../lib/types";
import { durStr, paceStr } from "../lib/format";

/* Overlay several metrics from one run on a single plot.

   These have different units, and the honest way to overlay them is NOT a second
   y-axis: two independent scales make the crossings look meaningful when they are an
   artefact of where each axis happens to start. Instead every series is normalised to
   its own observed range (0-100%), so the *shapes* can be compared directly, and the
   tooltip reports real values in real units.

   The y-axis is therefore deliberately unlabelled beyond low/high — a number there
   would imply a unit that does not exist. */

type Key = "pace" | "hr" | "cadence" | "elevation";

const METRICS: { key: Key; label: string; unit: string; invert?: boolean }[] = [
  { key: "pace", label: "Pace", unit: "/km", invert: true },
  { key: "hr", label: "Heart rate", unit: "bpm" },
  { key: "cadence", label: "Cadence", unit: "spm" },
  { key: "elevation", label: "Elevation", unit: "m" },
];

/* Colour is fixed per metric, not per position, so toggling one series never
   repaints the others. The dash patterns are not decoration: the light palette sits
   at the colour-vision separation floor, which is only acceptable with a second
   encoding carrying the same information. */
const STYLE: Record<Key, { colour: string; dash?: string }> = {
  pace: { colour: "var(--s1)" },
  hr: { colour: "var(--s2)", dash: "6 3" },
  cadence: { colour: "var(--s3)", dash: "2 3" },
  elevation: { colour: "var(--s4)", dash: "8 3 2 3" },
};

const SMOOTH = 15;

function rollingMean(values: (number | null)[], window: number): (number | null)[] {
  const half = Math.floor(window / 2);
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - half), i + half + 1)
      .filter((v): v is number => v != null);
    return slice.length ? slice.reduce((a, b) => a + b, 0) / slice.length : null;
  });
}

export function MetricOverlay(
  { stream, athlete, segments }:
  { stream: StreamPoint[]; athlete: Athlete; segments: Segment[] },
) {
  const [on, setOn] = useState<Key[]>(["pace", "hr"]);

  const speeds = rollingMean(stream.map((p) => p.speed_mps ?? null), SMOOTH);
  const raw = stream.map((p, i) => {
    const speed = speeds[i];
    return {
      t: p.offset_s,
      pace: speed && speed > 0.83 ? 1000 / speed : null,
      hr: p.heart_rate ?? null,
      cadence: p.cadence_spm ?? null,
      elevation: p.altitude_m ?? null,
    };
  });

  // Normalise each metric against its own min/max across the session.
  const ranges = {} as Record<Key, { min: number; max: number }>;
  for (const { key } of METRICS) {
    const values = raw.map((r) => r[key]).filter((v): v is number => v != null);
    ranges[key] = values.length
      ? { min: Math.min(...values), max: Math.max(...values) }
      : { min: 0, max: 1 };
  }

  const rows = raw.map((r) => {
    const out: Record<string, number | null> = { t: r.t };
    for (const { key, invert } of METRICS) {
      const v = r[key];
      const { min, max } = ranges[key];
      const span = max - min || 1;
      // Pace is inverted so "up" means faster on every series, matching intuition.
      out[key] = v == null ? null
        : Math.round(((invert ? max - v : v - min) / span) * 100);
      out[`${key}_raw`] = v;
    }
    return out;
  });

  const toggle = (key: Key) =>
    setOn((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);

  const runShare = segments.filter((s) => s.kind === "run").length;

  return (
    <div className="card static stack" style={{ gap: 10 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Compare metrics</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Each series scaled to its own range so the shapes line up. Hover for real values.
          </p>
        </div>
        <div className="row" style={{ gap: 6 }}>
          {METRICS.map((m) => (
            <button
              key={m.key}
              className="ghost"
              style={{
                padding: "5px 11px", fontSize: 12.5,
                borderLeft: `4px solid ${on.includes(m.key) ? STYLE[m.key].colour : "var(--rule)"}`,
                color: on.includes(m.key) ? "var(--ink)" : "var(--ink-faint)",
              }}
              onClick={() => toggle(m.key)}
              aria-pressed={on.includes(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
          <XAxis dataKey="t" type="number" domain={[0, "dataMax"]}
                 tickFormatter={(v) => durStr(v)}
                 tick={{ fill: "var(--ink-faint)", fontSize: 11 }}
                 stroke="var(--rule)" tickLine={false} />
          <YAxis domain={[0, 100]} width={46}
                 ticks={[0, 100]} tickFormatter={(v) => (v === 0 ? "low" : "high")}
                 tick={{ fill: "var(--ink-faint)", fontSize: 10 }}
                 stroke="var(--rule)" tickLine={false} />
          <Tooltip
            cursor={{ stroke: "var(--ink-faint)" }}
            content={({ active, payload, label }: any) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload;
              return (
                <div className="tooltip">
                  <div className="t-k mono">{durStr(label)}</div>
                  {METRICS.filter((m) => on.includes(m.key)).map((m) => {
                    const v = row[`${m.key}_raw`];
                    if (v == null) return null;
                    return (
                      <div key={m.key} className="mono">
                        <span className="t-k">{m.label} </span>
                        {m.key === "pace" ? `${paceStr(v)}${m.unit}`
                          : `${Math.round(v)} ${m.unit}`}
                      </div>
                    );
                  })}
                </div>
              );
            }}
          />
          {METRICS.filter((m) => on.includes(m.key)).map((m) => (
            <Line
              key={m.key} type="monotone" dataKey={m.key}
              stroke={STYLE[m.key].colour}
              strokeDasharray={STYLE[m.key].dash}
              strokeWidth={2} dot={false} connectNulls isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <p className="faint">
        Scaled, not stacked — there is no shared unit here, so the axis reads low to
        high rather than showing numbers. Pace is flipped so higher always means faster.
        {runShare > 0 && ` This session had ${runShare} run ${runShare === 1 ? "block" : "blocks"}.`}
      </p>
    </div>
  );
}
