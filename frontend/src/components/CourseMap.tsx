import { useMemo, useState } from "react";
import type { Segment, StreamPoint } from "../lib/types";
import { durStr, paceStr } from "../lib/format";

/* The route, drawn as an inline SVG polyline coloured by what the athlete was doing
   at each point — so "where did I start walking" is answerable at a glance.

   No tile layer on purpose: a basemap needs an external tile host and an API key,
   and adds nothing here. The shape of the route plus the run/walk colouring carries
   the information. Swap in Leaflet later if street context becomes worth the
   dependency — the projection below is the same one a tile layer would use. */

const COLOR: Record<Segment["kind"], string> = {
  run: "var(--run)",
  walk: "var(--walk)",
  stop: "var(--stop)",
};

const PAD = 12;
const VIEW_W = 720;
const VIEW_H = 380;

interface Props {
  stream: StreamPoint[];
  segments: Segment[];
}

interface Path {
  d: string;
  kind: Segment["kind"];
  segment: Segment;
}

export function CourseMap({ stream, segments }: Props) {
  const [active, setActive] = useState<Segment | null>(null);

  const geo = useMemo(() => {
    const pts = stream.filter(
      (p) => p.latitude != null && p.longitude != null &&
             Number.isFinite(p.latitude) && Number.isFinite(p.longitude),
    );
    if (pts.length < 2) return null;

    const lats = pts.map((p) => p.latitude!);
    const lons = pts.map((p) => p.longitude!);
    const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;

    // Equirectangular with a cos(lat) correction on x. Over a few km this is
    // indistinguishable from a proper projection and keeps the aspect ratio honest,
    // which a raw lat/lon plot does not — it stretches east-west the further you are
    // from the equator.
    const kx = Math.cos((midLat * Math.PI) / 180);
    const xs = lons.map((v) => v * kx);
    const ys = lats.map((v) => -v);

    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const spanX = maxX - minX || 1e-6;
    const spanY = maxY - minY || 1e-6;

    // One scale for both axes so the route keeps its true shape.
    const scale = Math.min((VIEW_W - PAD * 2) / spanX, (VIEW_H - PAD * 2) / spanY);
    const offX = (VIEW_W - spanX * scale) / 2;
    const offY = (VIEW_H - spanY * scale) / 2;

    const project = (lat: number, lon: number): [number, number] => [
      offX + (lon * kx - minX) * scale,
      offY + (-lat - minY) * scale,
    ];

    const paths: Path[] = [];
    for (const seg of segments) {
      const end = seg.start_offset_s + seg.duration_s;
      const inSeg = pts.filter((p) => p.offset_s >= seg.start_offset_s && p.offset_s <= end);
      if (inSeg.length < 2) continue;
      const d = inSeg
        .map((p, i) => {
          const [x, y] = project(p.latitude!, p.longitude!);
          return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ");
      paths.push({ d, kind: seg.kind, segment: seg });
    }

    const [sx, sy] = project(pts[0].latitude!, pts[0].longitude!);
    const [ex, ey] = project(pts[pts.length - 1].latitude!, pts[pts.length - 1].longitude!);
    return { paths, start: [sx, sy] as const, finish: [ex, ey] as const };
  }, [stream, segments]);

  if (!geo) {
    return (
      <p className="faint">
        No GPS track recorded for this activity — the route map needs position data.
      </p>
    );
  }

  return (
    <div className="stack" style={{ gap: 12 }}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        style={{ width: "100%", height: "auto", display: "block",
                 background: "var(--surface-2)", borderRadius: 8 }}
        role="img"
        aria-label="Route map coloured by run and walk sections"
        onMouseLeave={() => setActive(null)}
      >
        {/* Full route underneath, so gaps between segments never break the line. */}
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          {geo.paths.map((p, i) => (
            <path key={`base-${i}`} d={p.d} stroke="var(--surface)" strokeWidth={7} />
          ))}
          {geo.paths.map((p, i) => (
            <path
              key={i}
              d={p.d}
              stroke={COLOR[p.kind]}
              strokeWidth={active?.index === p.segment.index ? 6.5 : 3.5}
              onMouseEnter={() => setActive(p.segment)}
              style={{ cursor: "pointer", transition: "stroke-width .12s" }}
            />
          ))}
        </g>

        <circle cx={geo.start[0]} cy={geo.start[1]} r={6}
                fill="var(--surface)" stroke="var(--ink)" strokeWidth={2.5} />
        <circle cx={geo.finish[0]} cy={geo.finish[1]} r={6}
                fill="var(--ink)" stroke="var(--surface)" strokeWidth={2.5} />
      </svg>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="legend">
          <span><i className="sw" style={{ background: "var(--run)" }} /> Run</span>
          <span><i className="sw" style={{ background: "var(--walk)" }} /> Walk</span>
          <span><i className="sw" style={{ background: "var(--stop)" }} /> Stopped</span>
          <span className="faint">○ start · ● finish</span>
        </div>
        {active && (
          <span className="faint mono">
            {active.kind} · {durStr(active.duration_s)} · {Math.round(active.distance_m)} m
            {active.kind === "run" && ` · ${paceStr(active.avg_pace_s_per_km)}/km`}
          </span>
        )}
      </div>
    </div>
  );
}
