import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { PlayerInsight } from "../api/types";

export interface PlayerInsightFilters {
  season: number;
  kind?: "breakout" | "regression";
  team_id?: number;
  /** Set false to skip the request entirely, e.g. when the consuming section is hidden. */
  enabled?: boolean;
}

export function usePlayerInsights({ season, kind, team_id, enabled = true }: PlayerInsightFilters) {
  return useQuery({
    queryKey: ["player-insights", season, kind, team_id],
    queryFn: () =>
      apiGet<Paged<PlayerInsight>>("/players/insights", { season, kind, team_id, limit: 50 }),
    enabled,
  });
}
