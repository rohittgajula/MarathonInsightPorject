import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { DailyLogBox } from "../components/DailyLogBox";
import { GarminButton } from "../components/GarminButton";
import { SessionPlan } from "../components/SessionPlan";
import { WeekTable } from "../components/WeekTable";
import { SessionWeather } from "../components/SessionWeather";
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

  const t = data.up_next ?? data.tomorrow;
  const label = data.up_next_label ?? "Tomorrow";

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
                {dateStr(data.up_next_date ?? data.local_date)}
                {data.done_today && label === "Tomorrow" && " · today's session is done"}
              </div>
              <h1>{label}: {t ? t.title : "no plan set"}</h1>
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
          // A readiness of 11/100 on 3.3 h of sleep is a different message from "you
          // are a bit short", and rendering them identically teaches the reader to
          // skim past both.
          <div
            className={t.adjust_severity === "critical" ? "hero-alert" : ""}
            style={t.adjust_severity === "critical" ? undefined : {
              marginTop: 14, paddingTop: 12,
              borderTop: "1px solid rgba(255,255,255,.22)",
            }}
          >
            <p>
              <strong>
                {t.adjust_severity === "critical"
                  ? "Do not train hard today. "
                  : "Why this changed. "}
              </strong>
              {t.adjust_reason}
            </p>
          </div>
        )}
      </div>


      {data.session_weather && <SessionWeather weather={data.session_weather} />}

      <SessionPlan steps={data.session_steps ?? []} targets={data.session_targets ?? []} />

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

        <DailyLogBox today={data.local_date} />
      </div>

      <WeekTable today={data.local_date} />

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
