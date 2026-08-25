import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged, type Single } from "../api/client";
import type { Team } from "../api/types";

export interface TeamFilters {
  conference?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

export function useTeams(filters: TeamFilters = {}) {
  return useQuery({
    queryKey: ["teams", filters],
    queryFn: () => apiGet<Paged<Team>>("/teams", { ...filters }),
  });
}

export function useTeam(teamId: number | undefined) {
  return useQuery({
    queryKey: ["team", teamId],
    queryFn: () => apiGet<Single<Team>>(`/teams/${teamId}`),
    enabled: teamId !== undefined,
  });
}
