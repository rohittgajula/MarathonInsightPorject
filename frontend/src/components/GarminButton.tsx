import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { GarminStatus, SyncResult } from "../lib/types";

/* Compact header control: a status bulb plus one button. State is re-probed rather
   than trusted from a stored flag, because the failure that actually happens is a
   token that looks present but no longer works. */

export function GarminButton() {
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
      setMessage(`${r.imported} imported · ${r.skipped} already had`);
      invalidateTrainingData(queryClient);
    },
    onError: (err: ApiError) =>
      setMessage(
        err.status === 429 ? "Garmin is rate-limiting this IP. Try again in 15–60 min."
        : err.status === 401 ? "Session invalid — run `garmin-mcp login` again."
        : err.message),
  });

  const connected = status.data?.connected === true;
  const bulb = status.isLoading ? "pending" : connected ? "on" : "off";
  const label = status.isLoading ? "Checking Garmin…"
    : connected ? `Garmin connected${status.data?.name ? ` as ${status.data.name}` : ""}`
    : `Garmin not connected — ${status.data?.error ?? "no session"}`;

  return (
    <div className="tools">
      {message && <span className="faint" style={{ maxWidth: 280 }}>{message}</span>}
      <span className="row" style={{ gap: 7 }} title={label}>
        <i className={`bulb ${bulb}`} aria-hidden="true" />
        <span className="faint" style={{ fontSize: 12.5 }}>
          {status.isLoading ? "checking" : connected ? "connected" : "not connected"}
        </span>
        {/* Status is announced for screen readers, not carried by the bulb colour alone. */}
        <span className="sr-only" role="status">{label}</span>
      </span>
      <button
        className={connected ? "" : "ghost"}
        onClick={() => { setMessage(null); sync.mutate(); }}
        disabled={sync.isPending}
        title={label}
      >
        {sync.isPending ? "Refreshing…" : "Refresh Garmin"}
      </button>
    </div>
  );
}
