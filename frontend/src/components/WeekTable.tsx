import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { dateStr } from "../lib/format";
import type { CalendarResponse } from "../lib/types";

/* The week's schedule, navigable in both directions.

   Reads the calendar endpoint rather than the dashboard's fixed seven days, so
   stepping back to a finished week shows what was prescribed then — including any
   readiness adjustment that applied on the day. */

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mondayOf(d: Date) {
  const out = new Date(d);
  out.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return out;
}

export function WeekTable({ today }: { today: string }) {
  const [offset, setOffset] = useState(0);

  const start = mondayOf(new Date(today + "T00:00:00"));
  start.setDate(start.getDate() + offset * 7);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  const { data, isLoading } = useQuery({
    queryKey: ["weekTable", iso(start), iso(end)],
    queryFn: () => api.get<CalendarResponse>(`/calendar/?from=${iso(start)}&to=${iso(end)}`),
  });

  const label = offset === 0 ? "This week"
    : offset === -1 ? "Last week"
    : offset === 1 ? "Next week"
    : `${dateStr(iso(start)).replace(/,.*/, "")} – ${dateStr(iso(end)).replace(/,.*/, "")}`;

  return (
    <div className="card stack">
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>{label}</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            {dateStr(iso(start)).replace(/,.*/, "")} – {dateStr(iso(end)).replace(/,.*/, "")}
          </p>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="ghost" style={{ padding: "5px 11px" }}
                  onClick={() => setOffset(offset - 1)} aria-label="Previous week">←</button>
          {offset !== 0 && (
            <button className="ghost" style={{ padding: "5px 11px", fontSize: 12.5 }}
                    onClick={() => setOffset(0)}>This week</button>
          )}
          <button className="ghost" style={{ padding: "5px 11px" }}
                  onClick={() => setOffset(offset + 1)} aria-label="Next week">→</button>
        </div>
      </div>

      {isLoading && <p className="muted">Loading…</p>}

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Day</th><th>Session</th><th>Focus</th>
              <th>Target pace</th><th>Target HR</th>
              <th className="num">Run time</th><th className="num">Distance</th>
              <th className="num">Total</th>
            </tr>
          </thead>
          <tbody>
            {(data?.days ?? []).map((d) => {
              const p = d.planned;
              return (
                <tr key={d.date} style={d.is_today
                  ? { background: "var(--accent-soft)" } : undefined}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {new Date(d.date + "T00:00:00").toLocaleDateString(undefined,
                      { weekday: "short", day: "numeric", month: "short" })}
                    {d.activities.length > 0 && (
                      <span className="chip good" style={{ marginLeft: 7 }}>ran</span>
                    )}
                  </td>
                  <td>
                    {p?.title ?? "—"}
                    {p?.note && <span className="chip warn" style={{ marginLeft: 8 }}>{p.note}</span>}
                    {p?.adjusted && (
                      <span className={`chip ${p.adjust_severity === "critical" ? "warn" : "accent"}`}
                            style={{ marginLeft: 8 }} title={p.adjust_reason}>
                        {p.adjust_severity === "critical" ? "eased — low readiness" : "adjusted"}
                      </span>
                    )}
                  </td>
                  <td className="faint">{p?.focus || "—"}</td>
                  <td className="mono faint">{p?.target_pace || "—"}</td>
                  <td className="mono faint">{p?.target_hr || "—"}</td>
                  <td className="num mono">{p?.run_minutes ? `${p.run_minutes} min` : "—"}</td>
                  <td className="num mono">{p?.distance_km ? `${p.distance_km} km` : "—"}</td>
                  <td className="num mono">{p?.total_minutes ? `${p.total_minutes} min` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
