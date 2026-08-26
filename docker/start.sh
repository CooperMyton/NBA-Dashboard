#!/bin/sh
# Container entrypoint: migrate, then serve.
#
# Migrations run as a pre-serve step so a fresh environment (or a new release with
# pending migrations) comes up with a ready schema — the expand/contract pattern in
# docs/deployment.md. `exec` replaces the shell so uvicorn receives SIGTERM directly
# and shuts down cleanly.
#
# PORT is provided by most PaaS hosts (Render, Cloud Run, Fly) and must be honoured or
# the platform's health check never passes. Falls back to 8000 for local use.
set -e

alembic -c backend/alembic.ini upgrade head
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
