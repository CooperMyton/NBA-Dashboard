# Decision Log

> This file is authoritative for every choice the spec/design left open, per the spec's rule:
> *"Where a decision isn't specified here, Claude Code should choose the simplest option consistent
> with the rest of this spec and note the choice in `/docs/decisions.md`."*
> Where a decision here contradicts a statement in `NBA_Analytics_Claude_Code_Spec.md` or
> `NBA_Analytics_Design_Document.md`, **this file wins** and the superseded text is called out.
>
> Overriding constraint for all decisions below: **total running cost must be $0/month.**
> Last updated: 2026-08-03.

---

## Cost summary (target: $0/month)

| Concern | Choice | Cost |
|---|---|---|
| NBA data | balldontlie.io **Free tier** (API key required) | $0 |
| Postgres | Neon free tier (0.5 GB, scales to zero, no card) | $0 |
| Redis | Upstash free tier (serverless; verify caps at build time) | $0 |
| Backend/API host | Confirmed at Phase 5 — Render free (primary) / Fly.io / Cloud Run / HF Spaces | $0 |
| Frontend host | Cloudflare Pages or Vercel (static) | $0 |
| Nightly ETL | GitHub Actions **scheduled workflow** (not an always-on container) | $0 |
| CI/CD | GitHub Actions free tier | $0 |
| **Total** | | **$0/mo** |

No paid tier, no GPU, no expiring free trial in the critical path.

---

## D-001 — Data provider: balldontlie.io, Free tier

**Decision.** Use `balldontlie.io` on the **Free tier**. An API key is required even on free
(demonstrates authenticated, rate-limited API integration — a resume positive). Full provider
details in [`data_source.md`](./data_source.md).

**Free tier gives us:** `teams`, `players`, `games` (with final scores, date, home/away). Rate
limit **5 requests/minute**.

**Free tier does NOT give us** (all gated behind paid tiers): per-game player box scores
(`player_stats`), `injuries` (ALL-STAR, $9.99/mo), and the `standings`, team box scores, odds,
play-by-play (GOAT, $39.99/mo).

**Rationale.** `games` with scores is sufficient to build the entire win-probability model and to
*derive* standings and team stats ourselves (see D-004/D-005). balldontlie is explicitly
ToS-compliant and does not block datacenter IPs, so it works from GitHub Actions and any cloud host
— unlike `stats.nba.com`/`nba_api`, which blocks cloud/CI IPs and would break nightly ETL.

**Supersedes.** Spec §"Data Source" and design §1 offered "`balldontlie.io` **or** `stats.nba.com`
wrapper" as interchangeable. They are not; balldontlie Free is chosen and `stats.nba.com` is
rejected (cloud IP blocking + murky ToS).

---

## D-002 — ML prediction target: home-team win probability

**Decision.** The model predicts **P(home team wins)** for a scheduled game — a **binary
classification** problem. `POST /model/predict` returns a probability in `[0,1]` plus the implied
pick.

**Rationale.** Clean, unambiguous label (every completed game has a winner); directly justifies the
spec's chosen metrics (log loss, calibration/Brier); yields a meaningful, beatable baseline
(D-003); and powers the Prediction Tracker page (rolling accuracy + calibration curve). Regression
on point spread or player props were rejected for v1 — harder to present well and (props) needs
paid player data.

**Fills gap.** Neither source doc stated the target variable. This unblocks Phase 3 and the
`model_predictions` schema.

---

## D-003 — Baseline: majority class (home team always wins)

**Decision.** Baseline predicts "home team wins" for every game (historically ~57–58%). A trained
model must beat this on the held-out set (accuracy AND log loss) before it is eligible for
registration, per spec.

---

## D-004 — `standings` is a DERIVED table, computed from `games`

**Decision.** `standings` rows are computed by an ETL job from `games` (wins, losses, win %,
current streak, conference rank), not fetched from the provider.

**Rationale.** The provider's standings endpoint is GOAT-tier ($39.99/mo). Deriving standings from
game results costs $0 and is a stronger data-engineering signal than re-serving a vendor endpoint.

**Supersedes.** Spec/design treated `standings` as a fetched, cached core table. It remains a core
table with the same schema and caching; only its *source* changes to derivation.

---

## D-005 — `team_stats` is DERIVED from `games` scores

**Decision.** `team_stats` (per team per game: points for, points allowed, win/loss, home/away,
and season-to-date net rating) is derived from `games` final scores. Advanced box-score team stats
are out of scope for v1 (GOAT-gated).

---

## D-006 — `player_stats` and `injuries` deferred to stretch

**Decision.** Keep both **table definitions and Alembic migrations** (so the schema/migration work
still ships), but **do not populate them in v1** — their source data is paid (ALL-STAR, $9.99/mo).
Tests use committed fixtures in `/backend/seeds`. The Players page shows roster/bio data (free)
rather than box scores in v1.

**Upgrade path (documented, not built):** either subscribe to balldontlie ALL-STAR, or do a
one-time historical backfill via `nba_api` from a residential IP into seed data. Tracked as a
stretch task.

**Supersedes.** Spec lists `player_stats`/`injuries` as populated core tables and design §3 gives
them relationships; in v1 they are schema-only.

---

## D-007 — Auth: seeded API keys via admin CLI, no public registration

**Decision.** `users` holds hashed API keys. Keys are minted by an **admin CLI script**
(`python -m backend.scripts.mint_api_key`) that inserts a hash; there is **no public
registration/signup flow**. `POST /model/predict` validates the `X-API-Key` header against the
stored hash.

