import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ChartNotes } from "../components/ChartNotes";
import { CourseMap } from "../components/CourseMap";
import { SegmentBar } from "../components/SegmentBar";
import { SessionCharts } from "../components/SessionCharts";
import { durStr, km, paceStr, pct, dateStr } from "../lib/format";
import type { Activity, Athlete, StreamPoint } from "../lib/types";

function Tile({ label, value, tone, note }: {
  label: string; value: string; tone?: "good" | "warn"; note?: string;
}) {
  return (
    <div className="card tile">
      <div className="k">{label}</div>
      <div className={`v mono ${tone ?? ""}`}>{value}</div>
      {note && <div className="n">{note}</div>}
    </div>
  );
}

export function ActivityDetail() {
  const { id } = useParams<{ id: string }>();

  const athlete = useQuery({
    queryKey: ["athlete"],
    queryFn: () => api.get<Athlete>("/athletes/me/"),
  });

  const activity = useQuery({
    queryKey: ["activity", id],
    queryFn: () => api.get<Activity>(`/activities/${id}/`),
  });

  // Loaded separately so summary and segments paint without waiting on ~1,700 rows.
  const stream = useQuery({
    queryKey: ["activity", id, "stream"],
    queryFn: () => api.get<StreamPoint[]>(`/activities/${id}/stream/`),
    enabled: !!activity.data,
  });

  if (activity.isLoading) return <p className="muted">Loading activity…</p>;
  if (activity.error) return <p className="error">Could not load this activity.</p>;

  const a = activity.data!;
  const m = a.metrics;
  const runs = (a.segments ?? []).filter((s) => s.kind === "run");

  const disciplineTone = m?.pace_discipline_pct == null ? undefined
    : m.pace_discipline_pct >= 60 ? "good" : "warn";

  return (
    <div className="stack" style={{ gap: 26 }}>
      <div>
        <Link to="/activities" className="faint" style={{ textDecoration: "none" }}>← All activities</Link>
        <div className="eyebrow" style={{ marginTop: 10 }}>{dateStr(a.local_date)}</div>
        <h1>{km(a.total_distance_m)} km in {durStr(a.total_elapsed_s)}</h1>
      </div>

      <div className="grid">
        <Tile
          label="Ran continuously"
          value={durStr(m?.longest_run_s)}
          note={m ? `Longest unbroken block · ${Math.round(m.longest_run_m)} m` : undefined}
        />
        <Tile
          label="Run blocks"
          value={String(m?.run_block_count ?? "—")}
          note={m ? `${km(m.run_distance_m)} km running, ${km(m.walk_distance_m)} km walking` : undefined}
        />
        <Tile
          label="Avg running pace"
          value={`${paceStr(m?.avg_run_pace_s_per_km)}/km`}
          note="Across running blocks only — walking excluded."
        />
        <Tile
          label="Pace discipline"
          value={pct(m?.pace_discipline_pct)}
          tone={disciplineTone}
          note="Share of running time inside your easy band."
        />
        <Tile
          label="HR recovery"
          value={m?.avg_hr_recovery_60s != null ? `${m.avg_hr_recovery_60s.toFixed(0)} bpm` : "—"}
          tone={m?.avg_hr_recovery_60s != null && m.avg_hr_recovery_60s >= 20 ? "good" : undefined}
          note="Drop in the first minute of a walk break. Rises as you get fitter."
        />
        <Tile
          label="HR overshoot"
          value={m?.avg_hr_overshoot_bpm != null ? `+${m.avg_hr_overshoot_bpm.toFixed(0)} bpm` : "—"}
          tone={m?.avg_hr_overshoot_bpm != null && m.avg_hr_overshoot_bpm > 4 ? "warn" : undefined}
          note="How far HR kept climbing after you stopped. Should fall towards zero."
        />
      </div>

      <div className="card stack">
        <h2>Session shape</h2>
        <SegmentBar segments={a.segments ?? []} />
        <ChartNotes notes={a.chart_notes?.shape} />
      </div>

      <div className="card stack">
        <h2>Route</h2>
        {stream.isLoading && <p className="muted">Loading route…</p>}
        {stream.data && <CourseMap stream={stream.data} segments={a.segments ?? []} />}
        <ChartNotes notes={a.chart_notes?.route} />
      </div>

      <div className="card">
        {stream.isLoading && <p className="muted">Loading per-second data…</p>}
        {stream.data && athlete.data && (
          <SessionCharts stream={stream.data} athlete={athlete.data}
                         segments={a.segments ?? []} notes={a.chart_notes} />
        )}
      </div>

      <div className="card stack">
        <h2>Run blocks</h2>
        {runs.length === 0 ? (
          <p className="faint">No running detected in this session.</p>
        ) : (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th><th>Starts</th><th className="num">Duration</th>
                  <th className="num">Distance</th><th className="num">Pace</th>
                  <th className="num">Cadence</th><th className="num">Avg HR</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((s, i) => (
                  <tr key={s.index}>
                    <td className="mono">{i + 1}</td>
                    <td className="mono">{durStr(s.start_offset_s)}</td>
                    <td className="num mono">{durStr(s.duration_s)}</td>
                    <td className="num mono">{Math.round(s.distance_m)} m</td>
                    <td className="num mono">{paceStr(s.avg_pace_s_per_km)}</td>
                    <td className="num mono">{s.avg_cadence_spm?.toFixed(0) ?? "—"}</td>
                    <td className="num mono">{s.hr_avg ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
