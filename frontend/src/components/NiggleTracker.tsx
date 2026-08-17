import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { dateStr } from "../lib/format";
import type { NiggleResponse } from "../lib/types";

/* Pain mentions, gathered across every daily log.

   Nobody re-reads six weeks of their own notes, so a knee mentioned in weeks 2, 4 and
   5 stays invisible until it stops being a niggle. The threshold is low and the
   wording says plainly that three mentions is not proof of anything — the value is in
   noticing early, not in diagnosing. */

const TONE: Record<string, string> = { recurring: "warn", watch: "accent", noted: "" };

export function NiggleTracker() {
  const { data } = useQuery({
    queryKey: ["niggles"],
    queryFn: () => api.get<NiggleResponse>("/niggles/"),
  });

  if (!data) return null;

  if (data.areas.length === 0) {
    return (
      <div className="card stack" style={{ gap: 6 }}>
        <h2>Niggles</h2>
        <p className="faint">
          No pain mentioned in your logs. If something starts nagging, write it in the
          daily log and it will be tracked here — recurrence is the signal, not any one day.
        </p>
      </div>
    );
  }

  return (
    <div className={data.any_recurring ? "banner stack" : "card stack"} style={{ gap: 12 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Niggles</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Pain mentioned across your logs, over the last {data.window_days} days.
          </p>
        </div>
        <span className="faint">{data.total_mentions} mentions</span>
      </div>

      {data.areas.map((area) => (
        <div key={area.area} className="stack" style={{ gap: 6,
             borderTop: "1px solid var(--rule-soft)", paddingTop: 10 }}>
          <div className="row" style={{ gap: 9 }}>
            <strong style={{ fontSize: 14 }}>{area.label}</strong>
            <span className={`chip ${TONE[area.status]}`}>{area.status}</span>
            <span className="faint mono">
              ×{area.count} · {dateStr(area.first_seen).replace(/,.*/, "")} → {dateStr(area.last_seen).replace(/,.*/, "")}
            </span>
          </div>
          <p style={{ fontSize: 13 }}>{area.note}</p>
          <div className="stack" style={{ gap: 3 }}>
            {area.mentions.map((m) => (
              <div key={m.date} className="faint" style={{ fontSize: 12.5 }}>
                <span className="mono">{m.date}</span> — {m.text}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
