export interface Segment {
  index: number;
  kind: "run" | "walk" | "stop";
  start_offset_s: number;
  duration_s: number;
  distance_m: number;
  avg_pace_s_per_km: number | null;
  avg_cadence_spm: number | null;
  hr_start: number | null;
  hr_end: number | null;
  hr_avg: number | null;
  hr_max: number | null;
  hr_recovery_60s: number | null;
  hr_overshoot_bpm: number | null;
}

export interface ActivityMetrics {
  run_time_s: number;
  walk_time_s: number;
  stop_time_s: number;
  run_distance_m: number;
  walk_distance_m: number;
  run_block_count: number;
  longest_run_s: number;
  longest_run_m: number;
  avg_run_pace_s_per_km: number | null;
  avg_run_cadence_spm: number | null;
  pace_discipline_pct: number | null;
  hr_over_ceiling_pct: number | null;
  avg_hr_recovery_60s: number | null;
  avg_hr_overshoot_bpm: number | null;
  algorithm_version: number;
}

export interface Activity {
  id: number;
  garmin_activity_id: number | null;
  source: string;
  sport: string;
  started_at: string;
  local_date: string;
  total_distance_m: number;
  total_timer_s: number;
  total_elapsed_s: number;
  avg_hr: number | null;
  max_hr: number | null;
  avg_cadence_spm: number | null;
  calories: number | null;
  metrics: ActivityMetrics | null;
  segments?: Segment[];
  total_ascent_m?: number | null;
  total_descent_m?: number | null;
  chart_notes?: ChartNotes;
}

export interface StreamPoint {
  offset_s: number;
  distance_m: number | null;
  speed_mps: number | null;
  cadence_spm: number | null;
  heart_rate: number | null;
  altitude_m: number | null;
  latitude: number | null;
  longitude: number | null;
}

export interface Athlete {
  id: number;
  username: string;
  display_name: string;
  timezone: string;
  resting_hr: number | null;
  max_hr: number | null;
  easy_pace_min: number;
  easy_pace_max: number;
  hr_easy_min: number;
  hr_easy_max: number;
  hr_ceiling: number;
  run_cadence_threshold: number;
  training_days: Record<string, string>;
  running_days_per_week: number;
  day_type_labels: Record<string, string>;
  garmin_connected: boolean;
  garmin_last_sync: string | null;
}

export interface Race {
  id: number;
  name: string;
  race_date: string;
  distance_m: number;
  distance_label: string;
  location: string;
  goal: "finish" | "time";
  target_time_s: number | null;
  is_target: boolean;
  notes: string;
  days_until: number;
  weeks_until: number;
  is_past: boolean;
  week_number: number | null;
}

export interface DailyLog {
  id: number;
  log_date: string;
  text: string;
  alcohol_units: number | null;
  sleep_hours: number | null;
  felt: string;
  created_at: string;
}

export interface PlannedSession {
  date: string;
  kind: "intervals" | "long" | "rest" | "race";
  title: string;
  detail: string;
  plan_week: number;
  weeks_out: number;
  phase: string;
  note: string;
  run_minutes: number;
  distance_km: number;
  target_pace: string;
  target_hr: string;
  total_minutes: number;
  focus: string;
  adjusted: boolean;
  adjust_reason: string;
}

export interface TrendPoint {
  date: string;
  distance_km: number;
  longest_run_min: number | null;
  run_pace_s: number | null;
  discipline_pct: number | null;
  hr_recovery: number | null;
}

export interface Dashboard {
  today: PlannedSession | null;
  tomorrow: PlannedSession | null;
  week: PlannedSession[];
  insights: { tone: string; headline: string; detail: string }[];
  trend: TrendPoint[];
  wellness: WellnessPoint[];
  activity_count: number;
  log_count: number;
  garmin_connected: boolean;
}

export interface GarminStatus {
  connected: boolean;
  name: string;
  error: string;
  last_sync: string | null;
}

export interface SyncResult {
  imported: number;
  skipped: number;
  failed: number;
  errors: string[];
  activity_ids: number[];
}

export interface ChartNote {
  tone: "good" | "warn" | "neutral";
  text: string;
}

export type ChartNotes = Record<
  "shape" | "route" | "pace" | "hr" | "cadence" | "elevation",
  ChartNote[]
>;


export interface WellnessPoint {
  date: string;
  sleep_hours: number | null;
  sleep_need_hours: number | null;
  sleep_deficit_hours: number | null;
  sleep_score: number | null;
  training_readiness: number | null;
  resting_hr: number | null;
  body_battery_high: number | null;
  load_ratio: number | null;
  training_status: string;
}

export interface CalendarDay {
  date: string;
  is_today: boolean;
  is_past: boolean;
  is_race: boolean;
  planned: PlannedSession | null;
  activities: {
    id: number; sport: string; distance_km: number; duration_s: number;
    run_blocks: number | null; longest_run_s: number | null; avg_run_pace_s: number | null;
  }[];
  wellness: {
    sleep_hours: number | null; sleep_score: number | null;
    training_readiness: number | null; resting_hr: number | null;
  } | null;
  log: { text: string; felt: string } | null;
}

export interface CalendarResponse {
  from: string; to: string; today: string;
  race_date: string | null;
  days: CalendarDay[];
}

export interface WarmupExercise {
  key: string; name: string; duration: string;
  muscles: string[]; primary: string; why: string; how: string;
}

export interface WarmupRoutine {
  total: string; intro: string;
  muscle_labels: Record<string, string>;
  exercises: WarmupExercise[];
}

export interface ComparePoint {
  km: number;
  pace: number | null;
  hr: number | null;
  cadence: number | null;
  elevation: number | null;
}

export interface CompareSeries {
  id: number;
  date: string;
  sport: string;
  distance_km: number;
  duration_s: number;
  avg_run_pace_s: number | null;
  longest_run_s: number | null;
  points: ComparePoint[];
}

export interface CompareResponse { activities: CompareSeries[]; }

export interface AchievementItem {
  key: string;
  name: string;
  description: string;
  group: string;
  unit: string;
  format: "number" | "duration" | "distance" | "percent";
  target: number;
  value: number;
  progress: number;
  earned: boolean;
  earned_on: string | null;
}

export interface AchievementBoard {
  earned_count: number;
  total: number;
  groups: { name: string; items: AchievementItem[] }[];
  recent: AchievementItem[];
}
