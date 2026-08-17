import type { SessionWeather as Forecast } from "../lib/types";

/* Conditions for the session ahead, and what to do about them.

   The heat advice leads with the pace consequence rather than a warning, because the
   real failure mode is not heatstroke — it is running the prescribed pace in 30 C,
   finding it brutal, and concluding fitness has gone backwards. */

const TONE_STRIPE: Record<string, string> = {
  warn: "var(--warn)", good: "var(--good)", neutral: "var(--accent)",
};

export function SessionWeather({ weather }: { weather: Forecast }) {
  if (!weather || weather.temp_c == null) return null;

  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div className="row split" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Conditions for this session</h2>
          <p className="faint" style={{ marginTop: 2 }}>
            Forecast for {weather.hour}:00 on {weather.date}
            {weather.place && ` · ${weather.place}`}
          </p>
        </div>
        <span className="chip">{weather.conditions}</span>
      </div>

      <div className="grid">
        <div className="side-card">
          <div className="eyebrow">Feels like</div>
          <div className="mono" style={{ fontSize: 19, marginTop: 3 }}>
            {weather.feels_like_c?.toFixed(0)}°C
          </div>
          <div className="faint" style={{ fontSize: 11.5 }}>
            air {weather.temp_c?.toFixed(0)}°C
          </div>
        </div>
        <div className="side-card">
          <div className="eyebrow">Humidity</div>
          <div className="mono" style={{ fontSize: 19, marginTop: 3 }}>{weather.humidity_pct?.toFixed(0)}%</div>
        </div>
        <div className="side-card">
          <div className="eyebrow">Wind</div>
          <div className="mono" style={{ fontSize: 19, marginTop: 3 }}>{weather.wind_kmh?.toFixed(0)}</div>
          <div className="faint" style={{ fontSize: 11.5 }}>km/h</div>
        </div>
        <div className="side-card">
          <div className="eyebrow">Rain</div>
          <div className="mono" style={{ fontSize: 19, marginTop: 3 }}>{weather.rain_chance_pct?.toFixed(0)}%</div>
          <div className="faint" style={{ fontSize: 11.5 }}>chance</div>
        </div>
      </div>

      <div className="stack" style={{ gap: 0 }}>
        {weather.advice.map((a) => (
          <div key={a.title} className="insight" style={{ padding: "11px 0" }}>
            <span className="stripe" style={{ background: TONE_STRIPE[a.tone] ?? "var(--ink-faint)" }} />
            <div>
              <h3>{a.title}</h3>
              <p>{a.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
