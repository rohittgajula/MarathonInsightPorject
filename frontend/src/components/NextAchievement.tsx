import { Link } from "react-router-dom";
import { achievementValue } from "../lib/format";
import type { AchievementItem } from "../lib/types";

/* One thing within reach, at the top of the page.

   Deliberately a single line rather than a badge wall. The motivating thing is a
   concrete number you can move this week — "17 of 25 bpm" — not a count of what you
   have not done yet. It sits inside the hero because that is where the eye already
   is, and it borrows the hero's own colours rather than introducing a new tone.

   It states progress and nothing else. No "you've got this", no exclamation marks:
   the number is the encouragement, and anything added on top would be the app
   talking rather than the data. */

export function NextAchievement({ item }: { item: AchievementItem }) {
  const value = achievementValue(item.format, item.value);
  const target = achievementValue(item.format, item.target);
  const pct = Math.max(0, Math.min(100, item.progress));

  return (
    <Link to="/achievements" className="next-ach bare" aria-label={
      `Closest achievement: ${item.name}, ${value} of ${target}`
    }>
      <div className="row split" style={{ justifyContent: "space-between", gap: 12 }}>
        <span className="next-ach-name">
          <span aria-hidden="true">◆</span> Closest: {item.name}
        </span>
        <span className="mono next-ach-value">
          {value} <span aria-hidden="true">/</span> {target} {item.unit}
        </span>
      </div>
      <div className="next-ach-bar" role="presentation">
        <span style={{ width: `${pct}%` }} />
      </div>
      <p className="next-ach-desc">{item.description}</p>
    </Link>
  );
}
