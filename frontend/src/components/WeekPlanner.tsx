import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { Athlete } from "../lib/types";

/* Pick what each weekday is for. Changing this regenerates every planned date, so it
   invalidates the whole derived layer on save. */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ORDER = ["rest", "walk", "cross", "jog", "intervals", "long"];

const TONE: Record<string, string> = {
  rest: "var(--walk)", walk: "var(--walk)", cross: "var(--walk)",
  jog: "var(--run)", intervals: "var(--run)", long: "var(--run)",
};

export function WeekPlanner() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const athlete = useQuery({
    queryKey: ["athlete"],
    queryFn: () => api.get<Athlete>("/athletes/me/"),
  });

  const save = useMutation({
    mutationFn: (training_days: Record<string, string>) =>
      api.patch<Athlete>("/athletes/me/", { training_days }),
    onSuccess: () => {
      invalidateTrainingData(queryClient);
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      setDraft(null);
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  if (!athlete.data) return null;
  const labels = athlete.data.day_type_labels ?? {};
  const current = draft ?? athlete.data.training_days;
  const runningDays = Object.values(current).filter((v) =>
    ["jog", "intervals", "long"].includes(v)).length;
  const dirty = draft !== null;

  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Your training week</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Set what each day is for. The whole plan regenerates around it.
          </p>
        </div>
        <span className={`chip ${runningDays > 4 ? "warn" : runningDays >= 3 ? "good" : ""}`}>
          {runningDays} running {runningDays === 1 ? "day" : "days"}/week
        </span>
      </div>

      <div className="week-grid">
        {DAYS.map((label, i) => (
          <div key={label} className="week-day">
            <div className="eyebrow" style={{ textAlign: "center" }}>{label}</div>
            <select
              value={current[String(i)] ?? "rest"}
              onChange={(e) => setDraft({ ...current, [String(i)]: e.target.value })}
              style={{ borderLeft: `3px solid ${TONE[current[String(i)] ?? "rest"]}` }}
            >
              {ORDER.map((t) => (
                <option key={t} value={t}>{labels[t] ?? t}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {runningDays > 4 && (
        <p className="faint" style={{ color: "var(--warn)" }}>
          More than four running days while building a base is how most first training
          blocks end. New runners are injured by frequency far more often than by distance.
        </p>
      )}
      {runningDays < 3 && (
        <p className="faint">
          The plan is written around three running days. Fewer still holds fitness, but
          it builds it more slowly.
        </p>
      )}
      {error && <p className="error" style={{ margin: 0 }}>{error}</p>}

      {dirty && (
        <div className="row">
          <button onClick={() => save.mutate(current)} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save week"}
          </button>
          <button className="ghost" onClick={() => { setDraft(null); setError(null); }}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
