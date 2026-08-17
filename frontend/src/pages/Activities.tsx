import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { RunCompare } from "../components/RunCompare";
import { UploadCard } from "../components/UploadCard";
import { durStr, km, paceStr, pct, dateStr } from "../lib/format";
import type { Activity } from "../lib/types";

interface Paged<T> { results: T[]; count: number; }

export function Activities() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["activities"],
    queryFn: () => api.get<Paged<Activity>>("/activities/"),
  });

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div>
        <div className="eyebrow">Training log</div>
        <h1>Activities</h1>
      </div>


      <UploadCard />

      {isLoading && <p className="muted">Loading…</p>}
      {error && <p className="error">Could not load activities.</p>}

      {data && data.results.length === 0 && (
        <div className="card">
          <p className="muted">
            No activities yet. Upload a <code>.fit</code> file above to see your run
            broken into its actual run and walk blocks.
          </p>
        </div>
      )}

      {data && data.results.length > 0 && <RunCompare activities={data.results} />}

      {data && data.results.length > 0 && (
        <div className="card scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">Distance</th>
                <th className="num">Time</th>
                <th className="num">Blocks</th>
                <th className="num">Longest run</th>
                <th className="num">Run pace</th>
                <th className="num">Discipline</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((a) => (
                <tr key={a.id}>
                  <td><Link to={`/activity/${a.id}`}>{dateStr(a.local_date)}</Link></td>
                  <td className="num mono">{km(a.total_distance_m)} km</td>
                  <td className="num mono">{durStr(a.total_elapsed_s)}</td>
                  <td className="num mono">{a.metrics?.run_block_count ?? "—"}</td>
                  <td className="num mono">{durStr(a.metrics?.longest_run_s)}</td>
                  <td className="num mono">{paceStr(a.metrics?.avg_run_pace_s_per_km)}</td>
                  <td className="num mono">{pct(a.metrics?.pace_discipline_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
