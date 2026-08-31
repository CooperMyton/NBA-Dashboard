import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { PlayerInsight } from "../api/types";

export interface PlayerInsightFilters {
  season: number;
  kind?: "breakout" | "regression";
}

export function usePlayerInsights({ season, kind }: PlayerInsightFilters) {
  return useQuery({
    queryKey: ["player-insights", season, kind],
    queryFn: () =>
      apiGet<Paged<PlayerInsight>>("/players/insights", { season, kind, limit: 50 }),
  });
}
