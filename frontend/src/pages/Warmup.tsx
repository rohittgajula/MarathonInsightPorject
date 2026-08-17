import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { BodyDiagram } from "../components/BodyDiagram";
import type { WarmupRoutine } from "../lib/types";

/* Hovering an exercise highlights the muscles it targets on the diagram, so "which
   bit does this actually work" is answered by looking rather than by reading. */

export function Warmup() {
  const [active, setActive] = useState<string[] | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["warmup"],
    queryFn: () => api.get<WarmupRoutine>("/warmup/"),
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!data) return <p className="error">Could not load the warm-up routine.</p>;

  const highlighted = active ?? [];

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div>
        <div className="eyebrow">Before every run · {data.total}</div>
        <h1>Warm-up</h1>
        <p className="muted" style={{ marginTop: 6, maxWidth: "62ch" }}>{data.intro}</p>
      </div>

      <div className="warmup-layout">
        <div className="card static stack" style={{ gap: 10, position: "sticky", top: 20, alignSelf: "start" }}>
          <div>
            <h2>Where it works</h2>
            <p className="faint" style={{ marginTop: 2 }}>
              {active ? "Highlighted for the exercise you are pointing at." : "Point at an exercise to see the muscles it targets."}
            </p>
          </div>
          <BodyDiagram highlighted={highlighted} labels={data.muscle_labels} />
          {highlighted.length > 0 && (
            <div className="row" style={{ gap: 7 }}>
              {highlighted.map((m) => (
                <span key={m} className="chip good">{data.muscle_labels[m] ?? m}</span>
              ))}
            </div>
          )}
        </div>

        <ol className="stack" style={{ gap: 12, listStyle: "none", padding: 0, margin: 0 }}>
          {data.exercises.map((e, i) => (
            <li
              key={e.key}
              className="card stack"
              style={{ gap: 8 }}
              onMouseEnter={() => setActive(e.muscles)}
              onFocus={() => setActive(e.muscles)}
              onMouseLeave={() => setActive(null)}
              tabIndex={0}
            >
              <div className="row split" style={{ justifyContent: "space-between" }}>
                <div className="row" style={{ gap: 10 }}>
                  <span className="step-num mono">{i + 1}</span>
                  <div>
                    <h2>{e.name}</h2>
                    <div className="faint">{e.primary}</div>
                  </div>
                </div>
                <span className="chip accent">{e.duration}</span>
              </div>

              <p style={{ fontSize: 13.5 }}><strong>How:</strong> {e.how}</p>
              <p className="faint" style={{ fontSize: 13 }}>{e.why}</p>

              <div className="row" style={{ gap: 6 }}>
                {e.muscles.map((m) => (
                  <span key={m} className="chip">{data.muscle_labels[m] ?? m}</span>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
