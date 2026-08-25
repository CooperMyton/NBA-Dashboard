import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../api/client";
import type { ModelRegistry } from "../api/types";

export function useModelRegistry() {
  return useQuery({
    queryKey: ["model-registry"],
    queryFn: () => apiGet<{ data: ModelRegistry }>("/model/registry").then((r) => r.data),
  });
}
