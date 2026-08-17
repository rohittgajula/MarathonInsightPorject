import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { GarminStatus, SyncResult } from "../lib/types";

/* Connection state is re-probed rather than read from a stored flag, because the
   failure that actually happens is a token that looks present but no longer works —
   the login CLI prints "Logged in" even when it wrote nothing. */

export function GarminPanel() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  const status = useQuery({
    queryKey: ["garminStatus"],
    queryFn: () => api.get<GarminStatus>("/garmin/status/"),
    retry: false,
  });

  const sync = useMutation({
    mutationFn: () => api.post<SyncResult>("/garmin/sync/", { limit: 20 }),
    onSuccess: (r) => {
      const parts = [`${r.imported} imported`, `${r.skipped} already had`];
      if (r.failed) parts.push(`${r.failed} failed`);
      setMessage(parts.join(" · ") + (r.errors.length ? ` — ${r.errors[0]}` : ""));
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["activities"] });
      queryClient.invalidateQueries({ queryKey: ["garminStatus"] });
    },
    onError: (err: ApiError) => {
      setMessage(
        err.status === 429
          ? "Garmin is rate-limiting this IP. Wait 15–60 minutes and try again."
          : err.status === 401
          ? "Garmin session isn't valid. Run `garmin-mcp login` again."
          : err.message,
      );
    },
  });

  const connected = status.data?.connected === true;

  return (
    <div className={connected ? "card stack" : "banner stack"} style={{ gap: 10 }}>
      <div className="row split" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <h2>Garmin</h2>
            <span className={`chip ${connected ? "good" : "warn"}`}>
              {status.isLoading ? "checking" : connected ? "connected" : "not connected"}
            </span>
          </div>
          <p style={{ marginTop: 4, fontSize: 13.5 }}>
            {connected
              ? `Signed in as ${status.data?.name || "your Garmin account"}. Runs import automatically when you refresh.`
              : status.data?.error ||
                "No valid Garmin session. Everything below comes from files you uploaded by hand."}
          </p>
        </div>
        <button onClick={() => { setMessage(null); sync.mutate(); }} disabled={sync.isPending}>
          {sync.isPending ? "Refreshing…" : "Refresh from Garmin"}
        </button>
      </div>

      {!connected && !status.isLoading && (
        <p className="faint" style={{ marginTop: 0 }}>
          Run <code>~/.garmin-mcp-venv/bin/garmin-mcp login</code> in a terminal, then press
          Refresh. Check the token directory is not empty afterwards — the CLI reports
          success even when the login failed.
        </p>
      )}

      {message && <p className="faint" style={{ color: "var(--ink)" }}>{message}</p>}
    </div>
  );
}
