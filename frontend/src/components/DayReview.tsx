import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { durStr, paceStr } from "../lib/format";
import type { DayReviewResponse, DayState } from "../lib/types";

/* One day, opened from the week table.

   The table can only show the prescription — target pace, target HR, the distance
   the plan asked for. This is the other half: what the watch actually recorded
   against it, and the one or two things worth changing next time.

   Built on the native <dialog> so focus trapping, Esc and inert-background come from
   the platform rather than from a hand-rolled approximation of them. */

const STATE_LABEL: Record<DayState, { text: string; chip: string }> = {
  done: { text: "session recorded", chip: "good" },
  partial: { text: "recorded, but not run", chip: "warn" },
  missed: { text: "nothing recorded", chip: "warn" },
  moved: { text: "moved within the week", chip: "" },
  rest: { text: "rest day", chip: "" },
  extra: { text: "ran on a rest day", chip: "warn" },
  upcoming: { text: "not yet run", chip: "accent" },
  before_plan: { text: "before the plan", chip: "" },
};

function longDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

export function DayReview({ date, onClose }: { date: string | null; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dayReview", date],
    queryFn: () => api.get<DayReviewResponse>(`/day-review/?date=${date}`),
    enabled: date !== null,
  });

  // Kept in a ref so the listener below can be attached once per open rather than
  // re-attached on every render by an inline callback's changing identity.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  // showModal() rather than the `open` attribute: only the former gives the top
  // layer, the ::backdrop, the focus trap and Esc-to-close.
  //
  // Both listeners are attached by hand rather than as onClose/onCancel props,
  // because those events do not bubble and React 18 wires neither — as JSX props
  // they would fire never, leaving Esc to dismiss the dialog while the state that
  // owns it still read "open", so the same row would not reopen.
  //
  // Esc is handled on keydown rather than left to the `close` event alone: the
  // platform still closes the dialog itself, and both paths land on the same state,
  // but this one does not depend on an event some renderers never dispatch.
  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    if (!node.open) node.showModal();

    const closed = () => closeRef.current();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") closeRef.current(); };
    node.addEventListener("close", closed);
    node.addEventListener("keydown", key);
    return () => {
      node.removeEventListener("close", closed);
      node.removeEventListener("keydown", key);
    };
  }, [date]);

  if (!date) return null;

  const state = data ? STATE_LABEL[data.state] : null;

  return (
    <dialog
      ref={dialogRef}
      className="modal"
      aria-labelledby="day-review-title"
      /* The dialog element is the full-viewport box; its visible panel is the child.
         A click landing on the element itself is therefore a click on the backdrop. */
      onClick={(e) => { if (e.target === dialogRef.current) onClose(); }}
    >
      <div className="modal-panel">
        <header className="modal-head">
          <div style={{ minWidth: 0 }}>
            <p className="eyebrow">
              {data?.planned?.plan_week && !data.planned.before_plan
                ? `Week ${data.planned.plan_week} · ${data.planned.phase}`
                : data?.planned?.phase && data.planned.mode !== "build"
                  ? data.planned.phase
                  : "Training day"}
            </p>
            <h2 id="day-review-title">{longDate(date)}</h2>
          </div>
          <button className="ghost modal-close" onClick={onClose} aria-label="Close">✕</button>
        </header>

        {isLoading && <p className="muted">Loading the day…</p>}
        {isError && <p className="error">Could not load this day.</p>}

        {data && (
          <div className="stack" style={{ gap: 18 }}>
            <div>
              <div className="row" style={{ gap: 9, marginBottom: 6 }}>
                <strong style={{ fontSize: 15.5 }}>{data.planned?.title ?? "No session"}</strong>
                {state && <span className={`chip ${state.chip}`}>{state.text}</span>}
              </div>
              <p className="muted" style={{ fontSize: 13.5 }}>{data.summary}</p>
            </div>

            {data.planned?.adjusted && (
              <div className={`adjust-note ${data.planned.adjust_severity === "critical" ? "critical" : ""}`}>
                <p className="eyebrow">Eased on the day</p>
                <p>{data.planned.adjust_reason}</p>
              </div>
            )}

            {data.rows.length > 0 && (
              <section>
                <h3 style={{ marginBottom: 9 }}>Planned against actual</h3>
                <div className="scroll">
                  <table className="review-table">
                    <thead>
                      <tr>
                        <th>Metric</th><th>Planned</th><th>Actual</th><th>Difference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((r) => (
                        <tr key={r.key}>
                          <td>
                            {r.label}
                            {r.note && <span className="faint row-note">{r.note}</span>}
                          </td>
                          <td className="mono faint">{r.planned}</td>
                          {/* The verdict rides on the actual value, which is the one
                              being judged — and on a word, never on colour alone. */}
                          <td className={`mono val-${r.tone}`}>{r.actual}</td>
                          <td className="mono faint">{r.delta || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {data.suggestions.length > 0 && (
              <section>
                <h3 style={{ marginBottom: 4 }}>What to take from it</h3>
                {data.suggestions.map((s, i) => (
                  <div key={i} className={`insight ${s.tone}`}>
                    <span className="stripe" />
                    <div>
                      <h3>{s.headline}</h3>
                      <p className="muted">{s.detail}</p>
                    </div>
                  </div>
                ))}
              </section>
            )}

            {(data.wellness || data.log) && (
              <section>
                <h3 style={{ marginBottom: 9 }}>How the day looked</h3>
                <div className="grid">
                  {data.wellness?.sleep_hours != null && (
                    <Fact label="Slept" value={`${data.wellness.sleep_hours} h`}
                          sub={data.wellness.sleep_window} />
                  )}
                  {data.wellness?.training_readiness != null && (
                    <Fact label="Readiness" value={`${data.wellness.training_readiness}/100`} />
                  )}
                  {data.wellness?.resting_hr != null && (
                    <Fact label="Resting HR" value={`${data.wellness.resting_hr} bpm`} />
                  )}
                  {data.wellness?.sleep_score != null && (
                    <Fact label="Sleep score" value={`${data.wellness.sleep_score}`} />
                  )}
                </div>
                {data.log && (
                  <p className="muted" style={{ marginTop: 11, fontSize: 13.5 }}>
                    <span className="faint">You wrote: </span>“{data.log.text}”
                  </p>
                )}
              </section>
            )}

            {data.activities.map((a) => (
              <Link key={a.id} to={`/activity/${a.id}`} className="activity-link" onClick={onClose}>
                <span>
                  <strong>{a.distance_km.toFixed(2)} km</strong>
                  <span className="faint"> · {durStr(a.duration_s)}</span>
                  {a.avg_run_pace_s && (
                    <span className="faint"> · {paceStr(a.avg_run_pace_s)}/km running</span>
                  )}
                  {a.place_name && <span className="faint"> · {a.place_name}</span>}
                </span>
                <span className="open-cue">Open the full session →</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </dialog>
  );
}

function Fact({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="side-card">
      <p className="eyebrow">{label}</p>
      <p className="mono" style={{ fontSize: 17, fontWeight: 650 }}>{value}</p>
      {sub && <p className="faint">{sub}</p>}
    </div>
  );
}
