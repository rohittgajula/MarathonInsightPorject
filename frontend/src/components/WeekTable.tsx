import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";
import { api } from "../api/client";
import type { CalendarResponse } from "../lib/types";
import { DayReview } from "./DayReview";

/* The week's schedule, navigable in both directions.

   Reads the calendar endpoint rather than the dashboard's fixed seven days, so
   stepping back to a finished week shows what was prescribed then — including any
   readiness adjustment that applied on the day.

   Three things keep stepping between weeks from lurching, all of which are about
   removing layout changes rather than adding motion:

   - keepPreviousData holds the old week on screen while the next one loads. Without
     it the table empties, collapses to its 540px min-width, and springs back.
   - The columns are fixed by a colgroup instead of being sized from their contents,
     so a week containing "Easy walk — 25–30 min (instead of intervals)" does not
     lay out differently from a week of short titles.
   - The "This week" button keeps its space when it is not shown, so the arrows stay
     put rather than sliding sideways when it appears.

   Every row shows the prescription and nothing else, which is the whole of what the
   plan knows. Clicking one opens the other half — what was actually recorded. */

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mondayOf(d: Date) {
  const out = new Date(d);
  out.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return out;
}

/* "Aug 17 – 23", or "Jul 27 – Aug 2" when the week straddles two months.

   This replaces stripping everything after the first comma of a formatted date,
   which left "Mon" and "Sun" — so the subtitle read "Mon – Sun" on every week, and
   any week more than one step from today carried no date at all.

   formatRange rather than two formatted dates joined by a dash: it drops the
   repeated month itself and, more to the point, knows where the locale puts it.
   Composing the halves by hand produced "17 – Aug 23". */
const RANGE_FMT = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
function rangeLabel(start: Date, end: Date) {
  return RANGE_FMT.formatRange(start, end);
}

export function WeekTable({ today }: { today: string }) {
  const [offset, setOffset] = useState(0);
  const [openDay, setOpenDay] = useState<string | null>(null);

  const start = mondayOf(new Date(today + "T00:00:00"));
  start.setDate(start.getDate() + offset * 7);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  const { data, isFetching, isLoading } = useQuery({
    queryKey: ["weekTable", iso(start), iso(end)],
    queryFn: () => api.get<CalendarResponse>(`/calendar/?from=${iso(start)}&to=${iso(end)}`),
    placeholderData: keepPreviousData,
  });

  const range = rangeLabel(start, end);
  const label = offset === 0 ? "This week"
    : offset === -1 ? "Last week"
    : offset === 1 ? "Next week"
    : range;

  // Keyed on the week the rows actually belong to, not on `offset`. Re-running the
  // entry animation the moment a button is pressed would animate the outgoing week
  // back in, then swap its contents underneath — two movements for one step.
  const shownWeek = data?.from ?? "initial";

  return (
    <div className="card stack">
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>{label}</h2>
          {/* Never a bare repeat of the heading: on a far-off week the heading is
              already the range, and the year is what that week actually lacks. */}
          <p className="faint" style={{ marginTop: 2 }}>
            {label === range ? start.getFullYear() : range}
          </p>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="ghost" style={{ padding: "5px 11px" }}
                  onClick={() => setOffset(offset - 1)} aria-label="Previous week">←</button>
          {/* Held in the layout when hidden, so the arrows do not jump. */}
          <button className={`ghost${offset === 0 ? " held" : ""}`}
                  style={{ padding: "5px 11px", fontSize: 12.5 }}
                  onClick={() => setOffset(0)}
                  aria-hidden={offset === 0}
                  tabIndex={offset === 0 ? -1 : 0}>This week</button>
          <button className="ghost" style={{ padding: "5px 11px" }}
                  onClick={() => setOffset(offset + 1)} aria-label="Next week">→</button>
        </div>
      </div>

      <div className="scroll">
        {/* aria-busy rather than a "Loading…" line: text inserted above the table
            pushes it down and back, which is the jump this is trying to remove. */}
        <table className="week-table" aria-busy={isFetching}
               data-loading={isFetching && !isLoading ? "" : undefined}>
          {/* Fixed pixels rather than percentages, measured from the widest thing each
              column actually has to hold — the "DISTANCE" heading, "optional walk,
              easy", "130–145 bpm". Percentages looked tidier and clipped all three at
              real window sizes. Session is the one left to size itself, so the spare
              width lands in the only column whose text genuinely varies. */}
          <colgroup>
            <col style={{ width: 140 }} /><col />
            <col style={{ width: 100 }} /><col style={{ width: 156 }} />
            <col style={{ width: 120 }} /><col style={{ width: 102 }} />
            <col style={{ width: 104 }} /><col style={{ width: 80 }} />
          </colgroup>
          <thead>
            <tr>
              <th>Day</th><th>Session</th><th>Focus</th>
              <th>Target pace</th><th>Target HR</th>
              <th className="num">Run time</th><th className="num">Distance</th>
              <th className="num">Total</th>
            </tr>
          </thead>
          <tbody key={shownWeek}>
            {isLoading && Array.from({ length: 7 }, (_, i) => (
              <tr key={i} className="week-row" style={{ "--i": i } as CSSProperties}>
                <td colSpan={8}><span className="skeleton" /></td>
              </tr>
            ))}
            {(data?.days ?? []).map((d, i) => {
              const p = d.planned;
              return (
                <tr key={d.date}
                    className={`week-row clickable${d.is_today ? " is-today" : ""}`}
                    style={{ "--i": i } as CSSProperties}
                    onClick={() => setOpenDay(d.date)}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {/* A real button so the row is reachable by keyboard, without
                        putting a button role on a <tr> and breaking the table for
                        anyone reading it with a screen reader. */}
                    <button
                      className="day-open"
                      onClick={(e) => { e.stopPropagation(); setOpenDay(d.date); }}
                      aria-label={`Review ${d.date}${p ? `: ${p.title}` : ""}`}
                    >
                      {new Date(d.date + "T00:00:00").toLocaleDateString(undefined,
                        { weekday: "short", day: "numeric", month: "short" })}
                    </button>
                    {d.activities.length > 0 && (
                      <span className="chip good" style={{ marginLeft: 7 }}>ran</span>
                    )}
                  </td>
                  <td>
                    {p?.title ?? "—"}
                    {/* The targets on a rest day are real but not owed. Without this
                        the row is indistinguishable from a prescribed walk. */}
                    {p?.optional && (
                      <span className="chip" style={{ marginLeft: 8 }}>optional</span>
                    )}
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

      <p className="faint" style={{ margin: 0 }}>
        These are the targets for each day. Open a day to see what was actually recorded against them.
      </p>

      <DayReview date={openDay} onClose={() => setOpenDay(null)} />
    </div>
  );
}
