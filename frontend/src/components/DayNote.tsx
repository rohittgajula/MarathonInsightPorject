import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { DailyLog } from "../lib/types";

/* A note attached to a specific calendar day.

   Unlike the homepage box this can target any date, which is what makes it useful
   forward-looking: "flying Thursday, will sleep badly" written on Wednesday eases
   Thursday's session before it arrives. The night before governs the session, so a
   note on day D shapes day D+1. */

export function DayNote({ date, existing }: { date: string; existing: { text: string } | null }) {
  const [text, setText] = useState(existing?.text ?? "");
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();

  const save = useMutation({
    mutationFn: (body: { log_date: string; text: string }) =>
      api.post<DailyLog>("/logs/", body),
    onSuccess: () => {
      invalidateTrainingData(queryClient);
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  return (
    <div className="stack" style={{ gap: 8, borderTop: "1px solid var(--rule-soft)", paddingTop: 12 }}>
      <div className="eyebrow">Note for this day</div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. flying tomorrow and will sleep badly, or knee felt tight on the stairs"
        style={{ minHeight: 62 }}
      />
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <span className="faint">
          Sleep, alcohol and how you feel are picked out and applied to the next day's session.
        </span>
        <div className="row" style={{ gap: 8 }}>
          {saved && <span className="chip good">Saved</span>}
          <button
            onClick={() => text.trim() && save.mutate({ log_date: date, text: text.trim() })}
            disabled={save.isPending || !text.trim()}
          >
            {save.isPending ? "Saving…" : existing ? "Update note" : "Add note"}
          </button>
        </div>
      </div>
      {save.error && <p className="error" style={{ margin: 0 }}>{(save.error as Error).message}</p>}
    </div>
  );
}
