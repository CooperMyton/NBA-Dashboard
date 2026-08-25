import { useMemo, useState } from "react";

import type { Game, Prediction, Standing } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { QueryState } from "../components/QueryState";
import { Card, EmptyState, PageHeader, Stat, TeamMark } from "../components/ui";
import { useGames } from "../hooks/useGames";
import { useModelRegistry } from "../hooks/useModelRegistry";
import { useAllPredictions } from "../hooks/usePredictions";
import { useStandings } from "../hooks/useStandings";
import { useTeams } from "../hooks/useTeams";
import { AVAILABLE_SEASONS, DEFAULT_SEASON, UPCOMING_SEASON } from "../lib/constants";
import { formatDate, formatPct, formatSeason } from "../lib/format";
import { teamColor } from "../lib/teamColors";

const byRank = (a: Standing, b: Standing) =>
  (a.conference_rank ?? 99) - (b.conference_rank ?? 99);

function ProbBar({ homeProb, homeColor, awayColor }: { homeProb: number; homeColor: string; awayColor: string }) {
  return (
    <div className="flex h-1.5 overflow-hidden rounded-full">
      <span style={{ width: `${homeProb * 100}%`, backgroundColor: homeColor }} />
      <span style={{ width: `${(1 - homeProb) * 100}%`, backgroundColor: awayColor }} />
    </div>
  );
}

export default function Dashboard() {
  const [season, setSeason] = useState<number>(DEFAULT_SEASON);

  const registry = useModelRegistry();
  const standings = useStandings({ season, limit: 100 });
  const games = useGames({ season, status: "Final", order: "desc", limit: 6 });
  const teams = useTeams({ limit: 100 });
  const upcoming = useAllPredictions({ settled: false });
  const openers = useGames({ season: UPCOMING_SEASON, order: "asc", limit: 10 });

  const teamAbbr = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );
  const predByGame = useMemo(
    () => new Map((upcoming.data?.data ?? []).map((p) => [p.game_id, p])),
    [upcoming.data],
  );

  const active = registry.data?.versions.find((v) => v.version === registry.data?.active);
  const accuracy = active?.metrics.accuracy ?? null;

  const standingColumns: Column<Standing>[] = [
    { key: "rank", header: "#", render: (s) => s.conference_rank ?? "—" },
    {
      key: "team",
      header: "Team",
      render: (s) => {
        const abbr = teamAbbr.get(s.team_id);
        return <TeamMark color={teamColor(abbr)} abbr={abbr ?? `#${s.team_id}`} />;
      },
    },
    { key: "wl", header: "W-L", render: (s) => `${s.wins}-${s.losses}` },
    { key: "pct", header: "PCT", align: "right", render: (s) => formatPct(s.win_pct) },
    { key: "streak", header: "Strk", render: (s) => s.streak ?? "—" },
  ];

  const renderGame = (g: Game) =>
    `${teamAbbr.get(g.visitor_team_id) ?? "?"} ${g.visitor_team_score ?? ""} @ ` +
    `${teamAbbr.get(g.home_team_id) ?? "?"} ${g.home_team_score ?? ""}`;

  const opener = (g: Game): Prediction | undefined => predByGame.get(g.id);

  return (
    <div>
      <PageHeader
        eyebrow="Season Overview"
        title={`${formatSeason(season)} Season`}
        subtitle="Standings, recent results, and how the model reads the league."
        right={
          <label className="flex items-center gap-2 text-sm">
            <span className="eyebrow">Season</span>
            <select
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
              className="rounded-md border border-border bg-surface px-3 py-1.5 font-medium focus-visible:border-accent"
              aria-label="Select season"
            >
              {AVAILABLE_SEASONS.map((y) => (
                <option key={y} value={y}>
                  {formatSeason(y)}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat
          label="Model accuracy"
          value={accuracy === null ? "—" : formatPct(accuracy)}
          hint={active ? active.algorithm.replace(/_/g, " ") : undefined}
          accent="var(--color-accent)"
        />
        <Stat label="Games tracked" value={games.data?.meta.total ?? "—"} hint="this season" />
        <Stat
          label="Upcoming picks"
          value={upcoming.data?.meta.total ?? "—"}
          hint={`${formatSeason(UPCOMING_SEASON)} schedule`}
        />
      </div>

      <div className="mb-8">
        <Card title={`${formatSeason(UPCOMING_SEASON)} — Season Openers · Model Picks`}>
          <QueryState query={openers}>
            {(page) =>
              page.data.length === 0 ? (
                <EmptyState message="No upcoming games scheduled yet." />
              ) : (
                <ul className="space-y-3">
                  {page.data.map((g) => {
                    const pred = opener(g);
                    const homeAbbr = teamAbbr.get(g.home_team_id);
                    const awayAbbr = teamAbbr.get(g.visitor_team_id);
                    const homeColor = teamColor(homeAbbr);
                    const awayColor = teamColor(awayAbbr);
                    const p = pred?.predicted_home_win_prob;
                    const pickAbbr = pred?.predicted_home_win ? homeAbbr : awayAbbr;
                    const pickPct = p === undefined ? null : Math.round(Math.max(p, 1 - p) * 100);
                    return (
                      <li key={g.id} className="grid grid-cols-[1fr_auto] items-center gap-4">
                        <div>
                          <div className="flex items-center gap-2 text-sm">
                            <TeamMark color={awayColor} abbr={awayAbbr ?? "?"} />
                            <span className="text-fg-muted">@</span>
                            <TeamMark color={homeColor} abbr={homeAbbr ?? "?"} />
                            <span className="ml-2 text-xs text-fg-muted">{formatDate(g.game_date)}</span>
                          </div>
                          {p !== undefined && (
                            <div className="mt-1.5 max-w-xs">
                              <ProbBar homeProb={p} homeColor={homeColor} awayColor={awayColor} />
                            </div>
                          )}
                        </div>
                        <div className="text-right text-sm">
                          {pickPct === null ? (
                            <span className="text-fg-muted">—</span>
                          ) : (
                            <>
                              <span className="font-semibold">{pickAbbr}</span>{" "}
                              <span className="tabular text-fg-muted">{pickPct}%</span>
                            </>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )
            }
          </QueryState>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <QueryState query={standings}>
          {(page) => {
            const east = page.data.filter((s) => s.conference === "East").sort(byRank).slice(0, 8);
            const west = page.data.filter((s) => s.conference === "West").sort(byRank).slice(0, 8);
            if (page.data.length === 0) {
              return (
                <Card title="Standings">
                  <EmptyState message="No standings for this season yet." />
                </Card>
              );
            }
            return (
              <>
                <Card title="Eastern Conference">
                  <DataTable columns={standingColumns} rows={east} rowKey={(s) => s.id} />
                </Card>
                <Card title="Western Conference">
                  <DataTable columns={standingColumns} rows={west} rowKey={(s) => s.id} />
                </Card>
              </>
            );
          }}
        </QueryState>
      </div>

      <div className="mt-4">
        <Card title="Recent Results">
          <QueryState query={games}>
            {(page) =>
              page.data.length === 0 ? (
                <EmptyState message="No completed games for this season yet." />
              ) : (
                <ul className="divide-y divide-border">
                  {page.data.map((g) => (
                    <li key={g.id} className="flex items-center justify-between py-2.5 text-sm">
                      <span className="tabular font-medium">{renderGame(g)}</span>
                      <span className="text-fg-muted">{formatDate(g.game_date)}</span>
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryState>
        </Card>
      </div>
    </div>
  );
}
