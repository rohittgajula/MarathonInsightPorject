import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { FuelingPlan } from "../lib/types";

/* What to drink and eat around the session — before, during, after.

   Sits above the session itself because it is the part with a deadline: the
   pre-run drink has to happen two hours out, which is before anyone opens an app
   to check what the session is.

   Every figure is derived server-side from the session length, the forecast and
   body weight, and each card says which number it came from. The heat line is the
   one that earns the panel its place here: at 80% humidity the same 28-minute walk
   costs roughly half again as much fluid as it would in temperate air, and nothing
   in the app said so before. */

export function FuelingPanel({ date }: { date?: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["fueling", date ?? "auto"],
    queryFn: () => api.get<FuelingPlan>(`/fueling/${date ? `?date=${date}` : ""}`),
  });

  if (isLoading) return null;
  if (isError || !data) return null;

  const when = data.is_today ? "today" : "the next session";

  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Fuel and fluid</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            For {when} — {data.session_title || "no session"}
            {data.minutes > 0 && `, ${data.minutes} min`}
          </p>
        </div>
        <div className="row" style={{ gap: 7 }}>
          {data.hot && <span className="chip warn">heat adjusted</span>}
          {data.feels_like_c != null && (
            <span className="chip">{data.feels_like_c.toFixed(0)} °C felt</span>
          )}
          {data.humidity_pct != null && (
            <span className="chip">{data.humidity_pct.toFixed(0)}% humidity</span>
          )}
        </div>
      </div>

      {data.expected_loss_ml > 0 && (
        <div className="note-block">
          <strong>Expect to lose about {data.expected_loss_ml} ml</strong> over this
          session — roughly {data.sweat_rate_ml_per_h} ml an hour in these conditions.
          Everything below is scaled from that.
        </div>
      )}

      <div className="fuel-grid">
        <FuelColumn title="Before" subtitle="Starts 2 hours out" items={data.before} />
        <FuelColumn title="During" subtitle="Sip, don't gulp" items={data.during} />
        {data.after.length > 0 && (
          <FuelColumn title="After" subtitle="Within 2 hours" items={data.after} />
        )}
      </div>

      <div className="stack" style={{ gap: 6 }}>
        {data.notes.map((note, i) => (
          <p key={i} className="faint" style={{ lineHeight: 1.55 }}>{note}</p>
        ))}
      </div>
    </div>
  );
}

function FuelColumn({ title, subtitle, items }: {
  title: string; subtitle: string; items: FuelingPlan["before"];
}) {
  return (
    <section className="fuel-col">
      <div className="fuel-head">
        <h3>{title}</h3>
        <span className="faint">{subtitle}</span>
      </div>
      {items.map((item) => (
        <div key={item.key} className="fuel-item">
          <div className="row split" style={{ justifyContent: "space-between", gap: 8 }}>
            <span className="fuel-label">{item.label}</span>
            <span className="fuel-amount mono">{item.amount}</span>
          </div>
          <p className="muted">{item.detail}</p>
        </div>
      ))}
    </section>
  );
}
