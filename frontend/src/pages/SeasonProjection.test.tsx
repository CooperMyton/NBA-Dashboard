import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SeasonProjection from "./SeasonProjection";

vi.mock("../hooks/useProjections", () => ({
  useProjections: () => ({
    data: {
      data: [
        {
          id: 1,
          season: 2026,
          team_id: 37,
          model_version: "m.pkl",
          proj_wins: 55.2,
          proj_losses: 24.8,
          wins_p10: 49,
          wins_p50: 55,
          wins_p90: 61,
          make_playoffs_pct: 92.5,
          win_conference_pct: 24.0,
          win_title_pct: 12.5,
          avg_seed: 2.4,
          simulations: 2000,
        },
        {
          id: 2,
          season: 2026,
          team_id: 58,
          model_version: "m.pkl",
          proj_wins: 33.4,
          proj_losses: 46.6,
          wins_p10: 27,
          wins_p50: 33,
          wins_p90: 40,
          make_playoffs_pct: 18.0,
          win_conference_pct: 1.0,
          win_title_pct: 0.4,
          avg_seed: 11.2,
          simulations: 2000,
        },
      ],
      meta: { total: 2 },
    },
    isPending: false,
    isError: false,
  }),
}));

vi.mock("../hooks/useTeams", () => ({
  useTeams: () => ({
    data: {
      data: [
        {
          id: 37,
          abbreviation: "ATL",
          name: "Hawks",
          full_name: "Atlanta Hawks",
          city: "Atlanta",
          conference: "East",
          division: "Southeast",
        },
        {
          id: 58,
          abbreviation: "POR",
          name: "Trail Blazers",
          full_name: "Portland Trail Blazers",
          city: "Portland",
          conference: "West",
          division: "Northwest",
        },
      ],
      meta: { total: 2 },
    },
    isPending: false,
    isError: false,
  }),
}));

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SeasonProjection />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SeasonProjection", () => {
  it("renders a team's projected record and title odds", () => {
    renderPage();
    expect(screen.getByText("Atlanta Hawks")).toBeInTheDocument();
    expect(screen.getByText("55-25")).toBeInTheDocument();
    expect(screen.getAllByText("12.5%").length).toBeGreaterThan(0);
  });

  it("splits teams into their conferences", () => {
    renderPage();
    expect(screen.getByText("Eastern Conference")).toBeInTheDocument();
    expect(screen.getByText("Western Conference")).toBeInTheDocument();
  });

  it("states the no-roster limitation", () => {
    renderPage();
    expect(screen.getByText(/no roster moves, trades/i)).toBeInTheDocument();
  });
});
