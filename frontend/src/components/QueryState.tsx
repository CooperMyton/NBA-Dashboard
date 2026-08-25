import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "../api/client";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
}

/** Renders loading / error consistently; calls children only with loaded data. */
export function QueryState<T>({ query, children }: QueryStateProps<T>) {
  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading" className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-xl border border-border bg-surface" />
        ))}
      </div>
    );
  }
  if (query.isError) {
    return (
      <div role="alert" className="rounded-2xl border border-loss/40 bg-loss/10 p-5 text-sm">
        <p className="font-semibold text-loss">We couldn&apos;t load this just now</p>
        <p className="mt-1 text-fg-muted">{errorMessage(query.error)}</p>
      </div>
    );
  }
  return <>{children(query.data)}</>;
}
