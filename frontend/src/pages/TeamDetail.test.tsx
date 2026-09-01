import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import TeamDetail from "./TeamDetail";

vi.mock("../hooks/useTeams", () => ({
  useTeam: () => ({
    data: {
      data: {
        id: 1,
        abbreviation: "LAL",
        full_name: "Los Angeles Lakers",
        city: "Los Angeles",
        conference: "West",
        division: "Pacific",
      },
    },
    isLoading: false,
    isPending: false,
    isError: false,
  }),
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

vi.mock("../hooks/useGames", () => ({
  useGames: () => ({
    data: {
      data: [],
      meta: { total: 0, limit: 10, offset: 0, has_more: false },
    },
    isLoading: false,
    isPending: false,
    isError: false,
  }),
}));

vi.mock("../hooks/useStandings", () => ({
  useStandings: () => ({
    data: {
      data: [],
      meta: { total: 0, limit: 100, offset: 0, has_more: false },
    },
    isLoading: false,
    isPending: false,
    isError: false,
  }),
}));

vi.mock("../hooks/usePlayers", () => ({
  usePlayers: () => ({
    data: {
      data: [
        {
          id: 1,
          first_name: "Luka",
          last_name: "Doncic",
          position: "G",
          college: "—",
          country: "Slovenia",
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
          college: "UCLA",
          country: "USA",
          team_id: 1,
          roster_season: 2026,
          latest_stats: null,
        },
      ],
      meta: { total: 2, limit: 30, offset: 0, has_more: false },
    },
    isLoading: false,
    isPending: false,
    isError: false,
  }),
}));

vi.mock("../hooks/usePlayerInsights", () => ({
  usePlayerInsights: () => ({
    data: {
      data: [
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
        {
          player_id: 2,
          first_name: "Kareem",
          last_name: "Abdul-Jabbar",
          team_id: 1,
          team_abbreviation: "LAL",
          season: 2025,
          kind: "regression",
          score: -9.0,
          detail: "3P% 0.300 against a 0.400 baseline",
        },
      ],
      meta: { total: 2, limit: 50, offset: 0, has_more: false },
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
      <MemoryRouter initialEntries={["/teams/1"]}>
        <Routes>
          <Route path="/teams/:id" element={<TeamDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TeamDetail", () => {
  it("labels a flagged player on the roster", () => {
    renderPage();
    expect(screen.getByText(/breakout/i)).toBeInTheDocument();
  });

  it("labels a negative-score regression insight as bounce-back, not breakout or decline", () => {
    renderPage();
    const badge = screen.getByText("bounce-back");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("text-win");
    expect(badge.className).not.toContain("text-loss");
    expect(screen.queryByText("regression")).not.toBeInTheDocument();
  });

  it("shows an em dash for a player with no stats instead of NaN", () => {
    renderPage();
    const row = screen.getByText("Kareem Abdul-Jabbar").closest("tr");
    expect(row).not.toBeNull();
    const cells = Array.from(row!.querySelectorAll("td")).map((cell) => cell.textContent);
    expect(cells).not.toContain("NaN");
    expect(cells).not.toContain("undefined");
    expect(cells.some((text) => text?.includes("—"))).toBe(true);
  });
});
