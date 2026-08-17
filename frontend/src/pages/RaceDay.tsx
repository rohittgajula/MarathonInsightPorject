import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { dateStr } from "../lib/format";
import type { RacePlan } from "../lib/types";

/* A race plan in numbers rather than sentiment.

   "Start slow and take the water" is correct and useless at kilometre 6. This gives
   the pace to hold, the walk schedule, what each split should read, and what to do
   when it goes wrong — decided now, when it is easy to think. */

export function RaceDay() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["racePlan"],
    queryFn: () => api.get<RacePlan>("/race-plan/"),
    retry: false,
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (error || !data) {
    return (
      <div className="card">
        <p className="muted">Set a target race first and the plan builds itself around it.</p>
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="hero">
        <div className="row split" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div className="eyebrow">{dateStr(data.race_date)}</div>
            <h1>{data.race_name}</h1>
            <p>{data.goal}</p>
          </div>
          <span className="hero-badge mono">{data.distance_km} km</span>
        </div>
      </div>

      <div className="grid">
        <div className="card tile">
          <div className="k">Target pace</div>
          <div className="v mono">{data.target_pace}</div>
          <div className="n">The slow edge of your easy band — not faster.</div>
        </div>
        <div className="card tile">
          <div className="k">First kilometre</div>
          <div className="v mono">{data.opening_pace}</div>
          <div className="n">Slower again. It will feel far too easy; that is correct.</div>
        </div>
        <div className="card tile">
          <div className="k">Expected finish</div>
          <div className="v mono">{data.estimated_finish}</div>
          <div className="n">Irrelevant to the goal, useful for planning the day.</div>
        </div>
        <div className="card tile">
          <div className="k">Walk when above</div>
          <div className="v mono warn">{data.hr_ceiling} bpm</div>
          <div className="n">The same ceiling you train with.</div>
        </div>
      </div>

      <div className="card stack" style={{ gap: 8 }}>
        <h2>The walk plan</h2>
        <p style={{ fontSize: 14 }}><strong>{data.walk_plan.pattern}</strong></p>
        <p className="faint">{data.walk_plan.why}</p>
      </div>

      <div className="card stack">
        <h2>Kilometre by kilometre</h2>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Km</th><th className="num">Target</th><th className="num">Elapsed</th><th>What to think about</th></tr>
            </thead>
            <tbody>
              {data.splits.map((s) => (
                <tr key={s.km}>
                  <td className="mono">{s.km}</td>
                  <td className="num mono">{s.target_pace}</td>
                  <td className="num mono">{s.cumulative}</td>
                  <td>{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-2">
        <div className="card stack" style={{ gap: 10 }}>
          <h2>Before the start</h2>
          <div className="stack" style={{ gap: 0 }}>
            {data.before.map((row) => (
              <div key={row.when} className="target-row">
                <strong style={{ fontSize: 13.5 }}>{row.when}</strong>
                <p style={{ fontSize: 13, marginTop: 3 }}>{row.do}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card stack" style={{ gap: 10 }}>
          <h2>If it goes wrong</h2>
          <div className="stack" style={{ gap: 0 }}>
            {data.if_it_goes_wrong.map((row) => (
              <div key={row.problem} className="target-row">
                <strong style={{ fontSize: 13.5 }}>{row.problem}</strong>
                <p style={{ fontSize: 13, marginTop: 3 }}>{row.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
