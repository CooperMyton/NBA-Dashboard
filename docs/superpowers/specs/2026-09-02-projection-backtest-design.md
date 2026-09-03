# Projection Backtest — Design

Score the season projection on completed seasons so its accuracy is a measured number rather than
a claim that cannot be checked until June.

## Problem

The Season Projection page simulates 2026-27 and reports win totals, playoff odds and title odds.
Nothing on the site says how good those numbers are, and nothing can until the season ends. A
projection with no error bar attached is a demo, not a result.

## Approach

Replay the projection pipeline on seasons whose outcomes are known — 2024-25 and 2025-26 — and
compare projected win totals to actual ones.

### Leakage is the whole difficulty

The active model was trained on games from every loaded season, including the ones being tested.
Scoring the projection with that model would measure how well it recalls games it has already seen.
So each held-out season gets a **fresh logistic-regression model trained only on strictly earlier
games**, and team state (Elo, form) is seeded from those earlier games only. The model registry is
never touched; the backtest models are discarded after scoring.

This is the same pipeline the live projection runs — `build_training_data`, `train_by_name`,
`FeatureBuilder`, `run_simulations` — pointed at a truncated history. If any of those change, the
backtest re-measures the change for free.

### What is scored

Regular-season win totals only. Playoff and title odds cannot be scored on a sample of two seasons
with one champion each; win totals give thirty observations per season.

Metric: mean absolute error in wins across the thirty teams.

### Baselines

An error of "6.9 wins" means nothing on its own. Two baselines make it interpretable:

- **League mean** — predict every team at the average. Any forecast with skill beats this.
- **Persistence** — predict every team's win total from last season. The cheapest sensible
  forecast, and the one a projection must beat to justify existing.

### Simulation count

300 runs per season rather than the live job's 2,000. Win-total error needs far less resolution
than playoff odds, and simulation noise at 300 runs is well under one win. Each season takes a
couple of minutes.

## Deliverables

- `ml/pipeline/backtest.py` — the pure scorer `evaluate_projection` plus an orchestrating
  `backtest_season` and a `main` that prints a JSON summary. No database writes.
- Unit tests on the scorer: the error arithmetic, both baselines, the missing-prior-season case,
  and the no-overlap error.
- The measured results recorded in `README.md` and stated on the Season Projection page, so the
  claim ships next to the projection it qualifies.

## Limits

Two seasons is a small sample; the number is an estimate of accuracy, not a guarantee. 2024-25 is
projected from a single season of training data, which is thin. Both are stated where the result is
shown.
