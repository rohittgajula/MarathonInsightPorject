import {
  Area, CartesianGrid, Cell, ComposedChart, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Athlete, Segment, StreamPoint } from "../lib/types";
import { durStr, paceStr } from "../lib/format";

/* Pace and heart rate are deliberately two stacked charts sharing an x-axis rather
   than one dual-axis chart. Two y-scales on one plot make the crossings look
   meaningful when they are an artefact of the scaling. */

const SMOOTH_WINDOW = 15;

interface Row {
  t: number;
  pace: number | null;
  hr: number | null;
  alt: number | null;
  cadence: number | null;
  kind: Segment["kind"];
}

const KIND_COLOR: Record<Segment["kind"], string> = {
  run: "var(--run)", walk: "var(--walk)", stop: "var(--stop)",
};

function kindAt(segments: Segment[], t: number): Segment["kind"] {
  for (const s of segments) {
    if (t >= s.start_offset_s && t <= s.start_offset_s + s.duration_s) return s.kind;
  }
  return "stop";
}

function rollingMean(values: (number | null)[], window: number): (number | null)[] {
  const half = Math.floor(window / 2);
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - half), i + half + 1).filter((v): v is number => v != null);
    return slice.length ? slice.reduce((a, b) => a + b, 0) / slice.length : null;
  });
}

function buildRows(stream: StreamPoint[], segments: Segment[]): Row[] {
  const smoothedSpeed = rollingMean(stream.map((p) => p.speed_mps ?? null), SMOOTH_WINDOW);
  return stream.map((p, i) => {
    const speed = smoothedSpeed[i];
    // Anything slower than ~20 min/km is standing around; plotting it wrecks the scale.
    const pace = speed && speed > 0.83 ? 1000 / speed : null;
    return {
      t: p.offset_s, pace, hr: p.heart_rate ?? null,
      alt: p.altitude_m ?? null, cadence: p.cadence_spm ?? null,
      kind: kindAt(segments, p.offset_s),
    };
  });
}

const axisStyle = { fill: "var(--ink-faint)", fontSize: 11 };

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div className="tooltip">
      <div className="t-k mono">{durStr(label)}</div>
      <div className="mono">
        {unit === "pace" ? `${paceStr(value)}/km` : `${Math.round(value)} bpm`}
      </div>
    </div>
  );
}

