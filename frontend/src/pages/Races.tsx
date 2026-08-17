import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { dateStr, durStr } from "../lib/format";
import type { Race } from "../lib/types";

interface Paged<T> { results: T[]; }

const PRESETS = [
  { label: "5K", metres: 5000 },
  { label: "10K", metres: 10000 },
  { label: "Half", metres: 21097 },
  { label: "Marathon", metres: 42195 },
];

export function Races() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "", race_date: "", distance_m: 10000, location: "", goal: "finish" as const,
  });
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Race | null>(null);

  const races = useQuery({
    queryKey: ["races"],
    queryFn: () => api.get<Paged<Race>>("/races/"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["races"] });
    queryClient.invalidateQueries({ queryKey: ["targetRace"] });
  };

  const create = useMutation({
    mutationFn: (body: unknown) => api.post<Race>("/races/", body),
    onSuccess: () => {
      invalidate();
      setForm({ name: "", race_date: "", distance_m: 10000, location: "", goal: "finish" });
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const setTarget = useMutation({
    mutationFn: (id: number) => api.patch<Race>(`/races/${id}/`, { is_target: true }),
    onSuccess: invalidate,
  });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Race> }) =>
      api.patch<Race>(`/races/${id}/`, body),
    onSuccess: () => { invalidate(); setEditing(null); setError(null); },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del<void>(`/races/${id}/`),
    onSuccess: invalidate,
  });

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div>
        <div className="eyebrow">Goal</div>
        <h1>Races</h1>
        <p className="muted" style={{ marginTop: 6 }}>
          The target race sets the clock. Weeks remaining is what every progression
          decision is measured against.
        </p>
      </div>

      <form
        className="card stack"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ ...form, is_target: !races.data?.results.length });
        }}
      >
        <h2>Add a race</h2>
        <div className="grid">
          <label className="stack" style={{ gap: 5 }}>
            <span className="faint">Race name</span>
            <input
              required value={form.name}
              placeholder="e.g. Hyderabad Marathon"
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label className="stack" style={{ gap: 5 }}>
            <span className="faint">Race day</span>
            <input
              required type="date" value={form.race_date}
              onChange={(e) => setForm({ ...form, race_date: e.target.value })}
            />
          </label>
          <label className="stack" style={{ gap: 5 }}>
            <span className="faint">Distance</span>
            <select
              value={form.distance_m}
              onChange={(e) => setForm({ ...form, distance_m: Number(e.target.value) })}
            >
              {PRESETS.map((p) => (
                <option key={p.metres} value={p.metres}>{p.label}</option>
              ))}
            </select>
          </label>
          <label className="stack" style={{ gap: 5 }}>
            <span className="faint">Location</span>
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </label>
        </div>
        {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
        <div>
          <button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Add race"}
          </button>
        </div>
      </form>

      {races.data && races.data.results.length > 0 && (
        <div className="stack">
          {races.data.results.map((race) => (
            editing?.id === race.id ? (
              <form
                key={race.id} className="card stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  update.mutate({ id: race.id, body: {
                    name: editing.name, race_date: editing.race_date,
                    distance_m: editing.distance_m, location: editing.location,
                  }});
                }}
              >
                <h2>Edit race</h2>
                <div className="grid">
                  <label className="stack" style={{ gap: 5 }}>
                    <span className="faint">Race name</span>
                    <input required value={editing.name}
                           onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
                  </label>
                  <label className="stack" style={{ gap: 5 }}>
                    <span className="faint">Race day</span>
                    <input required type="date" value={editing.race_date}
                           onChange={(e) => setEditing({ ...editing, race_date: e.target.value })} />
                  </label>
                  <label className="stack" style={{ gap: 5 }}>
                    <span className="faint">Distance</span>
                    <select value={editing.distance_m}
                            onChange={(e) => setEditing({ ...editing, distance_m: Number(e.target.value) })}>
                      {PRESETS.map((p) => (
                        <option key={p.metres} value={p.metres}>{p.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="stack" style={{ gap: 5 }}>
                    <span className="faint">Location</span>
                    <input value={editing.location}
                           onChange={(e) => setEditing({ ...editing, location: e.target.value })} />
                  </label>
                </div>
                {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
                <div className="row">
                  <button type="submit" disabled={update.isPending}>
                    {update.isPending ? "Saving…" : "Save changes"}
                  </button>
                  <button type="button" className="ghost" onClick={() => { setEditing(null); setError(null); }}>
                    Cancel
                  </button>
                  <button
                    type="button" className="ghost" style={{ marginLeft: "auto" }}
                    onClick={() => {
                      if (confirm(`Delete "${race.name}"? This cannot be undone.`)) remove.mutate(race.id);
                    }}
                    disabled={remove.isPending}
                  >
                    Delete race
                  </button>
                </div>
              </form>
            ) : (
            <div key={race.id} className="card row split" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="row" style={{ gap: 9 }}>
                  <h2>{race.name}</h2>
                  <span className="chip">{race.distance_label}</span>
                  {race.is_target && <span className="chip good">Target</span>}
                  {race.is_past && <span className="chip">Done</span>}
                </div>
                <p className="faint" style={{ margin: "4px 0 0" }}>
                  {dateStr(race.race_date)}
                  {race.location && ` · ${race.location}`}
                  {race.goal === "time" && race.target_time_s
                    ? ` · target ${durStr(race.target_time_s)}`
                    : " · finish, no time target"}
                </p>
              </div>
              <div style={{ textAlign: "right" }}>
                {!race.is_past ? (
                  <>
                    <div className="mono" style={{ fontSize: 26, fontWeight: 750, letterSpacing: "-.03em" }}>
                      {race.weeks_until}
                    </div>
                    <div className="faint">
                      {race.weeks_until === 1 ? "week" : "weeks"} to go · {race.days_until} days
                    </div>
                  </>
                ) : (
                  <div className="faint">Race day has passed</div>
                )}
                <div className="row" style={{ marginTop: 8, justifyContent: "flex-end" }}>
                  {!race.is_target && !race.is_past && (
                    <button className="ghost" onClick={() => setTarget.mutate(race.id)}
                            disabled={setTarget.isPending}>
                      Make target
                    </button>
                  )}
                  <button className="ghost" onClick={() => { setEditing(race); setError(null); }}>
                    Edit
                  </button>
                </div>
              </div>
            </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}
