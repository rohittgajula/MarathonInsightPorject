import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { DailyLog } from "../lib/types";
import { LogAdviceBlock } from "./LogAdvice";

interface Paged<T> { results: T[]; }

/* Free-text entry, because a form with dropdowns for every food is a form nobody
   fills in by week three. The raw text is stored verbatim; the chips below show
   what was pulled out of it, so it is obvious when the extraction missed something. */

export function DailyLogBox({ today }: { today?: string }) {
  const [text, setText] = useState("");
  const [justSaved, setJustSaved] = useState(false);
  const queryClient = useQueryClient();

  const logs = useQuery({
    queryKey: ["logs"],
    queryFn: () => api.get<Paged<DailyLog>>("/logs/"),
    // Claude reads the entry in a background task, so the row arrives `pending` and
    // fills in a few seconds later. Polling only while something is actually pending
    // keeps this from becoming a permanent timer on the dashboard.
    refetchInterval: (query) => {
      const rows = query.state.data?.results ?? [];
      // Only `pending` resolves in seconds. `rate_limited` is fixed by the
      // scheduled sweep minutes later, so polling for it would spin pointlessly.
      return rows.some((l) => l.ai_status === "pending") ? 2500 : false;
    },
  });

  const save = useMutation({
    mutationFn: (body: { text: string }) =>
      api.post<DailyLog>("/logs/", { ...body, log_date: todayDate }),
    onSuccess: () => {
      // Cleared, because the box adds to the day rather than replacing it. The saved
      // text appears below immediately, so an empty box never looks like a failed
      // save — which was the reason it used to refill itself.
      setText("");
      setJustSaved(true);
      window.setTimeout(() => setJustSaved(false), 2500);
      invalidateTrainingData(queryClient);
    },
  });

  // The date comes from the server, in the athlete's timezone — the browser clock
  // and the configured timezone can disagree either side of midnight.
  const todayDate = today ?? new Date().toISOString().slice(0, 10);
  const all = logs.data?.results ?? [];
  const todaysLog = all.find((l) => l.log_date === todayDate) ?? null;
  const earlier = all.filter((l) => l.log_date !== todayDate).slice(0, 4);

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
          placeholder={todaysLog
            ? "Add another note — how the run went, what you ate, how you feel now"
            : "e.g. two beers and biryani last night, slept 5.5 hours, legs feel heavy"}
        />
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="faint">
            Sleep, food, alcohol, pain and mood are read out of the sentence — including
            whether you are writing about today or tomorrow.
          </span>
          <div className="row" style={{ gap: 8 }}>
            {justSaved && <span className="chip good">Saved</span>}
            <button type="submit" disabled={save.isPending || !text.trim()}>
              {save.isPending ? "Saving…" : todaysLog ? "Add to today's log" : "Save entry"}
            </button>
          </div>
        </div>
        {save.error && <p className="error" style={{ margin: 0 }}>{(save.error as Error).message}</p>}
      </form>

      {todaysLog && (
        <>
          <div className="row" style={{ gap: 7 }}>
            <span className="faint mono">
              {todaysLog.log_date}
              {todaysLog.logged_at && ` · written ${todaysLog.logged_at}`}
            </span>
            {/* The whole point of asking which day an entry is about: say so when
                the answer is not the day it was typed. */}
            {todaysLog.applies_to_date && todaysLog.applies_to_date !== todaysLog.log_date && (
              <span className="chip accent" title={todaysLog.applies_to_reason}>
                counted as {todaysLog.applies_to_date}
              </span>
            )}
            {(todaysLog.detected ?? []).map((d) => (
              <span key={d} className="chip good">{d}</span>
            ))}
            {(todaysLog.detected ?? []).length === 0 && todaysLog.ai_status !== "pending" && (
              <span className="chip warn">nothing detected</span>
            )}
          </div>

          {/* What is actually on file for today. The box clears after a save, so
              without this an empty box would look exactly like a lost entry — which
              is why it used to refill itself instead. Each note kept on its own
              line, in the order it was written. */}
          <div className="log-today">
            {todaysLog.text.split("\n").filter((line) => line.trim()).map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>

          <LogAdviceBlock
            advice={todaysLog.advice}
            summary={todaysLog.summary}
            status={todaysLog.ai_status}
            model={todaysLog.ai_model}
            compact
          />
        </>
      )}

      {earlier.length > 0 && (
        <div className="stack" style={{ gap: 9, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
          <div className="eyebrow">Earlier entries</div>
          {earlier.map((l) => (
            <div key={l.id} className="stack" style={{ gap: 4 }}>
              <div className="row" style={{ gap: 7 }}>
                <span className="faint mono">
                  {l.log_date}{l.logged_at && ` · ${l.logged_at}`}
                </span>
                {l.applies_to_date && l.applies_to_date !== l.log_date && (
                  <span className="chip accent" title={l.applies_to_reason}>
                    counted as {l.applies_to_date}
                  </span>
                )}
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
