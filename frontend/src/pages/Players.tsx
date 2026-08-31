import { useMemo, useState } from "react";

import type { Player, PlayerInsight } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { Card, EmptyState, PageHeader, SectionTitle, TeamMark } from "../components/ui";
import { QueryState } from "../components/QueryState";
import { usePlayerInsights } from "../hooks/usePlayerInsights";
import { usePlayers } from "../hooks/usePlayers";
import { useTeams } from "../hooks/useTeams";
import { DEFAULT_SEASON } from "../lib/constants";
import { formatPct } from "../lib/format";
import { teamColor } from "../lib/teamColors";

/** Renders one decimal place, or an em dash when the player has no stat line. */
function statCell(value: number | undefined, digits = 1): string {
  return value === undefined ? "—" : value.toFixed(digits);
}

const PAGE_SIZE = 25;

const INSIGHT_SECTIONS = [
  { title: "Primed to break out", kind: "breakout" as const },
  { title: "Regression candidates", kind: "regression" as const },
];

/** One breakout/regression candidate row, colour-tagged with its team. */
function InsightRow({ insight }: { insight: PlayerInsight }) {
  return (
    <li className="py-2">
      <div className="flex items-center gap-2">
        <TeamMark color={teamColor(insight.team_abbreviation)} abbr={insight.team_abbreviation ?? "FA"} />
        <span className="font-semibold">
          {insight.first_name} {insight.last_name}
        </span>
      </div>
      <p className="text-sm text-fg-muted">{insight.detail}</p>
    </li>
  );
}

export default function Players() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);

  const teams = useTeams({ limit: 100 });
  const teamById = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );

  const query = usePlayers({
    search: search || undefined,
    active: activeOnly,
    limit: PAGE_SIZE,
    offset,
  });

  const breakouts = usePlayerInsights({ season: DEFAULT_SEASON, kind: "breakout" });
  const regressions = usePlayerInsights({ season: DEFAULT_SEASON, kind: "regression" });
  const insightQueries = { breakout: breakouts, regression: regressions };

  const columns: Column<Player>[] = [
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
    { key: "team", header: "Team", render: (p) => (p.team_id ? (teamById.get(p.team_id) ?? "—") : "FA") },
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

  return (
    <div>
      <PageHeader
        eyebrow="The League"
        title="Players"
        subtitle={
          activeOnly
            ? "Current NBA rosters, plus the breakout and regression candidates our models are watching."
            : "A searchable index of players across NBA history. Try a name."
        }
      />

      {activeOnly && (
        <div className="mb-8 grid gap-4 sm:grid-cols-2">
          {INSIGHT_SECTIONS.map(({ title, kind }) => (
            <Card key={kind} title={title}>
              <QueryState query={insightQueries[kind]}>
                {(page) =>
                  page.data.length === 0 ? (
                    <EmptyState message="No candidates for this season." />
                  ) : (
                    <ul className="divide-y divide-border">
                      {page.data.slice(0, 10).map((insight) => (
                        <InsightRow key={`${insight.player_id}-${insight.kind}`} insight={insight} />
                      ))}
                    </ul>
                  )
                }
              </QueryState>
            </Card>
          ))}
        </div>
      )}

      <SectionTitle>{activeOnly ? "Current roster" : "All-time index"}</SectionTitle>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label htmlFor="search" className="sr-only">
          Search players
        </label>
        <input
          id="search"
          type="search"
          placeholder="Search by name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
          className="w-full max-w-xs rounded-full border border-border bg-surface px-4 py-1.5 text-sm focus-visible:border-accent"
        />

        <div className="inline-flex rounded-full border border-border p-0.5 text-sm">
          <button
            type="button"
            onClick={() => {
              setActiveOnly(true);
              setOffset(0);
            }}
            aria-pressed={activeOnly}
            className={`rounded-full px-4 py-1 transition-colors ${
              activeOnly ? "bg-accent text-accent-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            Current players
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveOnly(false);
              setOffset(0);
            }}
            aria-pressed={!activeOnly}
            className={`rounded-full px-4 py-1 transition-colors ${
              !activeOnly ? "bg-accent text-accent-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            All time
          </button>
        </div>
      </div>

      <QueryState query={query}>
        {(page) =>
          page.data.length === 0 ? (
            <EmptyState message="No players found." />
          ) : (
            <>
              <DataTable columns={columns} rows={page.data} rowKey={(p) => p.id} caption="Players" />
              <div className="mt-3 flex items-center justify-between text-sm text-fg-muted">
                <span>
                  {page.meta.offset + 1}–{page.meta.offset + page.data.length} of {page.meta.total}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    disabled={offset === 0}
                    className="rounded-full border border-border px-4 py-1 transition-colors hover:bg-surface-2 disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                    disabled={!page.meta.has_more}
                    className="rounded-full border border-border px-4 py-1 transition-colors hover:bg-surface-2 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )
        }
      </QueryState>
    </div>
  );
}
