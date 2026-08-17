import { useState } from "react";
import type { Segment } from "../lib/types";
import { durStr, paceStr } from "../lib/format";

/* The chart Garmin doesn't give you.
   A session summary says "2.65 km in 28:01". This says: five run blocks, the first
   one long and the rest collapsing, with walking in between. Width is proportional
   to elapsed time, so the shape of the session is legible at a glance. */

const COLOR: Record<Segment["kind"], string> = {
  run: "var(--run)",
  walk: "var(--walk)",
  stop: "var(--stop)",
};

const LABEL: Record<Segment["kind"], string> = {
  run: "Run",
  walk: "Walk",
  stop: "Stopped",
};

export function SegmentBar({ segments }: { segments: Segment[] }) {
  const [active, setActive] = useState<Segment | null>(null);

  const total = segments.reduce((sum, s) => sum + s.duration_s, 0);
  if (!total) return <p className="faint">No segment data for this activity.</p>;

  return (
    <div className="stack" style={{ gap: 12 }}>
      <div
        style={{ display: "flex", width: "100%", height: 34, borderRadius: 5, overflow: "hidden", gap: 2 }}
        onMouseLeave={() => setActive(null)}
      >
        {segments.map((seg) => (
          <button
            key={seg.index}
            aria-label={`${LABEL[seg.kind]} block, ${durStr(seg.duration_s)}, ${Math.round(seg.distance_m)} metres`}
            onMouseEnter={() => setActive(seg)}
            onFocus={() => setActive(seg)}
            style={{
              flex: `${Math.max(seg.duration_s, 1)} 0 0`,
              background: COLOR[seg.kind],
              /* Hit target spans the full bar height even for a 9-second block. */
              border: 0, borderRadius: 0, padding: 0, minWidth: 2, height: "100%",
              cursor: "pointer",
              outline: active?.index === seg.index ? "2px solid var(--ink)" : "none",
              outlineOffset: -2,
            }}
          />
        ))}
      </div>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="legend">
          <span><i className="sw" style={{ background: "var(--run)" }} /> Run</span>
          <span><i className="sw" style={{ background: "var(--walk)" }} /> Walk</span>
          <span><i className="sw" style={{ background: "var(--stop)" }} /> Stopped</span>
        </div>
        <div className="faint mono">{durStr(total)} total</div>
      </div>

      <div className="tooltip" style={{ visibility: active ? "visible" : "hidden", minHeight: 42 }}>
        {active && (
          <div className="row" style={{ gap: 18 }}>
            <strong>{LABEL[active.kind]}</strong>
            <span><span className="t-k">starts </span><span className="mono">{durStr(active.start_offset_s)}</span></span>
            <span><span className="t-k">for </span><span className="mono">{durStr(active.duration_s)}</span></span>
            <span><span className="t-k">dist </span><span className="mono">{Math.round(active.distance_m)} m</span></span>
            {active.kind === "run" && (
              <span><span className="t-k">pace </span><span className="mono">{paceStr(active.avg_pace_s_per_km)}/km</span></span>
            )}
            {active.hr_avg != null && (
              <span><span className="t-k">HR </span><span className="mono">{active.hr_avg}</span></span>
            )}
            {active.hr_recovery_60s != null && (
              <span><span className="t-k">HRR60 </span><span className="mono">{active.hr_recovery_60s} bpm</span></span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
