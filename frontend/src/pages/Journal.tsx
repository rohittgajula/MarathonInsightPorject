import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { dateStr } from "../lib/format";
import type { Activity, JournalEntry } from "../lib/types";

/* Long-form writing, kept separate from the quick daily log.

   Nothing written here changes the training plan. That separation is deliberate: if
   reflective writing altered tomorrow's session, you would start editing your own
   diary to get the session you wanted, and the honest record would be gone.

   Where an entry mentions pain the app says so and offers to add it to the day's
   quick log — an explicit choice, never a silent one. */

interface Paged<T> { results: T[]; }

export function Journal() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Partial<JournalEntry> | null>(null);

  const entries = useQuery({
    queryKey: ["journal"],
    queryFn: () => api.get<Paged<JournalEntry>>("/journal/"),
  });
  const activities = useQuery({
    queryKey: ["activities"],
    queryFn: () => api.get<Paged<Activity>>("/activities/"),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["journal"] });

  const save = useMutation({
    mutationFn: (entry: Partial<JournalEntry>) =>
      entry.id
        ? api.patch<JournalEntry>(`/journal/${entry.id}/`, entry)
        : api.post<JournalEntry>("/journal/", entry),
    onSuccess: () => { refresh(); setEditing(null); },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del<void>(`/journal/${id}/`),
    onSuccess: refresh,
  });

  const logPain = useMutation({
    mutationFn: (body: { log_date: string; text: string }) => api.post("/logs/", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const today = new Date().toISOString().slice(0, 10);
  const rows = entries.data?.results ?? [];

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="eyebrow">Your own words</div>
          <h1>Journal</h1>
          <p className="muted" style={{ marginTop: 6, maxWidth: "62ch" }}>
            How the run felt, how the day went, what you want to remember about a race.
            Nothing written here changes your plan — it is a record, not an instruction.
          </p>
        </div>
        {!editing && (
          <button onClick={() => setEditing({ entry_date: today, title: "", body: "" })}>
            New entry
          </button>
        )}
      </div>

      {editing && (
        <form className="card stack" style={{ gap: 12 }}
              onSubmit={(e) => { e.preventDefault(); if (editing.body?.trim()) save.mutate(editing); }}>
          <h2>{editing.id ? "Edit entry" : "New entry"}</h2>
          <div className="grid">
            <label className="stack" style={{ gap: 5 }}>
              <span className="faint">Date</span>
              <input type="date" value={editing.entry_date ?? today}
                     onChange={(e) => setEditing({ ...editing, entry_date: e.target.value })} />
            </label>
            <label className="stack" style={{ gap: 5 }}>
              <span className="faint">Title (optional)</span>
              <input value={editing.title ?? ""} placeholder="e.g. Race day"
                     onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
            </label>
            <label className="stack" style={{ gap: 5 }}>
              <span className="faint">Link to a session (optional)</span>
              <select value={editing.activity ?? ""}
                      onChange={(e) => setEditing({
                        ...editing,
                        activity: e.target.value ? Number(e.target.value) : null,
                      })}>
                <option value="">Not linked</option>
                {(activities.data?.results ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.local_date} · {(a.total_distance_m / 1000).toFixed(2)} km {a.sport}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="stack" style={{ gap: 5 }}>
            <span className="faint">Entry</span>
            <textarea value={editing.body ?? ""} style={{ minHeight: 190 }}
                      placeholder="Write as much or as little as you like…"
                      onChange={(e) => setEditing({ ...editing, body: e.target.value })} />
          </label>

          <div className="row">
            <button type="submit" disabled={save.isPending || !editing.body?.trim()}>
              {save.isPending ? "Saving…" : editing.id ? "Save changes" : "Save entry"}
            </button>
            <button type="button" className="ghost" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}

      {rows.length === 0 && !editing && (
        <div className="card">
          <p className="muted">
            Nothing written yet. The entries worth having later are the ones written on
            ordinary days, not just after races.
          </p>
        </div>
      )}

      {rows.map((entry) => (
        <article key={entry.id} className="card stack" style={{ gap: 10 }}>
          <div className="row split" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="eyebrow">{dateStr(entry.entry_date)}</div>
              {entry.title && <h2 style={{ marginTop: 3 }}>{entry.title}</h2>}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <button className="ghost" style={{ padding: "5px 11px", fontSize: 12.5 }}
                      onClick={() => setEditing(entry)}>Edit</button>
              <button className="ghost" style={{ padding: "5px 11px", fontSize: 12.5 }}
                      onClick={() => { if (confirm("Delete this entry?")) remove.mutate(entry.id); }}>
                Delete
              </button>
            </div>
          </div>

          {entry.activity_label && (
            <span className="chip accent" style={{ alignSelf: "flex-start" }}>
              {entry.activity_label}
            </span>
          )}

          <p style={{ fontSize: 14, whiteSpace: "pre-wrap" }}>{entry.body}</p>

          {(entry.flags?.pain_area || entry.flags?.illness) && (
            <div className="note-block">
              <strong>
                You mentioned {entry.flags.pain_area
                  ? `${entry.flags.pain_area.replace("_", " ")} pain`
                  : "feeling unwell"}.
              </strong>{" "}
              Journal entries do not change your plan on their own. Add it to that day's
              quick log if you want tomorrow's session eased.
              <div style={{ marginTop: 8 }}>
                <button style={{ padding: "5px 11px", fontSize: 12.5 }}
                        disabled={logPain.isPending}
                        onClick={() => logPain.mutate({
                          log_date: entry.entry_date,
                          text: entry.flags.pain_area
                            ? `${entry.flags.pain_area.replace("_", " ")} pain (from journal)`
                            : "feeling unwell (from journal)",
                        })}>
                  {logPain.isPending ? "Adding…" : "Add to that day's log"}
                </button>
              </div>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
