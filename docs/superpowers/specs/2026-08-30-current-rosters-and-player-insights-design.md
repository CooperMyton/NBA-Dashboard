# Current Rosters and Player Insights — Design

Replace the all-time player index on team pages with real 2026-27 rosters, add season stats, and
flag players primed to break out or regress.

## Problem

Team pages list every player who has ever appeared for a franchise — the Lakers roster shows Kareem
Abdul-Jabbar next to Luka Doncic. The balldontlie free tier cannot fix this. Its `/players`
endpoint accepts `team_ids[]` but has no season dimension: filtering the Lakers returns Carmelo
Anthony, Pau Gasol, Dwight Howard and Kurt Rambis alongside current players. This was verified
against the live API, not inferred from the docs, which claim otherwise. Paid tiers start at
$9.99/month and would break the project's $0 constraint.

## Data source: `nba_api`

`nba_api` reads `stats.nba.com`. It is free, needs no key, and carries current rosters, season
stats and advanced metrics. Verified working from the development machine:

- `commonteamroster(team_id, season="2026-27")` returns the current roster with `AGE` and `EXP`
  (years of experience) — 19 players for the Lakers. **2026-27 rosters are already published**, so
  the job targets the upcoming season directly.
- `leaguedashplayerstats(season, measure_type)` returns every player's season line in a single
  call — 582 players for 2025-26. `Base` supplies GP, MIN, PTS, REB, AST, FG3_PCT, FG3A;
  `Advanced` supplies TS_PCT and USG_PCT.

Roughly 38 requests total: 30 rosters plus 4 seasons x 2 measure types.

### Why this job is local-only

The NBA blocks datacenter IP ranges — AWS, GCP and Azure — which covers GitHub Actions and Render.
The job therefore runs from a developer machine and writes to the cloud database, exactly as the
existing data was loaded. It is deliberately **excluded from the nightly pipeline**; running it
there would fail every night. Rosters change slowly, so an occasional manual refresh is adequate.

`nba_api` is a normal dependency, but only this job imports it. Tests use recorded fixtures, so CI
never touches the network.

## Player identity

`nba_api` keys players by NBA's own id; the database keys them by balldontlie's. Matching is by
name, measured at **98.6%** (574 of 582) using case-, accent- and punctuation-insensitive
comparison with generational suffixes stripped. The misses are nickname-versus-legal-name cases:
"Nic Claxton" against Nicolas, "Alex Sarr" against Alexandre, "Bones Hyland" against Nah'Shon.

Matching runs in two passes:

1. Normalised full name.
2. Normalised last name plus current team, which resolves most nickname cases.

Anything still unmatched is inserted as a new player row. Every matched or inserted row stores
`nba_player_id`, so subsequent syncs join on a stable key and never repeat this work. The job logs
the unmatched count; a sudden rise signals an upstream change.

## Schema

- `players` gains `nba_player_id` (nullable, unique) and `roster_season` (nullable int). A player
  on a 2026-27 roster has `roster_season = 2026`; the ~5,300 historical players keep null. This is
  the "currently in the league" filter.
- New `player_season_stats`, unique on `(player_id, season)`: `team_id`, `games_played`,
  `minutes`, `points`, `rebounds`, `assists`, `fg3_pct`, `fg3a`, `ts_pct`, `usage_pct`.
- New `player_insights`, unique on `(player_id, season, kind)`: `kind` (`breakout` or
  `regression`), `score`, `detail` (the numbers behind the flag), `generated_at`.

Insights are precomputed by the job rather than derived per request, matching how
`season_projections` works. The existing unused `player_stats` per-game table is left untouched;
season aggregates are what this feature needs.

Alembic migration with a tested downgrade.

## Signals

Both are computed from `player_season_stats` over the four loaded seasons. Only players with a
`roster_season` are eligible — retired players are never flagged.

**Regression** compares a player's most recent TS% and 3P% against their own volume-weighted
baseline from prior seasons. `score` is the signed difference in percentage points; positive means
shooting above baseline and therefore likely to decline, negative means a bounce-back candidate.
A player is flagged when `abs(score) >= 4.0` percentage points. Eligibility requires at least 20
games and 100 three-point attempts in the recent season plus at least one prior season, so small
samples cannot dominate.

**Breakout** requires age <= 24 or experience <= 3 years and, comparing the two most recent
seasons, all of: minutes per game up, usage up, and per-36 production up, where per-36 production
is `(points + rebounds + assists) * 36 / minutes`. `score` is the per-36 production increase.
Players without a prior season (rookies) are ineligible — there is no trajectory to measure.

Each flag stores the numbers that produced it, so the UI can render "3P% .428 against .351 career
on 5.2 attempts" rather than a bare label.

## API

- `GET /api/v1/players` gains an `active` filter (`roster_season` is not null) and returns each
  player's most recent season stats when present.
- `GET /api/v1/players/insights?season=2025&kind=breakout|regression` returns flagged players with
  their supporting numbers, joined to team. `season` is the season the statistics came from, using
  the project's start-year convention — `2025` means 2025-26, the most recent completed season.
  The players themselves are on 2026-27 rosters.

  This route **must be declared before** `GET /players/{id}`. FastAPI matches in declaration order,
  so a later declaration would send `/players/insights` to the `{id}` handler and fail to parse
  "insights" as an integer, returning 422.
- The team detail roster needs no new endpoint. The page already lists players by team, so it
  passes `active=true` to `/players` and reads flags from the insights endpoint, composing the
  two client-side rather than widening the teams response.

Standard `{data, meta}` envelope. Business logic in services; routers stay thin.

## Frontend

- **Players page** — stats columns (GP, MIN, PTS, REB, AST, TS%), defaults to current players with
  a toggle for the full historical index, and a league-wide breakout/regression section.
- **Team detail** — roster filtered to current players with the same stat columns, and a badge on
  any flagged player.

Typed hooks (`usePlayerInsights`, extended `usePlayers`). No ad-hoc fetching in components.
Loading and error states throughout.

## Testing

- Two-pass name matching, including the known nickname cases and accented names
- Signal thresholds: low volume, missing prior season, rookies, exact boundary values
- Insight computation deterministic against fixtures
- API filtering and contract
- Pages render with mocked data

Tests construct provider dataclasses directly and inject them into the job, so no test imports
`nba_api` or performs network access. Only the pure payload-parsing helpers are unit-tested
against literal row dicts.

## Out of scope

Per-game box scores, injuries, contract or salary data, and any change to the win-probability
model. Player stats do not feed the game model — that remains team-level, as documented in the
season projection spec.
