import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Game } from "../api/types";

export interface GameFilters {
  season?: number;
  team_id?: number;
  status?: string;
  start_date?: string;
  end_date?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export function useGames(filters: GameFilters = {}) {
  return useQuery({
    queryKey: ["games", filters],
    queryFn: () => apiGet<Paged<Game>>("/games", { ...filters }),
  });
}
