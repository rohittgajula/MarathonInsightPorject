import type { ChartNote } from "../lib/types";

/* Every chart carries its own read. A chart without an interpretation is a picture;
   with one it is a decision. Tone is shown by stripe and wording, never colour alone. */

const LABEL: Record<string, string> = {
  good: "Working", warn: "To improve", neutral: "Note",
};

export function ChartNotes({ notes }: { notes?: ChartNote[] }) {
  if (!notes || notes.length === 0) return null;
  return (
    <div className="stack" style={{ gap: 0, marginTop: 10 }}>
      {notes.map((n, i) => (
        <div key={i} className={`insight ${n.tone}`} style={{ padding: "10px 0" }}>
          <span className="stripe" />
          <div>
            <span className={`chip ${n.tone === "neutral" ? "" : n.tone}`}>{LABEL[n.tone]}</span>
            <p style={{ fontSize: 13, marginTop: 5 }}>{n.text}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
