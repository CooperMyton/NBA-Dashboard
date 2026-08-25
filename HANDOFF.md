# Hardwood (NBA Analytics Platform) — Handoff

> Continuation brief for a fresh chat. Read this top-to-bottom; it captures everything decided and
> built so far, how to run it, known gotchas, and what to do next.

## 1. What this project is

A **full-stack NBA analytics platform**, built as a **portfolio piece to help land a software job**.
Hard constraint: **must run at $0/month** on free tiers. It ingests NBA data, engineers features,
trains a calibrated win-probability model, serves it via an async API, and presents it in a polished
React app. Branded **"Hardwood."**

- **Prediction target:** P(home team wins) for a game — binary classification.
- **Data source:** [balldontlie.io](https://www.balldontlie.io/) **Free tier** (API key required; 5
  req/min). Only teams / players / games are available free; standings & team stats are **derived**
  from games. Player box scores & injuries are paid → deferred (schema exists, unused).
- **Working dir:** `C:\Users\Cooper\cld_powers` (Windows, PowerShell + Git Bash). **Not a git repo.**
- **Owner:** Cooper (cooper.myton@gmail.com).

## 2. Current status — everything below is DONE and verified

Phases 1–5 of the original spec are complete, plus a large enhancement pass. **80 backend tests + 4
frontend tests pass**; `ruff`, `black`, `mypy --strict` all clean; 80% backend coverage gate.

The full stack **runs in Docker and is currently up** with **real data loaded** (persisted in the
`pgdata` volume):

- Seasons **2023-24, 2024-25, 2025-26** games loaded (~1,300 games each) + derived standings
  (regular-season only) + team stats.
- **2026-27 schedule (1,200 scheduled games) loaded and predicted** (the season "about to start").
- **5,804 all-time NBA players** (cleaned of provider junk).
- **3,962 settled backtested predictions** + **1,200 upcoming 2026-27 predictions**.
- Trained model registry: **v1 logistic_regression (active, 70.6% acc)**, v2 gradient_boosting (67.2%).

Live locally: frontend **http://localhost:5173**, API docs **http://localhost:8000/docs**.

## 3. Architecture & repo layout

```
balldontlie (free) → ETL (rate-limited client, validate, idempotent upsert) → PostgreSQL 16
   → feature engineering → ML (train LR+GB → evaluate → register) → active model
   → FastAPI (async, Redis read-through cache + rate limit) → React + Vite + TanStack Query
Nightly flow: sync_teams → sync_games → derive_team_stats → derive_standings
              → settle_predictions → predict_upcoming → sync_players → invalidate cache
```

```
backend/   FastAPI (api/v1 routers, services, models, schemas, core, db), Alembic, scripts
etl/       provider client + rate limiter, jobs (sync_*, derive_*, settle/predict/backtest), pipeline
ml/        pipeline (features, baseline, train, evaluate, collect, registry, run_training, inference),
           registry.json + models/*.pkl artifacts
frontend/  React + Vite + TS + Tailwind + TanStack Query + Chart.js
docs/      decisions.md, data_source.md, ml_lifecycle.md, deployment.md
docker/    docker-compose.yml + Dockerfile.backend + Dockerfile.frontend (nginx)
tests/     backend / etl / ml suites
.github/workflows/  ci.yml (lint/type/test/build/GHCR/deploy), etl-nightly.yml
```

Authoritative design decisions live in **`docs/decisions.md`** (D-001…D-015). Read it before changing
data/model/deploy choices.

## 4. How to run & verify

**Tooling:** Python via **`uv`** (installed globally via pip because it wasn't present; managed Python
3.12). Node 22 / npm 11. Docker Desktop (WSL2 backend).

```bash
# Run the whole stack (Docker Desktop must be running & onboarded — see gotchas)
docker compose -f docker/docker-compose.yml up -d
#   frontend → http://localhost:5173   API → http://localhost:8000/docs

# Backend gates (run from repo root, prefix env for imports)
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check .
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check .
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest -p no:warnings   # add --cov=backend --cov-fail-under=80

# Frontend gates
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
```

