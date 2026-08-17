import type { SessionStep, SessionTarget } from "../lib/types";

/* The prescription expanded into instructions.

   "8 × (1 min run / 2 min walk)" is a specification. Someone new to running needs the
   sequence, the numbers to hold, and what each number means in the body — otherwise
   the plan assumes knowledge it never taught. */

export function SessionPlan(
  { steps, targets }: { steps: SessionStep[]; targets: SessionTarget[] },
) {
  if (steps.length === 0 && targets.length === 0) return null;

  return (
    <div className="grid-2">
      {steps.length > 0 && (
        <div className="card stack" style={{ gap: 12 }}>
          <div>
            <h2>How to run it</h2>
            <p className="faint" style={{ marginTop: 2 }}>Start to finish, in order.</p>
          </div>
          <ol className="stack" style={{ gap: 0, listStyle: "none", padding: 0, margin: 0 }}>
            {steps.map((step, i) => (
              <li key={step.label} className="step-row">
                <span className="step-num mono">{i + 1}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <strong style={{ fontSize: 14 }}>{step.label}</strong>
                    <span className="chip">{step.duration}</span>
                  </div>
                  <p style={{ fontSize: 13, marginTop: 3 }}>{step.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {targets.length > 0 && (
        <div className="card stack" style={{ gap: 12 }}>
          <div>
            <h2>Numbers to hold</h2>
            <p className="faint" style={{ marginTop: 2 }}>
              And what each one actually means while you are running.
            </p>
          </div>
          <div className="stack" style={{ gap: 0 }}>
            {targets.map((t) => (
              <div key={t.label} className="target-row">
                <div className="row split" style={{ justifyContent: "space-between" }}>
                  <span className="faint">{t.label}</span>
                  <strong className="mono" style={{ fontSize: 14.5 }}>{t.value}</strong>
                </div>
                <p style={{ fontSize: 12.5, marginTop: 2 }}>{t.note}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
