# Data Source

> Required by the spec **before any ETL code is written**. Locks the provider, its auth, rate
> limits, and exactly which data is/ isn't available on our (free) tier.

## Provider: balldontlie.io (NBA), Free tier

- **Why this provider:** ToS-compliant, documented, and does **not** block datacenter/CI IPs — so
  nightly ETL works from GitHub Actions and any cloud host. `stats.nba.com`/`nba_api` is not used for
  games or the model because it blocks cloud/CI IPs and has undocumented ToS (D-001). It is used,
  narrowly, for current rosters and per-season player stats via a local-only job, because
  balldontlie Free has no season dimension for players. See [`decisions.md`](./decisions.md) D-017.
- **Cost:** $0 (Free tier).
- **Base URL:** `https://api.balldontlie.io/v1`
- **Auth:** API key sent in the `Authorization` header (raw key, no `Bearer` prefix). Key obtained
  by signing up at balldontlie.io. Stored **only** in the `BALLDONTLIE_API_KEY` env var — never
  committed. Listed in `.env.example`.
- **Rate limit:** **5 requests/minute** on Free. The single provider client enforces a token-bucket
  limiter at ≤5/min and logs every throttled request (per spec).

## What the Free tier includes (and how we use it)

| Endpoint | Feeds table | Notes |
|---|---|---|
| `GET /teams` | `teams` | Full 30-team list; seldom changes. |
| `GET /players` | `players` | Roster/bio (name, position, team, height/weight). Paginated. |
| `GET /games` | `games` | Date, home/away team, **final scores**, status, season. The workhorse endpoint. |

## What Free does NOT include, and our $0 compensation

| Not available on Free | Gated at | Our approach |
|---|---|---|
| `standings` | GOAT $39.99/mo | **Derive** from `games` (W/L, win %, streak, rank). D-004 |
| Team box scores (`team_stats`) | GOAT | **Derive** points for/against + net rating from `games` scores. D-005 |
| Player box scores (`player_stats`) | ALL-STAR $9.99/mo | Deferred to stretch; schema kept, fixtures for tests. D-006 |
| `injuries` | ALL-STAR $9.99/mo | Deferred to stretch; schema kept. D-006 |
| Odds / props / play-by-play | GOAT | Out of scope. |

## Access rules (per spec)

- **All** external calls go through the single client module in `/etl/client/`. Nothing else in the
  codebase calls balldontlie directly.
- Client responsibilities: auth header injection, token-bucket rate limiting (≤5/min), retry with
  exponential backoff on 429/5xx, structured logging of every request and every throttle.

## Historical backfill strategy (given 5 req/min)

- `games` is paginated (up to 100 rows/page via cursor). A full backfill of ~5 seasons of regular
  season games ≈ 6,000 games ≈ ~60 requests ≈ **~13 minutes** at 5 req/min — a one-time cost, run
  once with the limiter.
- Nightly incremental sync pulls only the current date's games — a handful of requests. Idempotent
  upserts (`INSERT ... ON CONFLICT DO UPDATE`) make re-runs safe (spec requirement).

## ToS / compliance

- Use only documented balldontlie endpoints; no page scraping. No sharing or committing the API
  key. Respect the published rate limit at all times.
