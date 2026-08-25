import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { useMemo } from "react";
import { Line } from "react-chartjs-2";

import type { Prediction } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { Card, EmptyState, PageHeader } from "../components/ui";
import { QueryState } from "../components/QueryState";
import { useGames } from "../hooks/useGames";
import { useAllPredictions } from "../hooks/usePredictions";
import { useTeams } from "../hooks/useTeams";
import { AVAILABLE_SEASONS } from "../lib/constants";
import { formatPct } from "../lib/format";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

const AXIS = "#ab9d8a";
const GRID = "#3a3025";
const ACCENT = "#e8622a";

function sortByTime(a: Prediction, b: Prediction): number {
  return (a.settled_at ?? a.predicted_at).localeCompare(b.settled_at ?? b.predicted_at);
}

function cumulativeAccuracy(settled: Prediction[]): number[] {
  let correct = 0;
  return settled.map((p, i) => {
    if (p.is_correct) correct += 1;
    return (correct / (i + 1)) * 100;
  });
}

const chartOptions: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      min: 0,
      max: 100,
      ticks: { color: AXIS, callback: (v) => `${v}%` },
      grid: { color: GRID },
    },
    x: { ticks: { color: AXIS, maxTicksLimit: 8 }, grid: { color: GRID } },
  },
  plugins: { legend: { labels: { color: AXIS } } },
};

export default function PredictionTracker() {
  const query = useAllPredictions({ settled: true });
  // Latest completed season's games cover the most recent settled predictions (for matchup labels).
  const games = useGames({ season: AVAILABLE_SEASONS[0], order: "desc", limit: 100 });
  const teams = useTeams({ limit: 100 });

  const teamAbbr = useMemo(
    () => new Map((teams.data?.data ?? []).map((t) => [t.id, t.abbreviation])),
    [teams.data],
  );
  const gameById = useMemo(
    () => new Map((games.data?.data ?? []).map((g) => [g.id, g])),
    [games.data],
  );

  const rows = useMemo(() => query.data?.data ?? [], [query.data]);
  const settled = useMemo(() => rows.filter((p) => p.is_correct !== null).sort(sortByTime), [rows]);

  const chartData: ChartData<"line"> = useMemo(
    () => ({
      labels: settled.map((_, i) => String(i + 1)),
      datasets: [
        {
          label: "Cumulative accuracy",
          data: cumulativeAccuracy(settled),
          borderColor: ACCENT,
          backgroundColor: ACCENT,
          tension: 0.25,
          pointRadius: 0,
        },
      ],
    }),
    [settled],
  );

  const matchup = (p: Prediction): string => {
    const g = gameById.get(p.game_id);
    if (!g) return `Game #${p.game_id}`;
    return `${teamAbbr.get(g.visitor_team_id) ?? "?"} @ ${teamAbbr.get(g.home_team_id) ?? "?"}`;
  };

  const recent = [...settled].reverse().slice(0, 12);
  const columns: Column<Prediction>[] = [
    { key: "matchup", header: "Matchup", render: matchup },
    { key: "prob", header: "P(home)", align: "right", render: (p) => formatPct(p.predicted_home_win_prob) },
    { key: "pick", header: "Pick", render: (p) => (p.predicted_home_win ? "Home" : "Away") },
    { key: "actual", header: "Actual", render: (p) => (p.actual_home_win ? "Home" : "Away") },
    {
      key: "result",
      header: "Result",
      render: (p) => (
        <span className={p.is_correct ? "text-win" : "text-loss"}>{p.is_correct ? "✓" : "✗"}</span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Prediction Tracker" subtitle="How the model's picks have held up over time" />
      <QueryState query={query}>
        {(page) =>
          page.data.length === 0 ? (
            <EmptyState message="No predictions yet. Run the prediction and settlement jobs." />
          ) : settled.length === 0 ? (
            <EmptyState message="Predictions exist but none are settled yet — check back after games finish." />
          ) : (
            <div className="grid grid-cols-1 gap-4">
              <Card title="Cumulative accuracy">
                <div className="h-64">
                  <Line data={chartData} options={chartOptions} aria-label="Cumulative accuracy chart" />
                </div>
              </Card>
              <Card title="Recent settled predictions">
                <DataTable
                  columns={columns}
                  rows={recent}
                  rowKey={(p) => p.id}
                  caption="Recent settled predictions"
                />
              </Card>
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
