import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import type { Paged } from "../api/client";
import type { Team } from "../api/types";
import Teams from "./Teams";

const TEAMS: Paged<Team> = {
  data: [
    {
      id: 1,
      abbreviation: "BOS",
      name: "Celtics",
      full_name: "Boston Celtics",
      city: "Boston",
      conference: "East",
      division: "Atlantic",
    },
  ],
  meta: { total: 1, limit: 100, offset: 0, has_more: false },
};

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders teams returned by the API", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify(TEAMS), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  renderWithClient(<Teams />);

  expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Teams" })).toBeInTheDocument();
});

test("shows an empty state when there are no teams", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify({ data: [], meta: { total: 0, limit: 100, offset: 0, has_more: false } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  renderWithClient(<Teams />);

  expect(await screen.findByText(/No teams found/)).toBeInTheDocument();
});