**Rebuild a container after code changes** (compose won't pick up code without `--build`):
`docker compose -f docker/docker-compose.yml up -d --build backend` (and/or `frontend`).
The backend command runs `alembic upgrade head` then uvicorn (migrate-then-serve).

## 5. ⚠️ KNOWN ISSUES / GOTCHAS (read these)

1. **Port 5173 is taken by the Docker `frontend` container** → `preview_start`/`npm run dev` fails
   with "Port 5173 is in use by com.docker.backend.exe". **Fix:** either stop the compose frontend
   (`docker compose -f docker/docker-compose.yml stop frontend`) then run the Vite dev server, **or**
   just view the app at http://localhost:5173 (the container already serves it). For the preview
   tool, set `"autoPort": true` in `.claude/launch.json` and remove any hardcoded `--port`, or free
   5173 first. Iterating on frontend design is easiest via `cd frontend && npm run dev` **after
   stopping the compose frontend** (Vite proxies `/api` → :8000, backend stays up).
2. **balldontlie free tier = 5 req/min, hard cap.** The limiter must be **burst-free**: see
   `etl/client/rate_limiter.py` → `make_provider_limiter()` (capacity=1, ~4/min). A token bucket with
   capacity==rate bursts to ~2× and trips 429s.
3. **Postgres bind-param cap (32,767).** Bulk upsert is **chunked** (`etl/core/upsert.py`,
   `max_params=30000`). Don't remove the chunking — a season of team_stats (~5k rows) exceeds it.
4. **Scheduled games:** balldontlie returns future games with `status` = the **ISO tip-off time**
   (not "Final") and **scores = 0** (not null). "Unplayed" is detected by `status != 'final'`
   (see `predict_upcoming.py`), and "completed" by `status == 'Final'` + scores present.
5. **Players are ALL-TIME, not current rosters** (free tier limitation). We keep only players with a
   team and non-empty names (~5,804). The Players page is framed as a searchable historical index;
   team-detail "roster" shows a team's all-time players.
6. **Model artifacts in the container:** `ml/` is **volume-mounted** into the backend container
   (`docker-compose.yml`) so `/model/registry` and live `/model/predict` use host-trained models.
   In prod they'd ship in the image.
7. **Cross-season Elo:** the model's Elo feature **carries across seasons** (regressed toward mean).
   This is what makes 2026-27 predictions team-specific instead of a uniform ~64%. `features_for`
   returns carried Elo even on a new season's first game; `predict_upcoming`/`backtest` build state
   from **all** completed history. Keep training/inference feature computation consistent.
8. **Data was loaded via ad-hoc scripts** in the session scratchpad (temp, likely gone). Reproduce
   with the commands in §6. Data itself persists in the `pgdata` Docker volume.
9. **Redis cache:** after any manual DB change, `docker compose ... exec -T redis redis-cli FLUSHALL`
   so the API serves fresh data (GETs on standings/teams/predictions are cached 5 min).
10. **Browser screenshot tool is flaky** (occasional `UnknownVizError` / "pane not displayed") —
    retry, or use `read_page` for DOM verification.

## 6. Reproducing the data & model (real commands)

Requires `BALLDONTLIE_API_KEY` set in `.env` (already set locally). `.env` `DATABASE_URL` points at
`localhost:5432` (the container's mapped port), so host `uv run` scripts write to the container DB.

```bash
# Load a season's games + derive (repeat per season; slow at ~4 req/min, ~4 min/season)
#   run inside a small asyncio script that calls sync_games.run(client, session, seasons=[YEAR]),
#   then derive_team_stats.run(session), derive_standings.run(session).
# Sync players (all-time; slow): etl.jobs.sync_players.run(client, session)

# Train (resets registry first for a clean set of versions):
rm -f ml/models/*.pkl; echo '{"active": null, "versions": []}' > ml/registry.json
ML_PROMOTE=1 PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run python -m ml.pipeline.run_training

# Backtest historical + predict upcoming (needs active model):
#   backtest_predictions.run(session, predictor, seasons=[2023,2024,2025])   # settled
#   predict_upcoming.run(session, predictor, seasons=[2026])                 # unsettled

# Cleaned-up junk players (already done, but if re-synced):
#   DELETE FROM players WHERE first_name='' AND last_name='';  DELETE FROM players WHERE team_id IS NULL;

# Nightly one-shot (the real entrypoint): python -m etl.pipeline   (ETL_SEASONS env, default = current season)
```

Frontend `DEFAULT_SEASON`/`AVAILABLE_SEASONS`/`UPCOMING_SEASON` live in
`frontend/src/lib/constants.ts` (currently 2024 default; seasons 2025/2024/2023; upcoming 2026).

## 7. ML details

- **Features (12)** in `ml/pipeline/features.py`: rolling form win% & pt-diff (home/away), rest days,
  season net rating, head-to-head, and **Elo** (`home_elo`, `away_elo`, `elo_win_prob`; K=20,
  home-court +100, season carry 0.75). All from free `games` data. **Leak-free**: features computed
  before observing each game.
- **Training** (`train.py`, `run_training.py`): trains **logistic_regression** and
  **gradient_boosting** (`HistGradientBoostingClassifier`), time-based 80/20 split, evaluates
  accuracy / log loss / Brier, must beat majority-class baseline, registers each winner, promotes the
  best (accuracy, tie-broken by log loss). Registry entries include `algorithm`.
- **Inference:** API loads the active model at startup + a manual `POST /model/predict` reload;
  `GET /model/registry` is public. `POST /model/predict` needs an `X-API-Key` (mint with
  `python -m backend.scripts.mint_api_key --name "..."`).
- Retraining cadence/drift documented in `docs/ml_lifecycle.md`.

## 8. API surface (`/api/v1`)

`GET teams`, `teams/{id}`, `players`, `players/{id}`, `games`, `games/{id}`, `standings`,
`predictions` (filters: `game_id`, `model_version`, **`settled`** true/false, pagination),
`model/registry`; `POST model/predict` (X-API-Key), `model/reload`; `health`, `ready`. Envelope:
`{data, meta}` for lists, `{data}` for items, `{error:{code,message}}` for errors.

## 9. Frontend design system ("not AI-made" — keep this direction)

Editorial **sports-almanac** aesthetic. The user explicitly wanted it to **not look AI-generated** and
to feel **human/inviting** — honor that.

- **Type:** headings/wordmark in **Fraunces** (serif, via Google Fonts in `index.html`); body **Inter**.
- **Color tokens:** warm dark theme in `src/index.css` (`--color-*`); `.eyebrow` (uppercase, letter-
  spaced small labels), `.tabular`, `.animate-rise`. Tailwind maps tokens as `bg`,`surface`,`fg`,
  `accent`,`win`,`loss`, etc.
- **Real team colors:** `src/lib/teamColors.ts` (`teamColor(abbr)`), used on cards, standings marks,
  team-detail headers, and the 2026-27 win-probability bars.
- **Components:** `components/ui.tsx` (`PageHeader{eyebrow,title,subtitle,right}`, `SectionTitle`,
  `Card`, `Stat`, `TeamMark`, `EmptyState`), `DataTable`, `QueryState` (skeletons + friendly error).
- **Layout:** `Layout.tsx` = "Hardwood" masthead + underline tab nav + footer. **No emoji, no
  "Good afternoon 👋" greeting** (those were removed as AI tells).
- **Pages** (`src/pages`): Dashboard (season selector, stat tiles, **2026-27 Season Openers with model
  picks**, team-colored standings, recent results), Teams (color cards → detail), **TeamDetail**
  (`/teams/:id`: team-tinted header, record/rank/home-road, recent games, roster), Players (searchable
  all-time index), ModelLab (**LR vs GB comparison + calibration reliability curve** via
  `/model/registry` + settled predictions), PredictionTracker (cumulative accuracy chart + recent
  settled table; uses `settled=true`).
- **Data layer:** typed hooks in `src/hooks` (`useTeams`,`useTeam`,`usePlayers`,`useGames`,
  `useStandings`,`usePredictions`+`useAllPredictions({settled})`,`useModelRegistry`). **No ad-hoc
  fetch in components.** Loading/error states everywhere; dark theme; accessible landmarks.
- Frontend tests use `MemoryRouter` (pages use `<Link>`).

## 10. Deployment (Phase 5)

`docker compose up` works clean-clone (migrate-then-serve). CI (`.github/workflows/ci.yml`): PR runs
frontend + backend + migrations(Postgres) + docker-build; merge-to-main pushes images to **GHCR** and
a **manual-approval `production` environment** job triggers a host deploy via `RENDER_DEPLOY_HOOK`.
Free hosting plan (Neon / Upstash / Render / Cloudflare Pages / GitHub Actions) in
`docs/deployment.md`. **Not yet deployed to the cloud** — only run locally.

## 11. Suggested next steps (nothing is blocking)

- **Immediate:** resolve the 5173 dev-server conflict if you want HMR (see §5.1).
- **Polish:** the Prediction Tracker "recent" table maps matchups from the latest completed season
  only; a dedicated **"Upcoming 2026-27 picks" page/table** (join `settled=false` predictions ↔ 2026
  games ↔ teams) would showcase forward predictions beyond the Dashboard card.
- **Model:** feature importances / SHAP in Model Lab; per-season accuracy breakdown; carry team Elo in
  a table.
- **Deploy:** actually provision the free stack and wire `RENDER_DEPLOY_HOOK` to go live (great for the
  resume — a working URL).
- **Optional Phase 6:** React Native/Expo mobile app (stretch; marginal resume gain over the web app).
- **Data quality:** the "current roster" problem is a free-tier limitation; if a paid tier or an
  `nba_api` backfill is ever added, populate `player_stats` and current rosters.

## 12. Conventions to keep

- Business logic in `services`/jobs; routes stay thin. Types everywhere; `mypy --strict` clean.
- All datetimes UTC. No hardcoded secrets — env via Pydantic `BaseSettings` (`.env`, `.env.example`).
- Every new ETL/ML job and API change ships with tests. Migrations are the only schema path (tested
  downgrades). Keep files reasonably small.
- After editing container-served code, **rebuild the container**; after DB edits, **flush Redis**.
