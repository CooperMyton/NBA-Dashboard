# Season Projection — Design

Project 2026-27 records, standings, and playoff outcomes by simulating the loaded schedule with
the active win-probability model.

## Goal

The 2026-27 schedule (1,200 scheduled games) is loaded and each game already has a single-game
prediction. This feature answers the season-level questions those per-game picks cannot: how many
games will each team win, who makes the playoffs, and who wins the title.

## Approach

Monte Carlo simulation of the full regular season plus postseason, repeated many times. Each
simulation samples every game's outcome from the model's probability and lets team strength evolve
as those simulated results land, so streaks compound the way a real season does.

### Why reuse `FeatureBuilder`

The simulation drives the existing `ml.pipeline.features.FeatureBuilder` rather than reimplementing
the 12 features. This guarantees games are scored exactly as they were during training. A vectorised
numpy rewrite would allow far more simulations, but would duplicate feature logic and reintroduce
the risk of training and simulation silently diverging. Fidelity beats simulation count here.

The cost is that the job is O(simulations x 1,200 games) at Python speed. Default **2,000
simulations** (~1% resolution on playoff odds). Measured runtime is **~15 minutes** for the full
2,000 on the 1,200-game schedule. This is an offline job run on demand, never in the request path
and not part of the nightly pipeline, so that cost is acceptable; drop `PROJECTION_SIMULATIONS` to
a few hundred for a faster, noisier refresh.

### Simulation loop

Per run:

1. Seed a `FeatureBuilder` from all completed history. Elo carries across seasons, as it already
   does for `predict_upcoming`.
2. Walk the 2026-27 regular season in date order. For each game: build features, get P(home win),
   sample the outcome, then `observe()` the simulated result so Elo and rolling form update.
3. Seed each conference by wins.
4. Run the play-in: 7v8 winner takes the 7 seed; 9v10 loser is eliminated; the 7v8 loser hosts the
   9v10 winner for the 8 seed.
5. Run three best-of-7 rounds per conference (first round, semi-finals, conference finals), then
   an inter-conference Finals. Home court to the higher seed in every series.
6. Record wins, final seed, made playoffs, won conference, won title.

Aggregate across runs into per-team rates.

### Known simplifications

These are deliberate, and the page states them.

- **Tiebreakers.** Real NBA tiebreakers (head-to-head, division, conference record) are not modelled.
  Ties are broken randomly within each simulation, which reflects the genuine uncertainty rather
  than inventing precision.
- **No rosters.** The balldontlie free tier exposes an all-time player index with no season or
  active-roster dimension, and no player stats. Independently, none of the 12 features consume
  player data. Team strength is therefore carried-over Elo plus form only — no trades, draft,
  free agency, or injuries.
- **80-game schedule.** The loaded 2026-27 schedule holds 1,200 games — exactly 80 per team, not
  the NBA's 82 (1,230 total). Projected records are therefore out of 80 and will read low against
  real-world expectations. The page labels the total explicitly. If the provider later exposes the
  full schedule, re-syncing and re-running the job is the only change needed.
- **Postseason dates.** Playoff games are scored using dates after the regular-season end; rest-day
  features are approximate in the postseason.

## Data model

New table `season_projections`, one row per `(season, team_id, model_version)`:

| Column | Notes |
|---|---|
| `season`, `team_id`, `model_version` | unique together |
| `proj_wins`, `proj_losses` | mean across simulations |
| `wins_p10`, `wins_p50`, `wins_p90` | uncertainty range without storing a histogram |
| `make_playoffs_pct`, `win_conference_pct`, `win_title_pct` | |
| `avg_seed` | mean final conference seed by record, 1-15; defined for every team, not just qualifiers |
| `simulations`, `generated_at` | provenance |

Alembic migration with a tested downgrade, matching the existing migration convention.

## API

`GET /api/v1/projections?season=2026` returns projections joined to teams, using the standard
`{data, meta}` envelope. Business logic sits in a service; the router stays thin.

## Frontend

New `/projection` page, "Season Projection", added to the nav:

- Projected standings for each conference, team-coloured: projected record, playoff %, title %
- Title-odds leaderboard (top 10)
- Win-total range bars driven by p10-p90, so uncertainty is visible rather than implied
- A one-line note stating the no-roster limitation

Data via a typed `useProjections` hook. No ad-hoc fetching in components. Loading and error states
throughout, consistent with the existing Hardwood pages.

## Testing

- Simulation is deterministic under a fixed seed
- Play-in advancement and best-of-7 bracket logic
- Aggregate sanity: title percentages across all teams sum to ~100%; every team's
  `make_playoffs_pct` is between 0 and 100; exactly 16 teams advance per simulation
- API endpoint contract and filtering
- Page renders with mocked data

## Out of scope

Player-level modelling, roster construction, trades, injuries, and real NBA tiebreakers. Each would
be its own project.
