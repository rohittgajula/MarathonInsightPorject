import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import { paceStr } from "../lib/format";
import type { Athlete, GarminStatus } from "../lib/types";

/* Garmin sign-in lives here rather than only in a terminal.

   The password field is a real credential, so the page says what happens to it
   instead of leaving the user to assume. It is exchanged for a token and dropped —
   never stored, never logged — and the form clears it the moment the request returns. */

function GarminSection() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [tone, setTone] = useState<"good" | "warn">("warn");

  const status = useQuery({
    queryKey: ["garminStatus"],
    queryFn: () => api.get<GarminStatus>("/garmin/status/"),
    retry: false,
  });

  const connect = useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<{ connected: boolean; name: string }>("/garmin/connect/", body),
    onSuccess: (r) => {
      setPassword("");
      setTone("good");
      setMessage(`Connected${r.name ? ` as ${r.name}` : ""}. Press Refresh to pull your history.`);
      invalidateTrainingData(queryClient);
    },
    onError: (err: ApiError) => {
      setPassword("");
      setTone("warn");
      setMessage(err.message);
    },
  });

  const disconnect = useMutation({
    mutationFn: () => api.post<{ connected: boolean }>("/garmin/disconnect/"),
    onSuccess: () => {
      setTone("good");
      setMessage("Disconnected. The stored token has been deleted.");
      invalidateTrainingData(queryClient);
    },
  });

  const connected = status.data?.connected === true;

  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Garmin</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            {connected
              ? `Signed in as ${status.data?.name || "your account"}.`
              : "Sign in once. Runs and daily health data then import on their own."}
          </p>
        </div>
        <span className="row" style={{ gap: 7 }}>
          <i className={`bulb ${status.isLoading ? "pending" : connected ? "on" : "off"}`} />
          <span className="faint">{connected ? "connected" : "not connected"}</span>
        </span>
      </div>

      {connected ? (
        <div className="row">
          <button className="ghost" onClick={() => disconnect.mutate()} disabled={disconnect.isPending}>
            {disconnect.isPending ? "Disconnecting…" : "Disconnect Garmin"}
          </button>
        </div>
      ) : (
        <form
          className="stack" style={{ gap: 10 }}
          onSubmit={(e) => { e.preventDefault(); setMessage(null); connect.mutate({ email, password }); }}
        >
          <div className="grid">
            <label className="stack" style={{ gap: 5 }}>
              <span className="faint">Garmin email</span>
              <input type="email" autoComplete="username" required
                     value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="stack" style={{ gap: 5 }}>
              <span className="faint">Garmin password</span>
              <input type="password" autoComplete="current-password" required
                     value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </div>

          <div className="note-block">
            <strong>What happens to your password:</strong> it is sent once to your own
            backend, exchanged with Garmin for an access token, and discarded. It is never
            written to the database, a file, or a log, and the field clears as soon as the
            request finishes. Only the refreshable token is kept. Over localhost this is
            fine; if you ever host this on a domain, put it behind HTTPS first.
          </div>

          <div className="row">
            <button type="submit" disabled={connect.isPending || !email || !password}>
              {connect.isPending ? "Connecting…" : "Connect Garmin"}
            </button>
            <span className="faint">
              Two-factor account? Use <code>scripts/garmin_login.py</code> — it can prompt for the code.
            </span>
          </div>
        </form>
      )}

      {message && (
        <p className={tone === "good" ? "faint" : "error"}
           style={tone === "good" ? { color: "var(--good)" } : undefined}>
          {message}
        </p>
      )}
    </div>
  );
}

function TrainingSection() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Partial<Athlete> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const athlete = useQuery({
    queryKey: ["athlete"],
    queryFn: () => api.get<Athlete>("/athletes/me/"),
  });

  const save = useMutation({
    mutationFn: (body: Partial<Athlete>) => api.patch<Athlete>("/athletes/me/", body),
    onSuccess: () => {
      invalidateTrainingData(queryClient);
      setDraft(null);
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  if (!athlete.data) return null;
  const current = { ...athlete.data, ...(draft ?? {}) };

  const field = (key: keyof Athlete, label: string, hint: string, unit = "") => (
    <label className="stack" style={{ gap: 5 }}>
      <span className="faint">{label}{unit && ` (${unit})`}</span>
      <input type="number" value={String(current[key] ?? "")}
             onChange={(e) => setDraft({ ...(draft ?? {}), [key]: Number(e.target.value) })} />
      <span className="faint" style={{ fontSize: 11.5 }}>{hint}</span>
    </label>
  );

  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div>
        <h2>Training targets</h2>
        <p className="faint" style={{ marginTop: 2 }}>
          These drive every judgement the app makes. Changing them rebuilds the metrics
          on all of your past sessions.
        </p>
      </div>

      <div className="grid">
        {field("easy_pace_min", "Easy pace, fast edge", `Currently ${paceStr(current.easy_pace_min)}/km`, "sec/km")}
        {field("easy_pace_max", "Easy pace, slow edge", `Currently ${paceStr(current.easy_pace_max)}/km`, "sec/km")}
        {field("hr_easy_min", "Easy HR, low", "Bottom of the band shaded on charts", "bpm")}
        {field("hr_easy_max", "Easy HR, high", "Top of the band shaded on charts", "bpm")}
        {field("hr_ceiling", "Walk-now ceiling", "Cross this in a run block and you should walk", "bpm")}
        {field("run_cadence_threshold", "Run cadence threshold",
               "Above this counts as running. 140 separates a slow jog from a brisk walk.", "spm")}
      </div>

      {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
      {draft && (
        <div className="row">
          <button onClick={() => save.mutate(draft)} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save and rebuild metrics"}
          </button>
          <button className="ghost" onClick={() => { setDraft(null); setError(null); }}>Cancel</button>
        </div>
      )}
    </div>
  );
}

export function Settings() {
  return (
    <div className="stack" style={{ gap: 20 }}>
      <div>
        <div className="eyebrow">Configuration</div>
        <h1>Settings</h1>
      </div>
      <GarminSection />
      <TrainingSection />
    </div>
  );
}
