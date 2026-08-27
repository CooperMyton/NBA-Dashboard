import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Projection } from "../api/types";

export function useProjections(season: number) {
  return useQuery({
    queryKey: ["projections", season],
    queryFn: () => apiGet<Paged<Projection>>("/projections", { season, limit: 50 }),
  });
}
