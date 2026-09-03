import { useMemo } from "react";

import { DataTable, type Column } from "../components/DataTable";
import { QueryState } from "../components/QueryState";
import { EmptyState, PageHeader, SectionTitle, TeamMark } from "../components/ui";
import { useProjections } from "../hooks/useProjections";
import { useTeams } from "../hooks/useTeams";
import type { Projection, Team } from "../api/types";
import { CONFERENCES, UPCOMING_SEASON } from "../lib/constants";
import { formatSeason } from "../lib/format";
import { teamColor } from "../lib/teamColors";

/** A projection joined to its team. */
interface Row extends Projection {
  team?: Team;
}

/** The API returns percentages as 0-100, so `formatPct` (which expects a fraction) is wrong here. */
function pct(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

/** Horizontal bar sized to a 0-100 percentage, tinted with the team's colour. */
function OddsBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2"
        role="presentation"
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.max(value, 1)}%`, backgroundColor: color }}
        />
      </div>
      <span className="tabular w-12 text-right text-xs text-fg-muted">{pct(value)}</span>
    </div>
  );
}

/**
 * Win-total range: p10 to p90, drawn across the widest range on the page so bars are
 * comparable between teams rather than each being scaled to itself.
 */
function WinRange({ row, min, max }: { row: Row; min: number; max: number }) {
  const span = Math.max(max - min, 1);
  const left = ((row.wins_p10 - min) / span) * 100;
  const width = Math.max(((row.wins_p90 - row.wins_p10) / span) * 100, 2);
  const median = ((row.wins_p50 - min) / span) * 100;
  const color = teamColor(row.team?.abbreviation ?? "");

  return (
    <div className="flex items-center gap-2">
      <div className="relative h-4 flex-1 min-w-24">
        <div className="absolute inset-x-0 top-1.5 h-1 rounded-full bg-surface-2" />
        <div
          className="absolute top-1.5 h-1 rounded-full opacity-70"
          style={{ left: `${left}%`, width: `${width}%`, backgroundColor: color }}
        />
        <div
          className="absolute top-0.5 h-3 w-0.5 rounded"
          style={{ left: `${median}%`, backgroundColor: color }}
        />
      </div>
      <span className="tabular w-16 text-right text-xs text-fg-muted">
        {Math.round(row.wins_p10)}-{Math.round(row.wins_p90)}
      </span>
    </div>
  );
}

export default function SeasonProjection() {
  const projections = useProjections(UPCOMING_SEASON);
  const teams = useTeams({ limit: 100 });

  const teamById = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t])),
    [teams.data],
  );

  const rows: Row[] = useMemo(
    () => (projections.data?.data ?? []).map((p) => ({ ...p, team: teamById.get(p.team_id) })),
    [projections.data, teamById],
  );

  const winBounds = useMemo(() => {
    if (rows.length === 0) return { min: 0, max: 1 };
    return {
      min: Math.min(...rows.map((r) => r.wins_p10)),
      max: Math.max(...rows.map((r) => r.wins_p90)),
    };
  }, [rows]);

  const simulations = rows[0]?.simulations ?? 0;
  const gamesPerTeam = Math.round((rows[0]?.proj_wins ?? 0) + (rows[0]?.proj_losses ?? 0));

  const columns: Column<Row>[] = [
    {
      key: "team",
      header: "Team",
      render: (row) => (
        <div className="flex items-center gap-2">
          <TeamMark color={teamColor(row.team?.abbreviation ?? "")} abbr={row.team?.abbreviation ?? "—"} />
          <span className="hidden sm:inline">{row.team?.full_name ?? `Team ${row.team_id}`}</span>
        </div>
      ),
    },
    {
      key: "record",
      header: "Proj. record",
      align: "right",
      render: (row) => (
        <span className="tabular">
          {Math.round(row.proj_wins)}-{Math.round(row.proj_losses)}
        </span>
      ),
    },
    {
      key: "range",
      header: "Win range (p10-p90)",
      render: (row) => <WinRange row={row} min={winBounds.min} max={winBounds.max} />,
    },
    {
      key: "playoffs",
      header: "Playoffs",
      align: "right",
      render: (row) => <span className="tabular">{pct(row.make_playoffs_pct)}</span>,
    },
    {
      key: "title",
      header: "Title",
      align: "right",
      render: (row) => <span className="tabular">{pct(row.win_title_pct, 1)}</span>,
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="The Season Ahead"
        title="Season Projection"
        subtitle={`${formatSeason(UPCOMING_SEASON)} simulated ${simulations.toLocaleString()} times, game by game, with team strength evolving as results land.`}
      />

      <p className="mb-6 max-w-3xl text-sm text-fg-muted">
        Team strength is carried forward from prior seasons — there are no roster moves, trades,
        draft picks, or injuries in this model, so treat it as a read on momentum rather than a
        forecast. The loaded schedule runs {gamesPerTeam || 80} games per team. Backtested on the
        last two completed seasons with a model trained only on earlier games, it missed win totals
        by 8.5 and 9.9 wins on average — a little better than carrying last season forward, and
        about two wins better than guessing the league average.
      </p>

      <QueryState query={projections}>
        {() =>
          rows.length === 0 ? (
            <EmptyState message="No projections have been generated for this season yet." />
          ) : (
            <div className="space-y-10">
              <section>
                <SectionTitle>Title odds</SectionTitle>
                <div className="grid gap-2 sm:grid-cols-2">
                  {[...rows]
                    .sort((a, b) => b.win_title_pct - a.win_title_pct)
                    .slice(0, 10)
                    .map((row) => (
                      <div
                        key={row.id}
                        className="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2"
                      >
                        <TeamMark
                          color={teamColor(row.team?.abbreviation ?? "")}
                          abbr={row.team?.abbreviation ?? "—"}
                        />
                        <OddsBar
                          value={row.win_title_pct}
                          color={teamColor(row.team?.abbreviation ?? "")}
                        />
                      </div>
                    ))}
                </div>
              </section>

              {CONFERENCES.map((conference) => {
                const conferenceRows = rows.filter((r) => r.team?.conference === conference);
                if (conferenceRows.length === 0) return null;
                return (
                  <section key={conference}>
                    <SectionTitle>{conference}ern Conference</SectionTitle>
                    <DataTable
                      columns={columns}
                      rows={conferenceRows}
                      rowKey={(row) => row.id}
                      caption={`Projected ${conference}ern Conference standings`}
                    />
                  </section>
                );
              })}
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
