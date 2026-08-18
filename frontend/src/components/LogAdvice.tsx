import { Link } from "react-router-dom";
import type { AdviceNote, LogAdvice as Advice, Prescription } from "../lib/types";
import { ExerciseAnimation } from "./ExerciseAnimation";

/* What follows from a log entry, once a model has read it.

   Two things are deliberately visible here. The model's own one-line restatement,
   so a misreading is obvious immediately rather than after it has quietly changed
   the plan. And, on every prescription, the line about when to see a person
   instead — an app that hands out rehab exercises owes that one up front, not in a
   footnote. */

const KIND_ORDER = ["rehab", "activation", "mobility", "strength", "core", "drill"];

export function LogAdviceBlock({ advice, summary, status, model, compact = false }: {
  advice?: Advice;
  summary?: string;
  status?: string;
  model?: string;
  /* On the dashboard the log sits above everything else on the page, so the
     prescription shows names and doses only. The full why-and-how lives on
     Strength & rehab, one click away, where there is room for it. */
  compact?: boolean;
}) {
  if (status === "pending") {
    return (
      <div className="row" style={{ gap: 8 }}>
        <span className="chip accent">reading your entry…</span>
        <span className="faint">
          Sleep, food, pain and which day this is about are being pulled out.
        </span>
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <p className="faint" style={{ margin: 0 }}>
        Falling back to keyword matching — no <code>GEMINI_API_KEY</code> or{" "}
        <code>ANTHROPIC_API_KEY</code> is set, so the chips above come from pattern
        rules rather than from reading the sentence.
      </p>
    );
  }

  if (status === "bad_key") {
    return (
      <p className="faint" style={{ margin: 0 }}>
        The API key is being rejected — check <code>GEMINI_API_KEY</code> in{" "}
        <code>.env</code>, then <code>docker compose up -d backend worker</code>. Your
        entry is saved and will be re-read once the key works.
      </p>
    );
  }

  if (status === "rate_limited") {
    return (
      <p className="faint" style={{ margin: 0 }}>
        Free-tier quota is used up for now — your entry is saved and will be re-read
        automatically within about ten minutes. The chips above are from the keyword
        parser meanwhile.
      </p>
    );
  }

  if (status === "failed") {
    return (
      <p className="faint" style={{ margin: 0 }}>
        Couldn't read this entry, so the chips above are from the keyword parser. Your
        text is saved either way — it will be re-read automatically.
      </p>
    );
  }

  const hydration = advice?.hydration ?? [];
  const pain = advice?.pain ?? [];
  const flags = advice?.flags ?? [];
  const nothing = !summary && !hydration.length && !pain.length && !flags.length;
  if (nothing) return null;

  return (
    <div className="stack" style={{ gap: 13 }}>
      {summary && (
        <div className="note-block">
          {/* Naming the model is not decoration: two backends can be in play, and
              a misreading is easier to judge when you know which one produced it. */}
          <p className="eyebrow" style={{ marginBottom: 4 }}>
            Read as{model ? ` · ${model}` : ""}
          </p>
          <p style={{ margin: 0 }}>{summary}</p>
        </div>
      )}

      {pain.map((p) => (
        <PrescriptionCard key={p.area} prescription={p} compact={compact} />
      ))}

      {[...hydration, ...flags].map((note) => (
        <Note key={note.key} note={note} />
      ))}
    </div>
  );
}

function Note({ note }: { note: AdviceNote }) {
  return (
    <div className={`insight ${note.tone}`}>
      <span className="stripe" />
      <div>
        <h3>{note.headline}</h3>
        <p className="muted">{note.detail}</p>
      </div>
    </div>
  );
}

export function PrescriptionCard({ prescription: p, compact = false }: {
  prescription: Prescription;
  compact?: boolean;
}) {
  const ordered = [...p.exercises].sort(
    (a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind),
  );

  return (
    <div className="prescription">
      <div className="row split" style={{ justifyContent: "space-between", gap: 10 }}>
        <h3 style={{ margin: 0 }}>
          {p.area.replace(/_/g, " ")}
          {p.side && p.side !== "unspecified" && ` · ${p.side}`}
        </h3>
        <div className="row" style={{ gap: 6 }}>
          <span className={`chip ${p.severity >= 3 ? "warn" : ""}`}>{p.severity}/5</span>
          {p.when === "running" && <span className="chip warn">while running</span>}
        </div>
      </div>

      {p.quote && <p className="faint" style={{ marginTop: 2 }}>“{p.quote}”</p>}

      <p className="muted" style={{ marginTop: 8 }}>{p.running_advice}</p>

      {/* Above the exercises, never below them: someone who needs this line is the
          person least likely to scroll past a list of things to try first. */}
      <div className="red-flags">
        <p className="eyebrow">When this is not a training problem</p>
        <p>{p.red_flags}</p>
      </div>

      {ordered.length > 0 && (
        <div className="stack" style={{ gap: 0, marginTop: 4 }}>
          <p className="eyebrow" style={{ marginBottom: 6 }}>
            {p.acute_only
              ? "Gentle work only, while it is this sore"
              : "Work this into the days between runs"}
          </p>
          {ordered.map((e) => (
            <div key={e.key} className="exercise-row">
              <div className="row split" style={{ justifyContent: "space-between", gap: 10 }}>
                <span className="exercise-name">{e.name}</span>
                <span className="mono faint">{e.dose}</span>
              </div>
              {!compact && (
                <div className="ex-row" style={{ marginTop: 6 }}>
                  <ExerciseAnimation exerciseKey={e.key} />
                  <div className="stack" style={{ gap: 6 }}>
                    <p className="muted" style={{ margin: 0 }}>{e.why}</p>
                    <p className="faint" style={{ margin: 0 }}>{e.how}</p>
                    {e.caution && <p className="caution" style={{ margin: 0 }}>{e.caution}</p>}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <Link to="/exercises" className="linklike" style={{ marginTop: 6, display: "inline-block" }}>
        {compact ? "How to do these, and everything else for this area →"
                 : "Everything else for this area →"}
      </Link>
    </div>
  );
}
