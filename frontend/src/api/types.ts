// Mirrors the backend Pydantic response schemas (backend/app/schemas/*).

export interface Team {
  id: number;
  abbreviation: string;
  name: string;
  full_name: string;
  city: string;
  conference: string;
  division: string;
}

export interface Player {
  id: number;
  first_name: string;
  last_name: string;
  position: string | null;
  height: string | null;
  weight: string | null;
  jersey_number: string | null;
  college: string | null;
  country: string | null;
  team_id: number | null;
  roster_season: number | null;
}

export interface PlayerInsight {
  player_id: number;
  first_name: string;
  last_name: string;
  team_id: number | null;
  team_abbreviation: string | null;
  season: number;
  kind: "breakout" | "regression";
  score: number;
  detail: string;
}

export interface Game {
  id: number;
  season: number;
  game_date: string;
  start_time: string | null;
  status: string;
  postseason: boolean;
  period: number | null;
  home_team_id: number;
  visitor_team_id: number;
  home_team_score: number | null;
  visitor_team_score: number | null;
}

export interface Standing {
  id: number;
  season: number;
  team_id: number;
  wins: number;
  losses: number;
  win_pct: number;
  conference: string | null;
  conference_rank: number | null;
  home_record: string | null;
  road_record: string | null;
  streak: string | null;
}

export interface Prediction {
  id: number;
  game_id: number;
  model_version: string;
  predicted_home_win_prob: number;
  predicted_home_win: boolean;
  actual_home_win: boolean | null;
  is_correct: boolean | null;
  predicted_at: string;
  settled_at: string | null;
}

export interface ModelVersion {
  version: number;
  filename: string;
  date: string;
  algorithm: string;
  metrics: { accuracy: number; log_loss: number; brier: number; n: number };
  features: string[];
  training_window: { seasons: number[] | null; n_train: number };
  git_commit: string;
}

export interface ModelRegistry {
  active: number | null;
  versions: ModelVersion[];
}

export interface Projection {
  id: number;
  season: number;
  team_id: number;
  model_version: string;
  proj_wins: number;
  proj_losses: number;
  wins_p10: number;
  wins_p50: number;
  wins_p90: number;
  make_playoffs_pct: number;
  win_conference_pct: number;
  win_title_pct: number;
  avg_seed: number;
  simulations: number;
}
