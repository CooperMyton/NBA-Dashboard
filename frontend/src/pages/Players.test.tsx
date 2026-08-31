import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Players from "./Players";

vi.mock("../hooks/usePlayers", () => ({
  usePlayers: () => ({
    data: {
      data: [
        {
          id: 1,
          first_name: "Luka",
          last_name: "Doncic",
          position: "G",
          team_id: 1,
          roster_season: 2026,
        },
      ],
      meta: { total: 1, limit: 25, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/usePlayerInsights", () => ({
  usePlayerInsights: ({ kind }: { kind?: string }) => ({
    data: {
      data:
        kind === "breakout"
          ? [
              {
                player_id: 1,
                first_name: "Luka",
                last_name: "Doncic",
                team_id: 1,
                team_abbreviation: "LAL",
                season: 2025,
                kind: "breakout",
                score: 3.2,
                detail: "18.0 to 28.0 minutes",
              },
            ]
          : [],
      meta: { total: 1, limit: 50, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/useTeams", () => ({
  useTeams: () => ({
    data: {
      data: [{ id: 1, abbreviation: "LAL", full_name: "Los Angeles Lakers" }],
      meta: { total: 1, limit: 100, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Players />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Players", () => {
  it("renders the player table", () => {
    renderPage();
    expect(screen.getAllByText(/Doncic/).length).toBeGreaterThan(0);
  });

  it("shows a breakout candidate with its supporting detail", () => {
    renderPage();
    expect(screen.getByText("18.0 to 28.0 minutes")).toBeInTheDocument();
  });
});
