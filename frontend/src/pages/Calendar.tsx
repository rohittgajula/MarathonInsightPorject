import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DayNote } from "../components/DayNote";
import { WeekPlanner } from "../components/WeekPlanner";
import { durStr, paceStr } from "../lib/format";
import type { CalendarDay, CalendarResponse } from "../lib/types";

/* A month grid where each cell carries both halves of the story: what the plan asked
   for, and what actually happened. Past days lead with the outcome; future days lead
   with the prescription. */

const KIND_DOT: Record<string, string> = {
  intervals: "var(--run)", long: "var(--run)", race: "var(--warn)", rest: "var(--walk)",
};

const monthName = (d: Date) =>
  d.toLocaleDateString(undefined, { month: "long", year: "numeric" });

function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function Calendar() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [selected, setSelected] = useState<string | null>(null);

  // Pad to whole weeks so the grid never has a ragged first or last row.
  const gridStart = new Date(month);
  gridStart.setDate(1 - ((month.getDay() + 6) % 7));
  const gridEnd = new Date(gridStart);
  gridEnd.setDate(gridStart.getDate() + 41);

  const { data, isLoading } = useQuery({
    queryKey: ["calendar", iso(gridStart), iso(gridEnd)],
    queryFn: () => api.get<CalendarResponse>(`/calendar/?from=${iso(gridStart)}&to=${iso(gridEnd)}`),
  });

  const byDate = new Map((data?.days ?? []).map((d) => [d.date, d]));
  const day = selected ? byDate.get(selected) : null;

  const cells: Date[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    cells.push(d);
  }

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="eyebrow">Plan</div>
          <h1>Calendar</h1>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="ghost" onClick={() =>
            setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>←</button>
          <span className="mono" style={{ minWidth: 150, textAlign: "center" }}>{monthName(month)}</span>
          <button className="ghost" onClick={() =>
            setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>→</button>
          <button className="ghost" onClick={() => setMonth(startOfMonth(new Date()))}>Today</button>
        </div>
      </div>

      <WeekPlanner />

      <div className="card static">
        {isLoading && <p className="muted">Loading…</p>}
        <div className="cal-head">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div key={d} className="eyebrow" style={{ textAlign: "center" }}>{d}</div>
          ))}
        </div>
        <div className="cal-grid">
          {cells.map((d) => {
            const key = iso(d);
            const info = byDate.get(key);
            const outside = d.getMonth() !== month.getMonth();
            const planned = info?.planned;
            const done = info?.activities?.length ?? 0;
            return (
              <button
                key={key}
                className={[
                  "cal-cell",
                  outside ? "outside" : "",
                  info?.is_today ? "today" : "",
                  info?.is_race ? "race" : "",
                  selected === key ? "selected" : "",
                ].join(" ")}
                // Selecting opens the day panel. Jumping straight to the activity
                // would hide the plan, the adjustment reason and that day's sleep —
                // the panel is where the day is actually explained, and it offers the
                // link onward.
                onClick={() => setSelected(key)}
                title={planned?.adjusted ? planned.adjust_reason : undefined}
                aria-label={
                  `${key}${planned ? `, planned ${planned.title}` : ""}` +
                  (planned?.adjusted ? `. Adjusted: ${planned.adjust_reason}` : "") +
                  ((info?.activities?.length ?? 0) > 0 ? ". Has a recorded activity" : "")
                }
              >
                <span className="cal-num mono">{d.getDate()}</span>
                {planned && planned.kind !== "rest" && (
                  <span className="cal-dot" style={{ background: KIND_DOT[planned.kind] }} />
                )}
                {planned && (
                  <span className="cal-label">
                    {info?.is_race ? "RACE" :
                     planned.distance_km ? `${planned.distance_km} km` :
                     planned.run_minutes ? `${planned.run_minutes} min` : "rest"}
                  </span>
                )}
                {done > 0 && <span className="cal-done" title={`${done} recorded`} />}
                {planned?.adjusted && <span className="cal-adj">eased</span>}
              </button>
            );
          })}
        </div>
        <div className="legend" style={{ marginTop: 12 }}>
          <span><i className="sw" style={{ background: "var(--run)" }} /> Running session</span>
          <span><i className="sw" style={{ background: "var(--walk)" }} /> Rest or walk</span>
          <span><i className="sw" style={{ background: "var(--warn)" }} /> Race day</span>
          <span><i className="cal-done" style={{ position: "static", display: "inline-block" }} /> Recorded</span>
        </div>
      </div>

      {day && <DayDetail day={day} />}
    </div>
  );
}

