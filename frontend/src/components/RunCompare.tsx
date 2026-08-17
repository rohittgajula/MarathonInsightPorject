import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api/client";
import { dateStr, paceStr } from "../lib/format";
import type { Activity, CompareResponse } from "../lib/types";

/* Overlay several runs on one plot, against distance.

   Distance rather than elapsed time on the x-axis: minute 5 of a 2 km jog and minute
   5 of an 8 km long run are not comparable, but kilometre 1 always is.

   Colour is an ordinal ramp, not a categorical palette. Runs compared over time are a
   sequence — oldest to newest — so a single hue getting darker encodes that order.
   Six arbitrary hues would also have failed colour-vision checks badly (two of the
   candidates sat at ΔE 1.1 for protanopia); a one-hue ramp sidesteps that entirely and
   is the honest encoding for ordered data. */

// Read from tokens so the ramp follows the theme without JS having to detect it.
const RAMP = ["var(--r1)", "var(--r2)", "var(--r3)", "var(--r4)", "var(--r5)", "var(--r6)"];

/* Spread the chosen runs across the ramp instead of indexing from position 0.
   Taking the first N steps meant two runs got the two most recessive colours and the
   chart looked washed out; the vivid end of the ramp went unused unless you selected
   six. A single run gets the mid step, which is the same green used everywhere else
   for running. */
function rampFor(count: number): string[] {
  if (count <= 1) return [RAMP[3]];
  const lo = 1;
  const hi = RAMP.length - 1;
  return Array.from({ length: count }, (_, i) =>
    RAMP[Math.round(lo + (i * (hi - lo)) / (count - 1))]);
}

const METRICS = [
  { key: "pace", label: "Pace", invert: true },
  { key: "hr", label: "Heart rate", invert: false },
  { key: "cadence", label: "Cadence", invert: false },
] as const;

export function RunCompare({ activities }: { activities: Activity[] }) {
  const runs = activities.filter((a) => a.sport.includes("run"));
  const [selected, setSelected] = useState<number[]>(() => runs.slice(0, 3).map((a) => a.id));
  const [metric, setMetric] = useState<(typeof METRICS)[number]["key"]>("pace");

  const { data } = useQuery({
    queryKey: ["compare", selected.join(",")],
    queryFn: () => api.get<CompareResponse>(`/activities/compare/?ids=${selected.join(",")}`),
    enabled: selected.length > 0,
  });

  if (runs.length < 2) {
    return (
      <div className="card static stack" style={{ gap: 8 }}>
        <h2>Compare runs</h2>
        <p className="faint">
          Two runs are needed before an overlay says anything. You have {runs.length}.
        </p>
      </div>
    );
  }

  const toggle = (id: number) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((v) => v !== id)
      : prev.length >= 6 ? prev : [...prev, id]);

  // Oldest first, so the ramp runs light (old) to dark (recent).
  const series = [...(data?.activities ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const ramp = rampFor(series.length);

  // Merge onto one distance grid keyed by km.
  const merged = new Map<number, Record<string, number | null>>();
  series.forEach((run) => {
    run.points.forEach((p) => {
      const row = merged.get(p.km) ?? { km: p.km };
      row[`a${run.id}`] = (p as any)[metric];
      merged.set(p.km, row);
    });
  });
  const rows = [...merged.values()].sort((a, b) => (a.km as number) - (b.km as number));
  const active = METRICS.find((m) => m.key === metric)!;

  return (
    <div className="card static stack" style={{ gap: 12 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Compare runs</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Plotted against distance, so kilometre 1 lines up across every run.
          </p>
        </div>
        <div className="row" style={{ gap: 6 }}>
          {METRICS.map((m) => (
            <button key={m.key}
                    className={metric === m.key ? "" : "ghost"}
                    style={{ padding: "5px 11px", fontSize: 12.5 }}
                    onClick={() => setMetric(m.key)}
                    aria-pressed={metric === m.key}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="row" style={{ gap: 7 }}>
        {runs.slice(0, 12).map((a) => {
          const idx = series.findIndex((s) => s.id === a.id);
          const chosen = selected.includes(a.id);
          return (
            <button key={a.id}
                    className="ghost"
                    style={{
                      padding: "5px 10px", fontSize: 12,
                      borderColor: chosen && idx >= 0 ? ramp[idx] : undefined,
                      color: chosen && idx >= 0 ? ramp[idx] : undefined,
                      borderLeftWidth: chosen ? 4 : 1,
                    }}
                    onClick={() => toggle(a.id)}
                    aria-pressed={chosen}>
              {dateStr(a.local_date).replace(/,.*/, "")} · {(a.total_distance_m / 1000).toFixed(1)}k
            </button>
          );
        })}
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
          <XAxis dataKey="km" type="number" domain={[0, "dataMax"]}
                 tickFormatter={(v) => `${v.toFixed(1)}`} unit=" km"
                 tick={{ fill: "var(--ink-faint)", fontSize: 11 }}
                 stroke="var(--rule)" tickLine={false} />
          <YAxis reversed={active.invert} width={50}
                 tickFormatter={(v) => (metric === "pace" ? paceStr(v) : String(Math.round(v)))}
                 tick={{ fill: "var(--ink-faint)", fontSize: 10 }}
                 stroke="var(--rule)" tickLine={false} />
          <Tooltip
            cursor={{ stroke: "var(--ink-faint)" }}
            content={({ active: on, payload, label }: any) => {
              if (!on || !payload?.length) return null;
              return (
                <div className="tooltip">
                  <div className="t-k mono">{Number(label).toFixed(2)} km</div>
                  {payload.map((p: any) => {
                    const run = series.find((s) => `a${s.id}` === p.dataKey);
                    if (!run || p.value == null) return null;
                    return (
                      <div key={p.dataKey} className="mono">
                        <span className="t-k">{dateStr(run.date).replace(/,.*/, "")} </span>
                        {metric === "pace" ? `${paceStr(p.value)}/km` : Math.round(p.value)}
                      </div>
                    );
                  })}
                </div>
              );
            }}
          />
          {series.map((run, i) => (
            <Line key={run.id} type="monotone" dataKey={`a${run.id}`}
                  stroke={ramp[i]} strokeWidth={2} dot={false}
                  connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <div className="legend">
        {series.map((run, i) => (
          <span key={run.id}>
            <i className="sw" style={{ background: ramp[i] }} />
            {dateStr(run.date).replace(/,.*/, "")} · {run.distance_km} km
          </span>
        ))}
        <span className="faint">faded = older, brightest = most recent</span>
      </div>
    </div>
  );
}
