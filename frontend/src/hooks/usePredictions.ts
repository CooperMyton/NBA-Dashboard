import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Prediction } from "../api/types";

export interface PredictionFilters {
  game_id?: number;
  model_version?: string;
  limit?: number;
  offset?: number;
}

export function usePredictions(filters: PredictionFilters = {}) {
  return useQuery({
    queryKey: ["predictions", filters],
    queryFn: () => apiGet<Paged<Prediction>>("/predictions", { ...filters }),
  });
}

export interface PredictionsResult {
  data: Prediction[];
  meta: { total: number };
}

/**
 * Fetch predictions across pages (API caps limit at 100). Bounded by `maxPages` so the ML
 * pages get a rich sample without unbounded requests.
 */
export function useAllPredictions(opts: { maxPages?: number; settled?: boolean } = {}) {
  const { maxPages = 12, settled } = opts;
  return useQuery<PredictionsResult>({
    queryKey: ["predictions-all", maxPages, settled],
    queryFn: async () => {
      const all: Prediction[] = [];
      let offset = 0;
      let total = 0;
      for (let page = 0; page < maxPages; page += 1) {
        const res = await apiGet<Paged<Prediction>>("/predictions", {
          limit: 100,
          offset,
          settled,
        });
        all.push(...res.data);
        total = res.meta.total;
        if (!res.meta.has_more) break;
        offset += 100;
      }
      return { data: all, meta: { total } };
    },
  });
}
