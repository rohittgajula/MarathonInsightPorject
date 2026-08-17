import type { QueryClient } from "@tanstack/react-query";

/* One place that knows what depends on what.

   Every mutation used to invalidate its own hand-picked list, which is how a screen
   ends up showing a stale number after an edit somewhere else. Anything that changes
   training data invalidates the whole derived layer instead — these are small
   queries and correctness matters more here than saving a request. */

export const KEYS = {
  dashboard: ["dashboard"],
  activities: ["activities"],
  activity: (id: string | number) => ["activity", String(id)],
  athlete: ["athlete"],
  races: ["races"],
  targetRace: ["targetRace"],
  logs: ["logs"],
  garminStatus: ["garminStatus"],
} as const;

/** Everything derived from activities, logs, wellness or the plan. */
const DERIVED = [
  KEYS.dashboard, KEYS.activities, KEYS.logs,
  KEYS.races, KEYS.targetRace, KEYS.athlete, KEYS.garminStatus,
];

export function invalidateTrainingData(qc: QueryClient) {
  DERIVED.forEach((queryKey) => qc.invalidateQueries({ queryKey }));
  // Activity detail pages are keyed per id, so match on the prefix.
  qc.invalidateQueries({ queryKey: ["activity"] });
}
