export const paceStr = (secPerKm?: number | null): string => {
  if (!secPerKm || !isFinite(secPerKm) || secPerKm <= 0) return "—";
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
};

export const durStr = (seconds?: number | null): string => {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
};

export const km = (metres?: number | null, dp = 2): string =>
  metres == null ? "—" : (metres / 1000).toFixed(dp);

export const pct = (value?: number | null): string =>
  value == null ? "—" : `${value.toFixed(0)}%`;

export const dateStr = (iso: string): string =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
