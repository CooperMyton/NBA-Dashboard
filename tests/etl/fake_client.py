"""In-memory stand-in for BalldontlieClient, used to drive job tests without HTTP."""

from collections.abc import AsyncIterator, Sequence
from typing import Any


class FakeClient:
    def __init__(
        self,
        *,
        teams: list[dict[str, Any]] | None = None,
        players: list[dict[str, Any]] | None = None,
        games: list[dict[str, Any]] | None = None,
    ) -> None:
        self._teams = teams or []
        self._players = players or []
        self._games = games or []

    async def list_teams(self) -> list[dict[str, Any]]:
        return list(self._teams)

    async def list_players(self) -> list[dict[str, Any]]:
        return list(self._players)

    async def iter_games(
        self,
        *,
        seasons: Sequence[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        for game in self._games:
            yield game
