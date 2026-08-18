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

/** "3 minutes ago", "2 hours ago", "yesterday" — picks the unit that reads naturally.
 *  Formatting everything in minutes gave "synced 76 minutes ago", which is accurate
 *  and useless: nobody counts in 76s. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";

  const seconds = Math.round((Date.now() - then) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  if (seconds < 45) return "just now";
  if (seconds < 3600) return rtf.format(-Math.round(seconds / 60), "minute");
  if (seconds < 86_400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    // Under three hours the spare minutes still matter for "is this data fresh?";
    // beyond that the hour alone is enough.
    return hours < 3 && minutes > 0
      ? `${hours}h ${minutes}m ago`
      : rtf.format(-hours, "hour");
  }
  if (seconds < 2_592_000) return rtf.format(-Math.round(seconds / 86_400), "day");
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
