import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import type { Game, Player } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { QueryState } from "../components/QueryState";
import { Card, EmptyState, Stat } from "../components/ui";
import { useGames } from "../hooks/useGames";
import { usePlayers } from "../hooks/usePlayers";
import { useStandings } from "../hooks/useStandings";
import { useTeam, useTeams } from "../hooks/useTeams";
import { DEFAULT_SEASON } from "../lib/constants";
import { formatDate, formatPct, formatSeason } from "../lib/format";
import { teamColor } from "../lib/teamColors";

export default function TeamDetail() {
  const { id } = useParams();
  const teamId = id ? Number(id) : undefined;

  const team = useTeam(teamId);
  const teams = useTeams({ limit: 100 });
  const standings = useStandings({ season: DEFAULT_SEASON, limit: 100 });
  const games = useGames({ season: DEFAULT_SEASON, team_id: teamId, order: "desc", limit: 10 });
  const players = usePlayers({ team_id: teamId, limit: 30 });

  const teamAbbr = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );
  const standing = (standings.data?.data ?? []).find((s) => s.team_id === teamId);

  const rosterColumns: Column<Player>[] = [
    {
      key: "name",
      header: "Player",
      render: (p) => (
        <span className="font-medium">
          {p.first_name} {p.last_name}
        </span>
      ),
    },
    { key: "pos", header: "Pos", render: (p) => p.position ?? "—" },
    { key: "college", header: "College", render: (p) => p.college ?? "—" },
    { key: "country", header: "Country", render: (p) => p.country ?? "—" },
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

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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

                <Card title="Roster">
                  <QueryState query={players}>
                    {(page) =>
                      page.data.length === 0 ? (
                        <EmptyState message="No roster data." />
                      ) : (
                        <DataTable
                          columns={rosterColumns}
                          rows={page.data}
                          rowKey={(p) => p.id}
                        />
                      )
                    }
                  </QueryState>
                </Card>
              </div>
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