**Rationale.** Demonstrates the resume-relevant parts (hashed secrets, header auth, middleware)
without building signup, email verification, or account management. Resolves the spec's
"if API keys/accounts are in scope" ambiguity.

---

## D-008 — Prediction settlement/grading job

**Decision.** Add an ETL job that, after final scores land, updates each `model_predictions` row
with the actual outcome and a correct/incorrect flag. Prediction Tracker reads these settled rows
for rolling accuracy and a calibration curve.

**Fills gap.** Neither doc described how predictions get graded against actual results; the
Prediction Tracker page requires it.

---

## D-009 — Cache invalidation: ETL deletes Redis keys by prefix

**Decision.** ETL and API share one Redis. After a successful load, the ETL job deletes cache keys
by prefix (`standings:*`, `predictions:*`, `teams:*`, ...). No pub/sub.

**Fills gap.** Design §4 said caches invalidate "on next ETL load" but ETL is a separate process
and can't invalidate in-process; explicit cross-process deletion is the mechanism.

---

## D-010 — `season` stored as integer start year

**Decision.** `season` is an integer = the season's start year (`2024` ⇒ the 2024–25 season),
matching balldontlie's `season` parameter. Format to `"2024–25"` only at the presentation layer.

---

## D-011 — Mobile (Phase 6) and monorepo tooling deferred to stretch

**Decision.** Descope the React Native/Expo app and the `/packages/api-client` monorepo tooling to
**stretch**. v1 ships the web app, API, ETL, ML, Docker, and CI/CD. Keep the plain repo layout; no
Turborepo/workspaces until mobile is actually taken on.

**Rationale.** The web + API + ETL + ML + Docker + CI/CD story is already a complete, coherent
full-stack portfolio. React Native adds weeks for marginal resume gain over the existing web app.

**Supersedes.** Spec Phase 6 and design §8 — retained as stretch, not v1.

---

## D-012 — `mypy` wired explicitly into CI

**Decision.** Add `mypy` to the CI lint job (backend), required to pass with zero errors.

**Fills gap.** Dev Rules require mypy to pass, but it was absent from the tech-stack list and CI's
explicit tool list.

---

## D-013 — Single deployed cloud environment; keep the manual-approval gate pattern

**Decision.** To stay free, provision **one** deployed environment (call it `prod`) rather than
separate `staging` + `prod` instances. `dev` remains local via `docker compose`. Keep the GitHub
Actions **environment protection / manual-approval gate** in the pipeline so the "promote to prod"
workflow is still demonstrated; it simply gates the single environment.

**Rationale.** Two always-on managed environments cost money; one free environment plus a
demonstrated approval gate keeps both the $0 budget and the CI/CD resume story.

**Supersedes.** Spec/design "auto-deploy to staging, manual prod" — collapsed to one env with the
approval gate retained. Recorded in [`deployment.md`](./deployment.md).

---

## D-014 — ETL scheduling: GitHub Actions scheduled workflow in the cloud

**Decision.** Nightly ETL in the cloud runs as a **GitHub Actions scheduled workflow** that
executes the ETL against the Neon database. The cron-in-a-container approach is used only for local
`docker compose` dev.

**Rationale.** No always-on cron container to host (free), and balldontlie tolerates CI IPs. This is
the "fallback documented in deployment.md" from design §5, promoted to the primary cloud mechanism.

---

## D-015 — Single root `uv` project (one `pyproject.toml`, one `uv.lock`)

**Decision.** One root `pyproject.toml` manages `backend`, `etl`, and `ml` as importable
top-level packages with a single committed `uv.lock`, rather than a `pyproject.toml` per package.
Configured as a non-package app (`[tool.uv] package = false`).

**Rationale.** The spec requires "a lockfile committed" (singular). ETL/ML still run as independent
processes (`python -m etl.jobs.sync_games`) and deploy independently (the GitHub Actions ETL job
installs the root project and runs the module) — independent *execution* doesn't require separate
*projects*. One lock is simpler to keep reproducible for a solo build.

**Supersedes.** Design §2 diagram showed `pyproject.toml` under `/backend`; it lives at the repo
root instead.

---

## D-016 — Phase 2 API scope: read endpoints now, `POST /model/predict` with Phase 3

**Decision.** Phase 2 ships the public read endpoints — `/teams`, `/teams/{id}`, `/players`,
`/players/{id}`, `/games`, `/games/{id}`, `/standings`, `/predictions`, plus `/health` and
`/ready`. `POST /model/predict` and its `X-API-Key` auth + the mint-key admin CLI (D-007) are
**deferred to Phase 3**, since the endpoint needs the active registered model to return anything.

**Additions beyond the spec's endpoint list.** `GET /standings` (the spec omits it but design §4
explicitly caches standings, and the frontend needs it) and `GET /games/{id}` (natural detail
counterpart). Both are supersets, not conflicts.

**Contract implemented.** Shared envelope (`data`/`meta`) + error shape
(`error.code`/`error.message`); `limit`/`offset` pagination (default 25, max 100); filtering +
sorting per resource; Redis read-through cache on `/standings` and `/predictions`; sliding-window
60 req/min/IP rate limit on all resource routes; `/health` liveness vs `/ready` DB+Redis readiness.

**Coverage gate.** CI enforces `--cov-fail-under=80` on `backend` (currently ~90%).

---

## Still open (resolve at the noted phase, not before)

- **Backend host** — final pick among Render free / Fly.io / Cloud Run / HF Spaces, confirmed
  before Phase 5 once cold-start and free-tier terms are re-checked. See `deployment.md`.
- **Retraining cadence + drift trigger** — finalized in `ml_lifecycle.md` before Phase 3 sign-off
  (current plan: weekly retrain + Brier-drift trigger).
