import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, PageHeader } from "../components/ui";
import { QueryState } from "../components/QueryState";
import { useStandings } from "../hooks/useStandings";
import { useTeams } from "../hooks/useTeams";
import { CONFERENCES, DEFAULT_SEASON } from "../lib/constants";
import { formatPct, formatSeason } from "../lib/format";
import { teamColor } from "../lib/teamColors";

export default function Teams() {
  const [conference, setConference] = useState<string>("");
  const teams = useTeams({ conference: conference || undefined, limit: 100 });
  const standings = useStandings({ season: DEFAULT_SEASON, limit: 100 });

  const standingByTeam = useMemo(
    () => new Map((standings.data?.data ?? []).map((s) => [s.team_id, s])),
    [standings.data],
  );

  return (
    <div>
      <PageHeader
        eyebrow="The League"
        title="Teams"
        subtitle={`Records shown for ${formatSeason(DEFAULT_SEASON)}. Select a team for the full picture.`}
        right={
          <label className="flex items-center gap-2 text-sm">
            <span className="eyebrow">Conference</span>
            <select
              value={conference}
              onChange={(e) => setConference(e.target.value)}
              className="rounded-md border border-border bg-surface px-3 py-1.5 font-medium focus-visible:border-accent"
            >
              <option value="">All</option>
              {CONFERENCES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <QueryState query={teams}>
        {(page) =>
          page.data.length === 0 ? (
            <EmptyState message="No teams found. Run the ETL to populate data." />
          ) : (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {page.data.map((t) => {
              const color = teamColor(t.abbreviation);
              const s = standingByTeam.get(t.id);
              return (
                <li key={t.id}>
                  <Link
                    to={`/teams/${t.id}`}
                    className="block h-full rounded-lg border border-border bg-surface p-4 transition-colors hover:border-fg-muted"
                    style={{ borderLeft: `3px solid ${color}` }}
                  >
                    <div className="flex items-baseline justify-between">
                      <span className="font-display text-2xl font-semibold">{t.abbreviation}</span>
                      {s?.conference_rank != null && (
                        <span className="eyebrow">
                          #{s.conference_rank} {t.conference}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 truncate text-sm text-fg-muted">{t.full_name}</div>
                    <div className="mt-3 tabular text-sm">
                      {s ? (
                        <>
                          <span className="font-semibold">
                            {s.wins}-{s.losses}
                          </span>{" "}
                          <span className="text-fg-muted">{formatPct(s.win_pct)}</span>
                        </>
                      ) : (
                        <span className="text-fg-muted">{t.city}</span>
                      )}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
          )
        }
      </QueryState>
    </div>
  );
}
