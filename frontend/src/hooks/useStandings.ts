import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Standing } from "../api/types";

export interface StandingFilters {
  season?: number;
  conference?: string;
  limit?: number;
  offset?: number;
}

export function useStandings(filters: StandingFilters = {}) {
  return useQuery({
    queryKey: ["standings", filters],
    queryFn: () => apiGet<Paged<Standing>>("/standings", { ...filters }),
  });
}
