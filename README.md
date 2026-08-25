# Hardwood — NBA Analytics Platform

A full-stack sports-analytics platform that ingests NBA data nightly, engineers features, trains a
calibrated win-probability model, serves everything through a versioned async API, and presents it
in a React dashboard. **Designed and built to run at $0/month** on free tiers.

> **What it does:** predicts **P(home team wins)** for upcoming games (binary classification),
> grades those predictions against real results, and tracks model accuracy and calibration over time.

---

## Architecture

```
 balldontlie.io ──▶ ETL (rate-limited client, validate, idempotent upsert)
   (Free tier)          │
                        ▼
                  PostgreSQL 16 ──▶ feature engineering ──▶ ML pipeline
                        │                                    (train → evaluate → register)
                        │                                          │  active model
             derive standings/team stats                          ▼
                        │                                    model registry (versioned .pkl)
                        ▼                                          │
                  FastAPI (async)  ◀───────────── inference (active model only) ───┘
                    │      ▲
             cache  ▼      │ read-through
                  Redis ───┘
                    │
          React + Vite + TanStack Query  (Dashboard · Teams · Team Detail · Players · Model Lab · Prediction Tracker)
```

The ML pipeline never sits in the request path — it writes predictions offline; the API only ever
reads the currently active registered model. Nightly orchestration:
`sync → derive → settle predictions → predict upcoming → invalidate cache`.

## What this demonstrates

| Area | Highlights |
|---|---|
| **Data engineering** | Rate-limited provider client (token bucket + retry/backoff), Pydantic-validated payloads, idempotent `ON CONFLICT` upserts, post-load data-quality checks, nightly orchestration |
| **Backend** | Async FastAPI, SQLAlchemy 2.0 + asyncpg, Alembic (tested downgrades), consistent envelope/error contract, pagination/filtering, Redis read-through cache + sliding-window rate limiting, API-key auth |
| **ML** | Leak-free feature engineering, time-based split, majority-class baseline gate, accuracy/log-loss/Brier calibration, versioned model registry with an explicit active pointer, batch inference + settlement |
| **Frontend** | React + TypeScript, TanStack Query (typed hooks, loading/error states), dark theme, accessible semantics, Chart.js |
| **Platform** | Docker Compose (migrate-then-serve), multi-job GitHub Actions CI, GHCR image publishing, manual-approval-gated deploy, expand/contract migrations |
| **Rigor** | ~80 tests, `ruff` + `black` + `mypy --strict` (zero errors), 80% backend coverage gate, migration round-trip verified in CI |

## Tech stack ($0/month)

Python 3.12 (uv) · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 · Redis · scikit-learn ·
React + Vite + TypeScript · Tailwind · TanStack Query · Chart.js · Docker · GitHub Actions.

Hosting plan: **Neon** (Postgres) · **Upstash** (Redis) · **Render** (API) · **Cloudflare Pages**
(frontend) · **GitHub Actions** (CI + nightly ETL). See [`docs/deployment.md`](docs/deployment.md).

## Build status

| Phase | Status |
|---|---|
| 1 · Database + ETL | ✅ |
| 2 · API | ✅ |
| 3 · ML pipeline + inference | ✅ |
| 4 · Frontend | ✅ |
| 5 · Deployment (Docker + CI/CD) | ✅ *(runs locally; cloud hosting not yet provisioned)* |
| 6 · Mobile | stretch |

## API surface (`/api/v1`)

`GET /teams` · `/teams/{id}` · `/players` · `/players/{id}` · `/games` · `/standings` ·
`/predictions` · `POST /model/predict` (API-key) · `/health` · `/ready` · OpenAPI at `/docs`.

## Quickstart

**Full stack in containers** (needs Docker):

```bash
cp .env.example .env          # add your free BALLDONTLIE_API_KEY
docker compose -f docker/docker-compose.yml up --build
# frontend → http://localhost:5173   ·   API → http://localhost:8000/docs
```

**Backend only (local dev):**

```bash
cp .env.example .env
uv sync
docker compose -f docker/docker-compose.yml up -d db redis
uv run alembic -c backend/alembic.ini upgrade head
uv run uvicorn backend.main:app --reload
```

**Populate data & train a model:**

```bash
uv run python -m etl.pipeline            # ingest + derive (needs BALLDONTLIE_API_KEY)
uv run python -m ml.pipeline.run_training  # train; ML_PROMOTE=1 to activate a winner
uv run python -m backend.scripts.mint_api_key --name "me"  # mint a key for /model/predict
```

**Frontend dev server:**

```bash
cd frontend && npm install && npm run dev   # proxies /api → :8000
```

## Repository layout

```text
backend/   FastAPI app (api/v1 routers, services, models, schemas, core), Alembic, scripts
etl/       provider client, sync/derive/settle/predict jobs, pipeline orchestration
ml/        pipeline (collect→features→train→evaluate→register), inference, registry
frontend/  React + Vite app (6 pages, typed API client, query hooks)
docs/      decisions · data_source · ml_lifecycle · deployment
docker/    compose + Dockerfiles (backend, frontend) + nginx
tests/     backend / etl / ml suites (~80 tests)
```

## Quality gates

```bash
uv run ruff check . && uv run black --check . && uv run mypy backend etl ml
uv run pytest --cov=backend --cov-fail-under=80
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
```

Design decisions and rationale live in [`docs/decisions.md`](docs/decisions.md).
