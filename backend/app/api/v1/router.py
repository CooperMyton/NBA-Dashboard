"""Aggregate router for API v1."""

from fastapi import APIRouter

from backend.app.api.v1 import games, health, model, players, predictions, standings, teams

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(teams.router)
api_router.include_router(players.router)
api_router.include_router(games.router)
api_router.include_router(standings.router)
api_router.include_router(predictions.router)
api_router.include_router(model.router)
