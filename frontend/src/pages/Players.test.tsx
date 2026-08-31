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
          latest_stats: {
            season: 2025,
            games_played: 70,
            minutes: 34.5,
            points: 28.6,
            rebounds: 8.2,
            assists: 8.8,
            ts_pct: 0.588,
            usage_pct: 0.31,
          },
        },
        {
          id: 2,
          first_name: "Kareem",
          last_name: "Abdul-Jabbar",
          position: "C",
          team_id: 1,
          roster_season: 2026,
          latest_stats: null,
        },
      ],
      meta: { total: 2, limit: 25, offset: 0, has_more: false },
    },
    isLoading: false,
    isPending: false,
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
    isPending: false,
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
    isPending: false,
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

  it("renders a player's latest season stats", () => {
    renderPage();
    expect(screen.getByText("28.6")).toBeInTheDocument();
    expect(screen.getByText("58.8%")).toBeInTheDocument();
  });

  it("shows an em dash for a player with no stats", () => {
    renderPage();
    const row = screen.getByText("Kareem Abdul-Jabbar").closest("tr");
    expect(row).not.toBeNull();
    const cells = Array.from(row!.querySelectorAll("td")).map((cell) => cell.textContent);
    expect(cells).not.toContain("NaN");
    expect(cells).not.toContain("undefined");
    expect(cells.filter((text) => text === "—").length).toBeGreaterThanOrEqual(6);
  });
});
