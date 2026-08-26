# Deployment

> This file records the deployment plan (all free) and what is built vs. still to confirm.
> Overriding constraint: **$0/month.**

## Environments

- **`dev` (local):** `docker compose -f docker/docker-compose.yml up --build` from a clean clone
  brings up **db** (Postgres 16), **redis**, **backend** (migrates then serves on `:8000`), and
  **frontend** (nginx serving the built SPA on `:5173`, proxying `/api` → backend). The ETL runs
  on demand via the opt-in `etl` profile. Must work end-to-end (spec Definition of Done).
- **Cloud:** a **single** deployed environment (named `prod`) rather than separate staging + prod
  instances, to stay free. A GitHub Actions **manual-approval gate** still fronts the deploy so the
  promote-to-prod workflow is demonstrated. See [`decisions.md`](./decisions.md) D-013.

## Local stack (docker compose)

| Service | Image / build | Port | Notes |
|---|---|---|---|
| `db` | postgres:16 | 5432 | healthchecked; `pgdata` volume |
| `redis` | redis:7 | 6379 | cache + rate limiting |
| `backend` | `docker/Dockerfile.backend` | 8000 | `docker/start.sh`: `alembic upgrade head` then uvicorn |
| `frontend` | `docker/Dockerfile.frontend` | 5173→80 | nginx serves `dist/`, proxies `/api` → `backend:8000` |
| `etl` | `docker/Dockerfile.backend` (profile `etl`) | — | one-shot `python -m etl.pipeline` |

Because nginx proxies `/api` to the backend, the browser sees a **single origin** locally — no CORS
needed. The frontend is built with the default `VITE_API_BASE_URL=/api/v1`.

## Free hosting stack ($0/month)

| Component | Service | Free-tier notes |
|---|---|---|
| Postgres | **Neon** | 0.5 GB/project, scales to zero, permanent free, no card. |
| Redis | **Upstash** | Serverless free tier; re-verify command/day caps at build time. |
| Backend/API | **Render free** (primary), else Fly.io / Cloud Run / HF Spaces | 750 hrs/mo, no card, sleeps after 15 min (~30–60 s cold start) — acceptable for a portfolio. Deploy the `Dockerfile.backend` image; set the migrate-then-serve command. |
| Frontend | **Cloudflare Pages** (static `dist/`) | Build with `VITE_API_BASE_URL=https://<backend-host>/api/v1`; then set the backend's `CORS_ORIGINS` to the Pages URL. |
| Nightly ETL | **GitHub Actions scheduled workflow** | Free; runs ETL against Neon. No always-on cron container in the cloud. D-014. |
| CI/CD | **GitHub Actions** | Free tier. |

### Cloud origins & CORS

Locally, nginx makes frontend + API same-origin (no CORS). In the cloud the static frontend and the
backend are **different origins**, so:
1. Build the frontend with `VITE_API_BASE_URL` = the backend's public `/api/v1` URL.
2. Set the backend's `CORS_ORIGINS` env var to the frontend's URL (the app enables CORS for it).

## CI/CD flow (`.github/workflows/ci.yml`)

- **On PR:** `frontend` (eslint + tsc + vitest + build), `backend` (ruff + black + mypy + pytest,
  backend coverage gate ≥80%), `migrations` (upgrade→downgrade→upgrade + drift check on Postgres 16),
  `docker-build` (builds **both** images, no push — validates the Dockerfiles).
- **On merge to `main`:** all of the above, then:
  - `images` — build + push `…-backend` and `…-frontend` to **GHCR** (`ghcr.io/<owner>/<repo>-*`),
    tagged with the commit SHA + `latest`, authenticated via the built-in `GITHUB_TOKEN`.
  - `deploy` — gated by the **`production` GitHub Environment** (required-reviewer = manual approval,
    D-013). Triggers the host to pull the new image via `RENDER_DEPLOY_HOOK`; the backend container
    runs `alembic upgrade head` on boot (expand/contract), so migrations apply as a pre-serve step.

### Container start command

The image's `CMD` is `docker/start.sh`, which runs `alembic -c backend/alembic.ini upgrade head`
and then `exec`s uvicorn on `${PORT:-8000}`. Keeping this in the image means **no host-specific
start-command override is needed** — compose and any PaaS boot identically, and hosts that inject
`$PORT` (Render, Cloud Run, Fly) are honoured automatically. On Render, leave the *Docker Command*
field **empty**.

Shell scripts are pinned to LF via `.gitattributes`; a CRLF shebang makes Linux look for an
interpreter named `/bin/sh` and the container exits 127.

**To activate the deploy** once a host is provisioned: create a `production` environment in repo
Settings → Environments, add the required reviewer, and set `RENDER_DEPLOY_HOOK` (the host's deploy
hook URL) as an environment secret. No other change needed.

## Migrations

- Run automatically as a **pre-deploy step** in the pipeline — never manually against the cloud DB.
- **Expand/contract** pattern so the previous image stays compatible with the new schema for one
  release cycle.

## Rollback

- Previous image tag redeployable via one workflow dispatch. Because migrations are
  backward-compatible for one release, rollback never needs a compensating migration.

## Verification status

- **CI/CD workflow:** YAML validated; runs on GitHub (no local equivalent).
- **`docker compose` config:** validated with `docker compose config` (all 5 services parse).
- **Local `docker compose up` end-to-end:** verified. All five services run; the backend migrates
  then serves, and the frontend is served by nginx with `/api` proxied. Real data for seasons
  2023-24 through 2025-26 plus the 2026-27 schedule is loaded and served.
- **Model artifacts:** `ml/models/*.pkl` are tracked in git (the active logistic-regression model is
  ~2 KB) so the CI-built image is self-contained and the deployed API can serve `/model/predict`.
  Without them the API still starts — model load failure is caught at startup — but live inference
  would return an error.

## Open (confirm when provisioning the cloud env)

- Re-check Render free-tier terms/cold-start at provisioning time; fall back to Fly.io / Cloud Run /
  HF Spaces if changed.
- Upstash Redis exact free-tier caps vs. expected cache traffic.
- Create the `production` environment + `RENDER_DEPLOY_HOOK` secret to arm the deploy job.
