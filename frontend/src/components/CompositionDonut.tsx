import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { ActivityMetrics } from "../lib/types";
import { durStr } from "../lib/format";

/* How the session divided into running, walking and standing still.

   A donut is the right form here only because these are parts of one whole that sum
   to the session — the case where a pie actually works. The centre carries the number
   that matters (running share), so the chart is readable without decoding angles. */

export function CompositionDonut({ metrics }: { metrics: ActivityMetrics }) {
  const slices = [
    { key: "Running", value: metrics.run_time_s, color: "var(--run)" },
    { key: "Walking", value: metrics.walk_time_s, color: "var(--walk)" },
    { key: "Stopped", value: metrics.stop_time_s, color: "var(--stop)" },
  ].filter((s) => s.value > 0);

  const total = slices.reduce((sum, s) => sum + s.value, 0);
  if (!total) return null;
  const runShare = Math.round((100 * metrics.run_time_s) / total);

  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div>
        <h2>Where the time went</h2>
        <p className="faint" style={{ marginTop: 2 }}>Running, walking and standing still</p>
      </div>

      <div style={{ position: "relative" }}>
        <ResponsiveContainer width="100%" height={196}>
          <PieChart>
            <Pie
              data={slices} dataKey="value" nameKey="key"
              innerRadius="64%" outerRadius="92%"
              startAngle={90} endAngle={-270}
              paddingAngle={2} stroke="none" isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.key} fill={s.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        <div style={{
          position: "absolute", inset: 0, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", pointerEvents: "none",
        }}>
          <div className="mono" style={{ fontSize: 30, fontWeight: 750, letterSpacing: "-.03em" }}>
            {runShare}%
          </div>
          <div className="faint">running</div>
        </div>
      </div>

      <div className="stack" style={{ gap: 7 }}>
        {slices.map((s) => (
          <div key={s.key} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
            <span className="row" style={{ gap: 8 }}>
              <i className="sw" style={{ background: s.color }} />
              <span style={{ fontSize: 13.5 }}>{s.key}</span>
            </span>
            <span className="mono faint">
              {durStr(s.value)} · {Math.round((100 * s.value) / total)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
