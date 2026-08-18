import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { DailyLog } from "../lib/types";

interface Paged<T> { results: T[]; }

/* Free-text entry, because a form with dropdowns for every food is a form nobody
   fills in by week three. The raw text is stored verbatim; the chips below show
   what was pulled out of it, so it is obvious when the extraction missed something. */

export function DailyLogBox({ today }: { today?: string }) {
  const [text, setText] = useState("");
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const logs = useQuery({
    queryKey: ["logs"],
    queryFn: () => api.get<Paged<DailyLog>>("/logs/"),
  });

  const save = useMutation({
    mutationFn: (body: { text: string }) =>
      api.post<DailyLog>("/logs/", { ...body, log_date: todayDate }),
    onSuccess: () => {
      setText("");
      invalidateTrainingData(queryClient);
    },
  });

  // The date comes from the server, in the athlete's timezone — the browser clock
  // and the configured timezone can disagree either side of midnight.
  const todayDate = today ?? new Date().toISOString().slice(0, 10);
  const all = logs.data?.results ?? [];
  const todaysLog = all.find((l) => l.log_date === todayDate) ?? null;
  const earlier = all.filter((l) => l.log_date !== todayDate).slice(0, 4);

  // Prefill today's entry so "Save entry" edits it rather than appearing to do
  // nothing. Only once per date, so it never fights what is being typed.
  if (todaysLog && loadedFor !== todayDate && text === "") {
    setLoadedFor(todayDate);
    setText(todaysLog.text);
  }

  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div>
        <h2>{todaysLog ? "Today's log" : "Log today"}</h2>
        <p className="faint" style={{ marginTop: 2 }}>
          What you ate and drank, how you slept, how you feel. Plain sentences are fine.
        </p>
      </div>

      <form
        className="stack" style={{ gap: 9 }}
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) save.mutate({ text: text.trim() }); }}
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. two beers and biryani last night, slept 5.5 hours, legs feel heavy"
        />
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="faint">
            Sleep, alcohol and mood are picked out automatically.
          </span>
          <button type="submit" disabled={save.isPending || !text.trim()}>
            {save.isPending ? "Saving…" : todaysLog ? "Update today's entry" : "Save entry"}
          </button>
        </div>
        {save.error && <p className="error" style={{ margin: 0 }}>{(save.error as Error).message}</p>}
      </form>

      {todaysLog && (
        <div className="row" style={{ gap: 7 }}>
          {(todaysLog.detected ?? []).map((d) => (
            <span key={d} className="chip good">{d}</span>
          ))}
          {(todaysLog.detected ?? []).length === 0 && (
            <span className="chip warn">nothing detected</span>
          )}
        </div>
      )}

      {earlier.length > 0 && (
        <div className="stack" style={{ gap: 9, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
          <div className="eyebrow">Earlier entries</div>
          {earlier.map((l) => (
            <div key={l.id} className="stack" style={{ gap: 4 }}>
              <div className="row" style={{ gap: 7 }}>
                <span className="faint mono">{l.log_date}</span>
                {(l.detected ?? []).map((d) => (
                  <span key={d} className="chip good">{d}</span>
                ))}
                {(l.detected ?? []).length === 0 && (
                  // Silence used to look identical to the feature being broken.
                  <span className="chip warn">nothing detected</span>
                )}
              </div>
              <p style={{ fontSize: 13 }}>{l.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