export function SessionCharts(
  { stream, athlete, segments }: { stream: StreamPoint[]; athlete: Athlete; segments: Segment[] },
) {
  const rows = buildRows(stream, segments);
  if (!rows.length) return <p className="faint">No per-second data for this activity.</p>;

  const paces = rows.map((r) => r.pace).filter((v): v is number => v != null);
  // Pace axis is inverted (faster is up) and clamped, so one GPS glitch can't
  // flatten the whole series into a line at the bottom.
  const paceMin = Math.max(Math.min(...paces, athlete.easy_pace_min) - 40, 180);
  const paceMax = Math.min(Math.max(...paces, athlete.easy_pace_max) + 40, 1100);

  const hrs = rows.map((r) => r.hr).filter((v): v is number => v != null);
  const hrMin = hrs.length ? Math.min(...hrs) - 8 : 60;
  const hrMax = hrs.length ? Math.max(...hrs) + 8 : 180;

  return (
    <div className="stack" style={{ gap: 22 }}>
      <div>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <h2>Pace</h2>
          <span className="faint">
            Shaded band is the prescribed easy range,{" "}
            <span className="mono">{paceStr(athlete.easy_pace_min)}–{paceStr(athlete.easy_pace_max)}/km</span>
          </span>
        </div>
        <ResponsiveContainer width="100%" height={190}>
          <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <ReferenceArea
              y1={athlete.easy_pace_min} y2={athlete.easy_pace_max}
              fill="var(--band)" stroke="none" ifOverflow="hidden"
            />
            <XAxis
              dataKey="t" type="number" domain={[0, "dataMax"]}
              tickFormatter={(v) => durStr(v)} tick={axisStyle}
              stroke="var(--rule)" tickLine={false}
            />
            <YAxis
              domain={[paceMin, paceMax]} reversed
              tickFormatter={(v) => paceStr(v)} tick={axisStyle}
              stroke="var(--rule)" tickLine={false} width={46}
            />
            <Tooltip content={<ChartTooltip unit="pace" />} cursor={{ stroke: "var(--ink-faint)" }} />
            <Line
              type="monotone" dataKey="pace" stroke="var(--run)" strokeWidth={2}
              dot={false} connectNulls={false} isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <h2>Heart rate</h2>
          <span className="faint">
            Band is the easy range; the line above it is the walk-now ceiling{" "}
            <span className="mono">({athlete.hr_ceiling} bpm)</span>
          </span>
        </div>
        <ResponsiveContainer width="100%" height={190}>
          <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <ReferenceArea
              y1={athlete.hr_easy_min} y2={athlete.hr_easy_max}
              fill="var(--band)" stroke="none" ifOverflow="hidden"
            />
            <ReferenceLine
              y={athlete.hr_ceiling} stroke="var(--warn)" strokeDasharray="4 3"
              ifOverflow="extendDomain"
            />
            <XAxis
              dataKey="t" type="number" domain={[0, "dataMax"]}
              tickFormatter={(v) => durStr(v)} tick={axisStyle}
              stroke="var(--rule)" tickLine={false}
            />
            <YAxis
              domain={[hrMin, hrMax]} tick={axisStyle}
              stroke="var(--rule)" tickLine={false} width={46}
            />
            <Tooltip content={<ChartTooltip unit="hr" />} cursor={{ stroke: "var(--ink-faint)" }} />
            <Area
              type="monotone" dataKey="hr" stroke="var(--run)" strokeWidth={2}
              fill="var(--band)" dot={false} connectNulls isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <h2>Cadence</h2>
          <span className="faint">
            Coloured by what you were doing — the gap between the two clusters is what
            the run/walk split is detected from
          </span>
        </div>
        <ResponsiveContainer width="100%" height={175}>
          <ScatterChart margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
            <ReferenceLine
              y={athlete.run_cadence_threshold} stroke="var(--ink-faint)" strokeDasharray="4 3"
              label={{ value: "run threshold", position: "insideTopRight",
                       fill: "var(--ink-faint)", fontSize: 10 }}
            />
            <XAxis
              dataKey="t" type="number" domain={[0, "dataMax"]}
              tickFormatter={(v) => durStr(v)} tick={axisStyle}
              stroke="var(--rule)" tickLine={false}
            />
            <YAxis
              dataKey="cadence" type="number" domain={[60, "dataMax"]}
              tick={axisStyle} stroke="var(--rule)" tickLine={false} width={46} unit=""
            />
            <Tooltip
              cursor={{ stroke: "var(--ink-faint)" }}
              content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const row = payload[0].payload as Row;
                return (
                  <div className="tooltip">
                    <div className="t-k mono">{durStr(row.t)}</div>
                    <div className="mono">{Math.round(row.cadence ?? 0)} spm · {row.kind}</div>
                  </div>
                );
              }}
            />
            <Scatter data={rows.filter((r) => r.cadence)} isAnimationActive={false}>
              {rows.filter((r) => r.cadence).map((r, i) => (
                <Cell key={i} fill={KIND_COLOR[r.kind]} r={1.6} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
        <div className="legend" style={{ marginTop: 4 }}>
          <span><i className="sw" style={{ background: "var(--run)" }} /> Run</span>
          <span><i className="sw" style={{ background: "var(--walk)" }} /> Walk</span>
          <span><i className="sw" style={{ background: "var(--stop)" }} /> Stopped</span>
        </div>
      </div>

      {rows.some((r) => r.alt != null) && (
        <div>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
            <h2>Elevation</h2>
            <span className="faint">
              Total ascent over the session — useful context when a pace looks slower than usual
            </span>
          </div>
          <ResponsiveContainer width="100%" height={130}>
            <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="var(--rule-soft)" vertical={false} />
              <XAxis
                dataKey="t" type="number" domain={[0, "dataMax"]}
                tickFormatter={(v) => durStr(v)} tick={axisStyle}
                stroke="var(--rule)" tickLine={false}
              />
              <YAxis
                domain={["dataMin - 3", "dataMax + 3"]} tick={axisStyle}
                stroke="var(--rule)" tickLine={false} width={46}
                tickFormatter={(v) => `${Math.round(v)}`}
              />
              <Tooltip
                cursor={{ stroke: "var(--ink-faint)" }}
                content={({ active, payload, label }: any) =>
                  active && payload?.length ? (
                    <div className="tooltip">
                      <div className="t-k mono">{durStr(label)}</div>
                      <div className="mono">{Math.round(payload[0].value)} m</div>
                    </div>
                  ) : null}
              />
              <Area
                type="monotone" dataKey="alt" stroke="var(--walk)" strokeWidth={1.5}
                fill="var(--surface-2)" dot={false} connectNulls isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
