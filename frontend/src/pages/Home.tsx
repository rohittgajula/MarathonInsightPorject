import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { DailyLogBox } from "../components/DailyLogBox";
import { TrendCharts } from "../components/TrendCharts";
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
      <div>
        <div className="eyebrow">Today is {dateStr(new Date().toISOString().slice(0, 10))}</div>
        <h1>Tomorrow</h1>
      </div>

      {!data.garmin_connected && (
        <div className="banner">
          <p>
            <strong>Garmin isn't connected yet.</strong> Everything below comes from
            files you've uploaded by hand. Connect Garmin to have runs appear on their own.
          </p>
        </div>
      )}

      {t && (
        <div className="card stack" style={{ gap: 12 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="row" style={{ gap: 9 }}>
              <h2>{t.title}</h2>
              {t.kind !== "rest" && (
                <span className={`chip ${KIND_CHIP[t.kind] ?? ""}`}>{t.kind}</span>
              )}
              {t.note && <span className="chip warn">{t.note}</span>}
            </div>
            <span className="faint">
              Week {t.plan_week} of 17 · {t.phase} · {t.weeks_out} weeks to race
            </span>
          </div>
          <p style={{ fontSize: 14 }}>{t.detail}</p>
          {(t.run_minutes > 0 || t.distance_km > 0) && (
            <div className="row" style={{ gap: 22 }}>
              {t.run_minutes > 0 && (
                <span className="faint">
                  Running time <b className="mono" style={{ color: "var(--ink)" }}>{t.run_minutes} min</b>
                </span>
              )}
              {t.distance_km > 0 && (
                <span className="faint">
                  Distance <b className="mono" style={{ color: "var(--ink)" }}>{t.distance_km} km</b>
                </span>
              )}
            </div>
          )}
        </div>
      )}

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
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>This week</h2>
          <span className="faint">Tue and Thu intervals · Sunday long run</span>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Day</th><th>Session</th><th className="num">Running</th><th className="num">Distance</th></tr>
            </thead>
            <tbody>
              {data.week.map((s) => (
                <tr key={s.date}>
                  <td>{new Date(s.date + "T00:00:00").toLocaleDateString(undefined,
                    { weekday: "short", day: "numeric", month: "short" })}</td>
                  <td>
                    {s.title}
                    {s.note && <span className="chip warn" style={{ marginLeft: 8 }}>{s.note}</span>}
                  </td>
                  <td className="num mono">{s.run_minutes ? `${s.run_minutes} min` : "—"}</td>
                  <td className="num mono">{s.distance_km ? `${s.distance_km} km` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <TrendCharts trend={data.trend} />

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
