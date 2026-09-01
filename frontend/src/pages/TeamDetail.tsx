import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import type { Game, Player, PlayerInsight } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { QueryState } from "../components/QueryState";
import { Card, EmptyState, Stat } from "../components/ui";
import { useGames } from "../hooks/useGames";
import { usePlayerInsights } from "../hooks/usePlayerInsights";
import { usePlayers } from "../hooks/usePlayers";
import { useStandings } from "../hooks/useStandings";
import { useTeam, useTeams } from "../hooks/useTeams";
import { DEFAULT_SEASON } from "../lib/constants";
import { formatDate, formatPct, formatSeason } from "../lib/format";
import { insightBadge } from "../lib/insights";
import { teamColor } from "../lib/teamColors";

/** Renders one decimal place, or an em dash when the player has no stat line. */
function statCell(value: number | undefined, digits = 1): string {
  return value === undefined ? "—" : value.toFixed(digits);
}

export default function TeamDetail() {
  const { id } = useParams();
  const teamId = id ? Number(id) : undefined;

  const team = useTeam(teamId);
  const teams = useTeams({ limit: 100 });
  const standings = useStandings({ season: DEFAULT_SEASON, limit: 100 });
  const games = useGames({ season: DEFAULT_SEASON, team_id: teamId, order: "desc", limit: 10 });
  const players = usePlayers({ team_id: teamId, active: true, limit: 30 });
  const insights = usePlayerInsights({ season: DEFAULT_SEASON, team_id: teamId });

  const teamAbbr = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );
  const standing = (standings.data?.data ?? []).find((s) => s.team_id === teamId);

  const insightByPlayer = useMemo(
    () => new Map((insights.data?.data ?? []).map((i) => [i.player_id, i])),
    [insights.data],
  );

  const rosterColumns: Column<Player>[] = [
    {
      key: "name",
      header: "Player",
      render: (p) => {
        const insight: PlayerInsight | undefined = insightByPlayer.get(p.id);
        const badge = insight ? insightBadge(insight) : null;
        return (
          <span className="font-medium">
            {p.first_name} {p.last_name}
            {insight && badge ? (
              <span
                title={insight.detail}
                className={`ml-2 rounded px-1.5 py-0.5 text-xs font-semibold ring-1 ${badge.className}`}
              >
                {badge.label}
              </span>
            ) : null}
          </span>
        );
      },
    },
    { key: "pos", header: "Pos", render: (p) => p.position ?? "—" },
    { key: "college", header: "College", render: (p) => p.college ?? "—" },
    { key: "country", header: "Country", render: (p) => p.country ?? "—" },
    {
      key: "gp",
      header: "GP",
      align: "right",
      render: (p) => (
        <span className="tabular">
          {p.latest_stats ? p.latest_stats.games_played : "—"}
        </span>
      ),
    },
    {
      key: "min",
      header: "MIN",
      align: "right",
      render: (p) => <span className="tabular">{statCell(p.latest_stats?.minutes)}</span>,
    },
    {
      key: "pts",
      header: "PTS",
      align: "right",
      render: (p) => <span className="tabular">{statCell(p.latest_stats?.points)}</span>,
    },
    {
      key: "reb",
      header: "REB",
      align: "right",
      render: (p) => <span className="tabular">{statCell(p.latest_stats?.rebounds)}</span>,
    },
    {
      key: "ast",
      header: "AST",
      align: "right",
      render: (p) => <span className="tabular">{statCell(p.latest_stats?.assists)}</span>,
    },
    {
      key: "ts",
      header: "TS%",
      align: "right",
      render: (p) => (
        <span className="tabular">
          {p.latest_stats ? formatPct(p.latest_stats.ts_pct) : "—"}
        </span>
      ),
    },
  ];

  const gameLine = (g: Game): string => {
    const away = teamAbbr.get(g.visitor_team_id) ?? "?";
    const home = teamAbbr.get(g.home_team_id) ?? "?";
    return `${away} ${g.visitor_team_score ?? ""} @ ${home} ${g.home_team_score ?? ""}`;
  };

  return (
    <div>
      <Link to="/teams" className="eyebrow inline-block hover:text-fg">
        ← All teams
      </Link>

      <QueryState query={team}>
        {(res) => {
          const t = res.data;
          const color = teamColor(t.abbreviation);
          return (
            <>
              <div
                className="mt-3 mb-8 rounded-lg border border-border bg-surface p-6"
                style={{ borderLeft: `5px solid ${color}` }}
              >
                <div className="eyebrow" style={{ color }}>
                  {t.conference} · {t.division}
                </div>
                <h1 className="mt-1 font-display text-4xl font-semibold tracking-tight">
                  {t.full_name}
                </h1>
                <p className="mt-1 text-fg-muted">
                  {t.city} · {formatSeason(DEFAULT_SEASON)}
                </p>
              </div>

              <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat
                  label="Record"
                  value={standing ? `${standing.wins}-${standing.losses}` : "—"}
                  accent={color}
                />
                <Stat label="Win %" value={standing ? formatPct(standing.win_pct) : "—"} />
                <Stat
                  label="Conf. rank"
                  value={standing?.conference_rank ?? "—"}
                  hint={standing?.streak ? `streak ${standing.streak}` : undefined}
                />
                <Stat
                  label="Home / Road"
                  value={standing ? `${standing.home_record}` : "—"}
                  hint={standing?.road_record ? `road ${standing.road_record}` : undefined}
                />
              </div>

              <div className="mb-8">
                <Card title="Recent Games">
                  <QueryState query={games}>
                    {(page) =>
                      page.data.length === 0 ? (
                        <EmptyState message="No games for this season." />
                      ) : (
                        <ul className="divide-y divide-border">
                          {page.data.map((g) => (
                            <li key={g.id} className="flex justify-between py-2 text-sm">
                              <span className="tabular">{gameLine(g)}</span>
                              <span className="text-fg-muted">{formatDate(g.game_date)}</span>
                            </li>
                          ))}
                        </ul>
                      )
                    }
                  </QueryState>
                </Card>
              </div>

              <Card title="Current roster">
                <QueryState query={players}>
                  {(page) =>
                    page.data.length === 0 ? (
                      <EmptyState message="No roster data." />
                    ) : (
                      <DataTable columns={rosterColumns} rows={page.data} rowKey={(p) => p.id} />
                    )
                  }
                </QueryState>
              </Card>
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
