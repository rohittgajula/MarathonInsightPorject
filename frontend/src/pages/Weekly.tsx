import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { NiggleTracker } from "../components/NiggleTracker";
import { dateStr, durStr } from "../lib/format";
import type { WeekReview, WeeklyResponse } from "../lib/types";

/* The decision the plan actually turns on: hold, repeat, or progress.

   Sessions are counted rather than calendar slots matched — running three times on
   days that suit you is a completed week, and day-matching would have scored a
   Monday run as zero purely because Monday is written as rest. */

const VERDICT: Record<string, { label: string; tone: string }> = {
  progress: { label: "Progress", tone: "good" },
  hold: { label: "Hold here", tone: "warn" },
  repeat: { label: "Repeat the week", tone: "warn" },
  in_progress: { label: "In progress", tone: "accent" },
  before_plan: { label: "Before the plan", tone: "" },
  none: { label: "No plan", tone: "" },
};

function Stat({ label, actual, planned, unit }: {
  label: string; actual: string; planned?: string; unit?: string;
}) {
  return (
    <div className="side-card">
      <div className="eyebrow">{label}</div>
      <div className="mono" style={{ fontSize: 16, marginTop: 3 }}>
        {actual}{unit}
        {planned && <span className="faint" style={{ fontSize: 12 }}> / {planned}{unit}</span>}
      </div>
    </div>
  );
}

function Week({ week }: { week: WeekReview }) {
  const v = VERDICT[week.verdict] ?? VERDICT.none;
  const grew = week.longest_run_s > week.previous_longest_run_s && week.longest_run_s > 0;

  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="eyebrow">
            {dateStr(week.start).replace(/,.*/, "")} – {dateStr(week.end).replace(/,.*/, "")}
            {week.plan_week ? ` · week ${week.plan_week} of 17 · ${week.phase}` : ` · ${week.phase}`}
          </div>
          <h2 style={{ marginTop: 3 }}>
            {week.before_plan
              ? week.actual_distance_km > 0
                ? `${week.actual_distance_km} km run`
                : "No runs recorded"
              : `${week.completed_sessions} of ${week.planned_sessions} sessions`}
          </h2>
        </div>
        <span className={`chip ${v.tone}`}>{v.label}</span>
      </div>

      <p style={{ fontSize: 13.5 }}>{week.verdict_reason}</p>

      <div className="grid">
        <Stat label="Running time" actual={`${week.actual_run_minutes}`}
              planned={week.before_plan ? undefined : `${week.planned_run_minutes}`} unit=" min" />
        <Stat label="Distance" actual={`${week.actual_distance_km}`}
              planned={!week.before_plan && week.planned_distance_km
                ? `${week.planned_distance_km}` : undefined} unit=" km" />
        <Stat label="Longest unbroken"
              actual={week.longest_run_s ? durStr(week.longest_run_s) : "—"} />
        <Stat label="Pace discipline"
              actual={week.pace_discipline_pct != null ? `${week.pace_discipline_pct.toFixed(0)}%` : "—"} />
        {week.avg_sleep_h != null && <Stat label="Avg sleep" actual={`${week.avg_sleep_h}`} unit=" h" />}
        {week.sleep_debt_h != null && <Stat label="Sleep debt" actual={`${week.sleep_debt_h}`} unit=" h" />}
      </div>

      {grew && (
        <p className="faint" style={{ color: "var(--good)" }}>
          Longest unbroken run grew from {durStr(week.previous_longest_run_s)} to{" "}
          {durStr(week.longest_run_s)} — the number that matters most.
        </p>
      )}

      {week.off_plan_days.length > 0 && (
        <p className="faint">
          Ran on {week.off_plan_days.map((d) => dateStr(d).replace(/,.*/, "")).join(", ")},
          which the plan had as rest. Counted — the work is what matters, not the day.
        </p>
      )}

      {!week.before_plan && (
      <div className="week-strip">
        {week.days.map((d) => (
          <div key={d.date}
               className={`strip-day ${d.done ? "done" : ""} ${d.prescribed ? "prescribed" : ""}`}
               title={`${d.date}: ${d.planned}`}>
            <span className="eyebrow">
              {new Date(d.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "narrow" })}
            </span>
            <span className="strip-mark">{d.done ? "✓" : d.prescribed ? "·" : ""}</span>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}

export function Weekly() {
  const { data, isLoading } = useQuery({
    queryKey: ["weekly"],
    queryFn: () => api.get<WeeklyResponse>("/weekly/"),
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!data) return <p className="error">Could not load the weekly review.</p>;

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div>
        <div className="eyebrow">Planned against actual</div>
        <h1>Weekly review</h1>
        <p className="muted" style={{ marginTop: 6, maxWidth: "64ch" }}>
          The plan advances on the calendar whether or not the work happened. This is
          where that gets checked — and where the decision to hold, repeat or move on
          actually lives.
        </p>
      </div>

      <NiggleTracker />

      {data.weeks.map((w) => <Week key={w.start} week={w} />)}
    </div>
  );
}
