import {
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

import type { ModelVersion, Prediction } from "../api/types";
import { DataTable, type Column } from "../components/DataTable";
import { Card, EmptyState, PageHeader } from "../components/ui";
import { QueryState } from "../components/QueryState";
import { useModelRegistry } from "../hooks/useModelRegistry";
import { useAllPredictions } from "../hooks/usePredictions";
import { formatPct } from "../lib/format";

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

const ACCENT = "#e8622a";
const AXIS = "#ab9d8a";
const GRID = "#3a3025";

interface Bucket {
  x: number; // mean predicted %
  y: number; // actual home-win %
}

function calibration(rows: Prediction[]): Bucket[] {
  const settled = rows.filter((p) => p.actual_home_win !== null);
  const buckets: Bucket[] = [];
  for (let lo = 0; lo < 100; lo += 10) {
    const hi = lo + 10;
    const inBin = settled.filter((p) => {
      const pct = p.predicted_home_win_prob * 100;
      return pct >= lo && (hi === 100 ? pct <= hi : pct < hi);
    });
    if (inBin.length < 5) continue;
    const meanPred = inBin.reduce((s, p) => s + p.predicted_home_win_prob, 0) / inBin.length;
    const actual = inBin.filter((p) => p.actual_home_win).length / inBin.length;
    buckets.push({ x: meanPred * 100, y: actual * 100 });
  }
  return buckets;
}

const chartOptions: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      type: "linear",
      min: 0,
      max: 100,
      title: { display: true, text: "Predicted home-win %", color: AXIS },
      ticks: { color: AXIS, callback: (v) => `${v}%` },
      grid: { color: GRID },
    },
    y: {
      min: 0,
      max: 100,
      title: { display: true, text: "Actual home-win %", color: AXIS },
      ticks: { color: AXIS, callback: (v) => `${v}%` },
      grid: { color: GRID },
    },
  },
  plugins: { legend: { labels: { color: AXIS } } },
};

const versionColumns: Column<ModelVersion>[] = [
  {
    key: "algo",
    header: "Model",
    render: (v) => <span className="font-semibold capitalize">{v.algorithm.replace(/_/g, " ")}</span>,
  },
  { key: "acc", header: "Accuracy", align: "right", render: (v) => formatPct(v.metrics.accuracy) },
  { key: "ll", header: "Log loss", align: "right", render: (v) => v.metrics.log_loss.toFixed(3) },
  { key: "brier", header: "Brier", align: "right", render: (v) => v.metrics.brier.toFixed(3) },
  { key: "n", header: "Eval n", align: "right", render: (v) => v.metrics.n },
];

export default function ModelLab() {
  const registry = useModelRegistry();
  const predictions = useAllPredictions({ settled: true });

  const rows = useMemo(() => predictions.data?.data ?? [], [predictions.data]);
  const buckets = useMemo(() => calibration(rows), [rows]);

  const active = registry.data?.versions.find((v) => v.version === registry.data?.active);

  const chartData: ChartData<"line"> = {
    datasets: [
      {
        label: "Perfectly calibrated",
        data: [
          { x: 0, y: 0 },
          { x: 100, y: 100 },
        ],
        borderColor: GRID,
        borderDash: [5, 5],
        pointRadius: 0,
      },
      {
        label: "Model",
        data: buckets,
        borderColor: ACCENT,
        backgroundColor: ACCENT,
        showLine: true,
        pointRadius: 4,
        tension: 0.2,
      },
    ],
  };

  return (
    <div>
      <PageHeader
        eyebrow="Under the Hood"
        title="Model Lab"
        subtitle="How the win-probability model is built, and how well its confidence holds up."
      />

      <QueryState query={registry}>
        {(reg) =>
          reg.versions.length === 0 ? (
            <EmptyState message="No models registered yet." />
          ) : (
            <div className="grid grid-cols-1 gap-6">
              <Card title="Candidate Models — Held-out Evaluation">
                <p className="mb-3 text-sm text-fg-muted">
                  Each training run trains and scores multiple algorithms on a time-based holdout;
                  the strongest is promoted. Active model:{" "}
                  <span className="font-semibold text-fg capitalize">
                    {active?.algorithm.replace(/_/g, " ") ?? "—"}
                  </span>
                  .
                </p>
                <DataTable columns={versionColumns} rows={reg.versions} rowKey={(v) => v.version} />
              </Card>

              <Card title="Calibration — Reliability Curve">
                <p className="mb-4 text-sm text-fg-muted">
                  Each point is a bucket of games; well-calibrated predictions sit on the dashed
                  line (predicted probability ≈ actual outcome rate).
                </p>
                {buckets.length === 0 ? (
                  <EmptyState message="No settled predictions to calibrate yet." />
                ) : (
                  <div className="h-72">
                    <Line data={chartData} options={chartOptions} aria-label="Calibration curve" />
                  </div>
                )}
              </Card>

              {active && (
                <Card title="Features">
                  <ul className="flex flex-wrap gap-2">
                    {active.features.map((f) => (
                      <li
                        key={f}
                        className="rounded-full border border-border bg-surface-2 px-3 py-1 text-xs text-fg-muted"
                      >
                        {f.replace(/_/g, " ")}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
