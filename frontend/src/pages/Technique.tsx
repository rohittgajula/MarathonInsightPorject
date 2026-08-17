import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TechniqueGuide } from "../lib/types";

/* The things a training plan assumes you already know.

   Note what is absent: any instruction about which part of the foot to land on. The
   evidence does not support prescribing a foot strike, and telling a new runner to
   change theirs is a reliable way to produce a calf or achilles injury. Where the
   foot lands relative to the body is what matters, and that is covered. */

export function Technique() {
  const { data, isLoading } = useQuery({
    queryKey: ["technique"],
    queryFn: () => api.get<TechniqueGuide>("/technique/"),
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!data) return <p className="error">Could not load the guide.</p>;

  return (
    <div className="stack" style={{ gap: 22 }}>
      <div>
        <div className="eyebrow">The bit plans leave out</div>
        <h1>How to run</h1>
        <p className="muted" style={{ marginTop: 6, maxWidth: "64ch" }}>
          Six things worth thinking about while you run. Take one per session rather
          than all six at once — trying to fix everything simultaneously is how people
          end up running stiffly and calling it form.
        </p>
      </div>

      <div className="grid-2">
        {data.cues.map((cue, i) => (
          <div key={cue.key} className="card stack" style={{ gap: 8 }}>
            <div className="row" style={{ gap: 10 }}>
              <span className="step-num mono">{i + 1}</span>
              <h2>{cue.title}</h2>
            </div>
            <p style={{ fontSize: 13.5 }}><strong>Try this:</strong> {cue.cue}</p>
            <p className="faint" style={{ fontSize: 13 }}>{cue.why}</p>
          </div>
        ))}
      </div>

      <div className="card stack" style={{ gap: 12 }}>
        <div>
          <h2>When it goes wrong</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            The problems almost everyone hits in the first month.
          </p>
        </div>
        <div className="stack" style={{ gap: 0 }}>
          {data.troubleshooting.map((row) => (
            <div key={row.problem} className="target-row">
              <strong style={{ fontSize: 13.5 }}>{row.problem}</strong>
              <p style={{ fontSize: 13, marginTop: 3 }}>{row.answer}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="note-block">
        <strong>One thing deliberately not here:</strong> which part of your foot should
        land first. The research does not support prescribing a foot strike, and changing
        yours on purpose is a common route to a calf or achilles injury. Land under your
        hips, keep the cadence quick, and your foot strike will sort itself out.
      </div>
    </div>
  );
}
