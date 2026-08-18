import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { achievementValue, dateStr } from "../lib/format";
import type { AchievementBoard, AchievementItem } from "../lib/types";

/* Locked achievements show real progress rather than a padlock: "4:51 of 10:00" tells
   you where you actually are and what the next step costs. Progress is capped below
   100% until earned, so a bar never sits full on something you have not done. */

const formatValue = (item: AchievementItem, value: number) =>
  achievementValue(item.format, value);

function Card({ item }: { item: AchievementItem }) {
  const done = item.earned;
  return (
    <div className={`ach ${done ? "earned" : ""}`}>
      <div className="row split" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <h3>{item.name}</h3>
          <p className="faint" style={{ fontSize: 12.5, marginTop: 3 }}>{item.description}</p>
        </div>
        <span className={`ach-badge ${done ? "on" : ""}`} aria-hidden="true">
          {done ? "✓" : `${Math.round(item.progress)}%`}
        </span>
      </div>

      <div className="ach-bar" role="img"
           aria-label={done ? "Earned" : `${Math.round(item.progress)} percent of the way there`}>
        <span style={{ width: `${item.progress}%` }} />
      </div>

      <div className="row split" style={{ justifyContent: "space-between" }}>
        <span className="faint mono" style={{ fontSize: 12 }}>
          {item.key === "no_overshoot" && !done
            ? `best ${formatValue(item, item.value)} — needs 0`
            : `${formatValue(item, item.value)} of ${formatValue(item, item.target)}`}
        </span>
        {done && item.earned_on && (
          <span className="chip good">{dateStr(item.earned_on).replace(/,.*/, "")}</span>
        )}
      </div>
    </div>
  );
}

export function Achievements() {
  const { data, isLoading } = useQuery({
    queryKey: ["achievements"],
    queryFn: () => api.get<AchievementBoard>("/achievements/"),
  });

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!data) return <p className="error">Could not load achievements.</p>;

  const pct = Math.round((data.earned_count / data.total) * 100);

  return (
    <div className="stack" style={{ gap: 22 }}>
      <div className="hero">
        <div className="row split" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div className="eyebrow">Earned from your own data</div>
            <h1>{data.earned_count} of {data.total}</h1>
            <p>
              Every one of these is a threshold in your training that was not true
              before and is now. Nothing here is awarded for showing up.
            </p>
          </div>
          <span className="hero-badge mono">{pct}%</span>
        </div>
      </div>

      {data.recent.length > 0 && (
        <div className="card stack" style={{ gap: 10 }}>
          <h2>Most recent</h2>
          <div className="row" style={{ gap: 10 }}>
            {data.recent.map((item) => (
              <span key={item.key} className="chip good" style={{ fontSize: 12 }}>
                {item.name} · {item.earned_on && dateStr(item.earned_on).replace(/,.*/, "")}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.groups.map((group) => (
        <div key={group.name} className="stack" style={{ gap: 12 }}>
          <div className="row split" style={{ justifyContent: "space-between" }}>
            <h2>{group.name}</h2>
            <span className="faint">
              {group.items.filter((i) => i.earned).length} of {group.items.length}
            </span>
          </div>
          <div className="ach-grid">
            {group.items.map((item) => <Card key={item.key} item={item} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