function DayDetail({ day }: { day: CalendarDay }) {
  const p = day.planned;
  const dateLabel = new Date(day.date + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="eyebrow">{day.is_past ? "What happened" : "Planned"}</div>
          <h2 style={{ marginTop: 3 }}>{dateLabel}</h2>
        </div>
        {p && (
          <span className="chip accent">
            {p.plan_week ? `Week ${p.plan_week} · ${p.phase}` : p.phase}
          </span>
        )}
      </div>

      {p && (
        <div className="stack" style={{ gap: 8 }}>
          <div className="row" style={{ gap: 9 }}>
            <strong style={{ fontSize: 15 }}>{p.title}</strong>
            {p.note && <span className="chip warn">{p.note}</span>}
            {p.adjusted && <span className="chip accent">adjusted</span>}
          </div>
          <p style={{ fontSize: 13.5 }}>{p.detail}</p>
          {/* Why this day is off the template. A recovery day and a rest day are
              the same `kind`, and without this the calendar cannot tell them
              apart — nor can the person reading it. */}
          {p.mode && p.mode !== "build" && p.mode !== "race" && p.mode_reason && (
            <div className="adjust-note">
              <span className="eyebrow">Why this day</span>
              <p>{p.mode_reason}</p>
            </div>
          )}
          {p.adjusted && (
            <div className={`adjust-note ${p.adjust_severity === "critical" ? "critical" : ""}`}>
              <span className="eyebrow">
                {p.adjust_severity === "critical" ? "⚠ Do not train hard today" : "Why this changed"}
              </span>
              <p>{p.adjust_reason}</p>
            </div>
          )}
          <div className="grid">
            {p.target_pace && <Mini k="Target pace" v={p.target_pace} />}
            {p.target_hr && <Mini k="Target HR" v={p.target_hr} />}
            {p.run_minutes > 0 && <Mini k="Running" v={`${p.run_minutes} min`} />}
            {p.distance_km > 0 && <Mini k="Distance" v={`${p.distance_km} km`} />}
          </div>
        </div>
      )}

      {day.activities.length > 0 && (
        <div className="stack" style={{ gap: 8, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
          <div className="eyebrow">Recorded</div>
          {day.activities.map((a) => (
            <Link key={a.id} to={`/activity/${a.id}`} className="activity-link">
              <span className="row" style={{ gap: 12 }}>
                <span className="chip">{a.sport}</span>
                <span className="mono">{a.distance_km} km</span>
                <span className="mono faint">{durStr(a.duration_s)}</span>
                {a.run_blocks ? (
                  <>
                    <span className="mono faint">{a.run_blocks} blocks</span>
                    <span className="mono faint">longest {durStr(a.longest_run_s)}</span>
                    <span className="mono faint">{paceStr(a.avg_run_pace_s)}/km</span>
                  </>
                ) : null}
              </span>
              <span className="open-cue">Open activity →</span>
            </Link>
          ))}
        </div>
      )}

      {(day.wellness || day.log) && (
        <div className="stack" style={{ gap: 6, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
          <div className="eyebrow">That day</div>
          {day.wellness && (
            <div className="row" style={{ gap: 16 }}>
              {day.wellness.sleep_hours != null && (
                <span className="faint">
                  Slept <b className="mono" style={{ color: "var(--ink)" }}>{day.wellness.sleep_hours} h</b>
                  {/* The hours alone are ambiguous about which night is meant, and this
                      athlete's sleep often starts after midnight. */}
                  {day.wellness.sleep_window && (
                    <span className="mono"> ({day.wellness.sleep_window})</span>
                  )}
                </span>
              )}
              {day.wellness.sleep_score != null && (
                <span className="faint">Sleep score <b className="mono" style={{ color: "var(--ink)" }}>{day.wellness.sleep_score}</b></span>
              )}
              {day.wellness.training_readiness != null && (
                <span className="faint">Readiness <b className="mono" style={{ color: "var(--ink)" }}>{day.wellness.training_readiness}</b></span>
              )}
              {day.wellness.resting_hr != null && (
                <span className="faint">Resting HR <b className="mono" style={{ color: "var(--ink)" }}>{day.wellness.resting_hr}</b></span>
              )}
            </div>
          )}
          {day.log && <p style={{ fontSize: 13 }}>{day.log.text}</p>}
        </div>
      )}

      {!p && day.activities.length === 0 && (
        <p className="faint">Nothing planned or recorded for this day.</p>
      )}

      <DayNote date={day.date} existing={day.log} />
    </div>
  );
}

function Mini({ k, v }: { k: string; v: string }) {
  return (
    <div className="side-card">
      <div className="eyebrow">{k}</div>
      <div className="mono" style={{ fontSize: 15, marginTop: 3 }}>{v}</div>
    </div>
  );
}
