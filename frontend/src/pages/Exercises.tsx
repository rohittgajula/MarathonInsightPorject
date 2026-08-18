import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { ExerciseAnimation } from "../components/ExerciseAnimation";
import { PrescriptionCard } from "../components/LogAdvice";
import type { ExerciseItem, ExerciseLibrary } from "../lib/types";

/* Strength, mobility and rehab work, browsable by what hurts.

   Opens on whatever the most recent log reported, because the person opening this
   page almost always has something specific in mind — and it is already known.
   The full catalogue is below that for the days when nothing hurts, which is when
   the maintenance work actually gets done. */

const KIND_ORDER = ["rehab", "activation", "mobility", "strength", "core", "drill"];

export default function Exercises() {
  const [area, setArea] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["exercises"],
    queryFn: () => api.get<ExerciseLibrary>("/exercises/"),
  });

  const focused = useQuery({
    queryKey: ["exercises", area],
    queryFn: () => api.get<ExerciseLibrary>(`/exercises/?area=${area}`),
    enabled: area !== null,
  });

  if (isLoading || !data) return <p className="muted">Loading…</p>;

  const shown = area ? focused.data?.prescriptions ?? [] : data.prescriptions;
  const byKind = KIND_ORDER.map((kind) => ({
    kind,
    label: data.kind_labels[kind] ?? kind,
    items: data.exercises.filter((e) => e.kind === kind),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="page stack">
      <div className="pagebar">
        <div>
          <h1>Strength and rehab</h1>
          <p className="faint" style={{ marginTop: 4 }}>
            What to do about the thing that is sore, and what to do twice a week so it
            does not come back.
          </p>
        </div>
      </div>

      <div className="card stack" style={{ gap: 12 }}>
        <div className="row split" style={{ justifyContent: "space-between" }}>
          <h2>{area ? "Picked by you" : "From your log"}</h2>
          {area && (
            <button className="ghost" onClick={() => setArea(null)}>Back to my log</button>
          )}
        </div>

        {!area && data.from_log && (
          <p className="faint">
            Most recent report, {data.from_log.date}: “{data.from_log.text}”
          </p>
        )}

        <div className="row" style={{ gap: 6 }}>
          {data.areas.map((a) => (
            <button
              key={a}
              className={`ghost area-pill${area === a ? " on" : ""}`}
              onClick={() => setArea(a === area ? null : a)}
            >
              {a.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        {shown.length === 0 && (
          <p className="muted">
            {area
              ? "Nothing catalogued for that area yet."
              : "Nothing sore reported recently — which is the point. The maintenance " +
                "routine below is what keeps it that way."}
          </p>
        )}
        {shown.map((p) => <PrescriptionCard key={p.area + p.severity} prescription={p} />)}
      </div>

      <div className="card stack" style={{ gap: 12 }}>
        <div>
          <h2>Twice a week, whatever is sore</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Hip abductors, calf capacity and trunk control — the three things that most
            often fail in a new runner, in about fifteen minutes.
          </p>
        </div>
        <div className="ex-list">
          {data.maintenance.map((e) => <ExerciseCard key={e.key} exercise={e} />)}
        </div>
      </div>

      {byKind.map((group) => (
        <div key={group.kind} className="card stack" style={{ gap: 12 }}>
          <h2>{group.label}</h2>
          <div className="ex-list">
            {group.items.map((e) => <ExerciseCard key={e.key} exercise={e} />)}
          </div>
        </div>
      ))}

      <div className="card">
        <p className="eyebrow">When to stop reading this page</p>
        <p className="muted" style={{ marginTop: 6 }}>{data.red_flags}</p>
      </div>
    </div>
  );
}

function ExerciseCard({ exercise: e }: { exercise: ExerciseItem }) {
  return (
    <div className="ex-card">
      <div className="row split" style={{ justifyContent: "space-between", gap: 10 }}>
        <h3 style={{ margin: 0 }}>{e.name}</h3>
        <span className="mono faint">{e.dose}</span>
      </div>
      <div className="row" style={{ gap: 5, marginTop: 6 }}>
        {e.areas.map((a) => (
          <span key={a} className="chip">{a.replace(/_/g, " ")}</span>
        ))}
        {e.acute && <span className="chip good">safe while sore</span>}
      </div>
      {/* The motion sits beside the words, as on the warm-up page: "draw the ball
          of the foot toward the heel" is a sentence people read twice and still
          get wrong. */}
      <div className="ex-row" style={{ marginTop: 8 }}>
        <ExerciseAnimation exerciseKey={e.key} />
        <div className="stack" style={{ gap: 6 }}>
          <p className="muted" style={{ margin: 0 }}>{e.why}</p>
          <p className="faint" style={{ margin: 0 }}>{e.how}</p>
          {e.caution && <p className="caution" style={{ margin: 0 }}>{e.caution}</p>}
        </div>
      </div>
    </div>
  );
}
