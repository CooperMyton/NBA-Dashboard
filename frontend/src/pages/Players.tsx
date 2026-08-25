import { useMemo, useState } from "react";

import type { Player } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, PageHeader } from "../components/ui";
import { QueryState } from "../components/QueryState";
import { usePlayers } from "../hooks/usePlayers";
import { useTeams } from "../hooks/useTeams";

const PAGE_SIZE = 25;

export default function Players() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const teams = useTeams({ limit: 100 });
  const teamById = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );

  const query = usePlayers({ search: search || undefined, limit: PAGE_SIZE, offset });

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
  ];

  return (
    <div>
      <PageHeader
        eyebrow="The League"
        title="Players"
        subtitle="A searchable index of players across NBA history. Try a name."
      />

      <div className="mb-4">
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
