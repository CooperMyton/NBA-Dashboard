import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Player } from "../api/types";

export interface PlayerFilters {
  team_id?: number;
  search?: string;
  active?: boolean;
  limit?: number;
  offset?: number;
}

export function usePlayers(filters: PlayerFilters = {}) {
  return useQuery({
    queryKey: ["players", filters],
    queryFn: () => apiGet<Paged<Player>>("/players", { ...filters }),
  });
}
