# Season Projection — Backtest Results

How accurate is the Season Projection? This replays the projection pipeline on completed seasons
and scores it. Design and rationale: `superpowers/specs/2026-09-02-projection-backtest-design.md`.

## Method

For each held-out season, a fresh logistic-regression model is trained on **strictly earlier games
only**, team state (Elo, form) is seeded from those games only, the season's real regular-season
schedule is simulated 300 times, and projected win totals are compared to actual ones. The model
registry is untouched. This avoids the leakage that would come from scoring the live model on
seasons it was trained on.

Metric: mean absolute error in regular-season wins across the 30 teams.

## Results

| Season | Training games | Projection MAE | Persistence baseline | League-mean baseline |
|---|---|---|---|---|
| 2024-25 | 1,319 (one prior season) | **8.53** | 9.13 | 10.63 |
| 2025-26 | 2,640 (two prior seasons) | **9.88** | 10.60 | 11.70 |

- **Persistence** = predict each team's win total from the previous season.
- **League mean** = predict every team at the league average (no skill).

The projection beats persistence by 0.6–0.7 wins and the no-skill baseline by about two wins in
both seasons. That is a modest, consistent edge — not a large one. The Season Projection page
states this next to the projection it qualifies.

## Reading the numbers honestly

- Two seasons is a small sample. Treat these as an estimate of accuracy, not a guarantee.
- 2024-25 is projected from a single season of training data, which is thin; the model had only
  1,319 games to learn from.
- 2025-26's higher absolute error reflects a higher-variance season (the league-mean baseline is
  also worse), not necessarily a worse model — the gap to both baselines is similar in both years.
- Team strength enters purely as carried-over Elo and form. Roster changes, trades and the draft
  are not modelled, which is the most obvious source of remaining error and the clearest place a
  future improvement could be measured against this table.

## Reproduce

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run python -m ml.pipeline.backtest
# BACKTEST_SEASONS=2024,2025 and BACKTEST_SIMULATIONS=300 are the defaults
```

Takes about nine minutes for both seasons. Prints a JSON summary; per-team rows are available from
`BacktestResult.rows` if you call `backtest_season` directly.
