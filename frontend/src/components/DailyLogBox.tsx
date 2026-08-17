import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { DailyLog } from "../lib/types";

interface Paged<T> { results: T[]; }

/* Free-text entry, because a form with dropdowns for every food is a form nobody
   fills in by week three. The raw text is stored verbatim; the chips below show
   what was pulled out of it, so it is obvious when the extraction missed something. */

export function DailyLogBox() {
  const [text, setText] = useState("");
  const queryClient = useQueryClient();

  const logs = useQuery({
    queryKey: ["logs"],
    queryFn: () => api.get<Paged<DailyLog>>("/logs/"),
  });

  const save = useMutation({
    mutationFn: (body: { text: string }) => api.post<DailyLog>("/logs/", body),
    onSuccess: () => {
      setText("");
      queryClient.invalidateQueries({ queryKey: ["logs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const recent = logs.data?.results.slice(0, 4) ?? [];

  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div>
        <h2>Today's log</h2>
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
            {save.isPending ? "Saving…" : "Save entry"}
          </button>
        </div>
        {save.error && <p className="error" style={{ margin: 0 }}>{(save.error as Error).message}</p>}
      </form>

      {recent.length > 0 && (
        <div className="stack" style={{ gap: 9, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
          {recent.map((l) => (
            <div key={l.id} className="stack" style={{ gap: 4 }}>
              <div className="row" style={{ gap: 7 }}>
                <span className="faint mono">{l.log_date}</span>
                {l.alcohol_units != null && (
                  <span className="chip">{l.alcohol_units} {l.alcohol_units === 1 ? "unit" : "units"}</span>
                )}
                {l.sleep_hours != null && <span className="chip">{l.sleep_hours} h sleep</span>}
                {l.felt && <span className="chip">{l.felt}</span>}
              </div>
              <p style={{ fontSize: 13 }}>{l.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
