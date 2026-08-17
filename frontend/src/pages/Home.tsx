import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { DailyLogBox } from "../components/DailyLogBox";
import { GarminButton } from "../components/GarminButton";
import { TrendCharts } from "../components/TrendCharts";
import { WellnessCharts } from "../components/WellnessCharts";
import { dateStr, durStr, paceStr } from "../lib/format";
import type { Dashboard } from "../lib/types";

const KIND_CHIP: Record<string, string> = {
  intervals: "accent", long: "accent", race: "warn", rest: "",
};

export function Home() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<Dashboard>("/dashboard/"),
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (error || !data) return <p className="error">Could not load your dashboard.</p>;

  const t = data.tomorrow;

  return (
    <div className="stack" style={{ gap: 22 }}>
      <div className="pagebar">
        <span className="eyebrow">Training</span>
        <GarminButton />
      </div>

      <div className="hero">
        <div className="row split" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="row" style={{ gap: 14, alignItems: "flex-start", flexWrap: "nowrap" }}>
            <span className="hero-icon" aria-hidden="true">🏃</span>
            <div style={{ minWidth: 0 }}>
              <div className="eyebrow">
                {dateStr(new Date().toISOString().slice(0, 10))}
              </div>
              <h1>Tomorrow: {t ? t.title : "no plan set"}</h1>
              <p>
                {t
                  ? t.kind === "rest"
                    ? "A rest day. Adaptation happens on the days you don't run."
                    : `Week ${t.plan_week} of 17 · ${t.phase}. Run blocks at 10:00–10:45/km — keep your cadence and shorten your stride.`
                  : "Add a target race to get a session prescribed for every day."}
              </p>
            </div>
          </div>
          {t && (
            <span className="hero-badge mono">{t.weeks_out} weeks to race</span>
          )}
        </div>
        {t?.adjusted && (
          <p style={{ marginTop: 14, paddingTop: 12,
                      borderTop: "1px solid rgba(255,255,255,.22)" }}>
            <strong>Adjusted from your log.</strong> {t.adjust_reason}
          </p>
        )}
      </div>


      <div className="grid-2">
        <div className="card stack" style={{ gap: 0 }}>
          <h2 style={{ marginBottom: 12 }}>What your data says</h2>
          {data.insights.map((c, i) => (
            <div key={i} className={`insight ${c.tone}`}>
              <span className="stripe" />
              <div>
                <h3>{c.headline}</h3>
                <p>{c.detail}</p>
              </div>
            </div>
          ))}
        </div>

        <DailyLogBox />
      </div>

      <div className="card stack">
        <div className="row split" style={{ justifyContent: "space-between" }}>
          <h2>This week</h2>
          <span className="faint">Tue and Thu intervals · Sunday long run</span>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Day</th><th>Session</th><th>Focus</th>
                <th>Target pace</th><th>Target HR</th>
                <th className="num">Running</th><th className="num">Distance</th>
                <th className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.week.map((s) => (
                <tr key={s.date}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {new Date(s.date + "T00:00:00").toLocaleDateString(undefined,
                      { weekday: "short", day: "numeric", month: "short" })}
                  </td>
                  <td>
                    {s.title}
                    {s.note && <span className="chip warn" style={{ marginLeft: 8 }}>{s.note}</span>}
                    {s.adjusted && <span className="chip accent" style={{ marginLeft: 8 }}>adjusted</span>}
                  </td>
                  <td className="faint">{s.focus || "—"}</td>
                  <td className="mono faint">{s.target_pace || "—"}</td>
                  <td className="mono faint">{s.target_hr || "—"}</td>
                  <td className="num mono">{s.run_minutes ? `${s.run_minutes} min` : "—"}</td>
                  <td className="num mono">{s.distance_km ? `${s.distance_km} km` : "—"}</td>
                  <td className="num mono">{s.total_minutes ? `${s.total_minutes} min` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="row split" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <h2>From your watch</h2>
          <span className="faint">Sleep, readiness and load — measured, not typed</span>
        </div>
        <WellnessCharts wellness={data.wellness ?? []} />
      </div>

      <div>
        <div className="row split" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <h2>From your runs</h2>
          <span className="faint">Derived from the per-second data in each session</span>
        </div>
        <TrendCharts trend={data.trend} />
      </div>

      {data.trend.length > 0 && (
        <div className="card stack">
          <h2>Recent sessions</h2>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th><th className="num">Distance</th><th className="num">Longest run</th>
                  <th className="num">Run pace</th><th className="num">Discipline</th>
                </tr>
              </thead>
              <tbody>
                {[...data.trend].reverse().map((p) => (
                  <tr key={p.date}>
                    <td>{dateStr(p.date)}</td>
                    <td className="num mono">{p.distance_km} km</td>
                    <td className="num mono">
                      {p.longest_run_min ? durStr(p.longest_run_min * 60) : "—"}
                    </td>
                    <td className="num mono">{paceStr(p.run_pace_s)}</td>
                    <td className="num mono">
                      {p.discipline_pct != null ? `${p.discipline_pct.toFixed(0)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
