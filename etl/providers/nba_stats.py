"""nba_api access — the only module that imports it.

balldontlie's free tier has no season dimension for players, so rosters and player stats come from
stats.nba.com instead. The NBA blocks datacenter IP ranges, so anything calling this module runs
from a developer machine, never from CI or the deployed host.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from nba_api.stats.endpoints import commonteamroster, leaguedashplayerstats
from nba_api.stats.static import teams as nba_teams

from backend.app.core.logging import get_logger

logger = get_logger("etl.nba_stats")

# stats.nba.com is unofficial and rate-sensitive; pace requests rather than risk a soft ban.
_REQUEST_DELAY_S = 0.7
_TIMEOUT_S = 60


@dataclass(frozen=True)
class RosterEntry:
    nba_player_id: int
    name: str
    team_abbr: str
    position: str | None
    jersey: str | None
    age: float
    experience: int


@dataclass(frozen=True)
class StatLine:
    nba_player_id: int
    name: str
    team_abbr: str
    season: int
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    fg3_pct: float
    fg3a: float
    ts_pct: float
    usage_pct: float


def season_label(season: int) -> str:
    """2026 -> '2026-27', matching the NBA's season string format."""
    return f"{season}-{str(season + 1)[-2:]}"


def parse_experience(value: str) -> int:
    """'R' means rookie; otherwise a year count. Anything unrecognised counts as zero."""
    text = str(value).strip().upper()
    if text == "R":
        return 0
    try:
        return int(text)
    except ValueError:
        return 0


def _num(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    return 0.0 if value is None else float(value)


def rows_to_stat_lines(
    base: list[dict[str, Any]], advanced: list[dict[str, Any]], *, season: int
) -> list[StatLine]:
    """Join the Base and Advanced dashboards on player id.

    A player present in Base but absent from Advanced is skipped rather than defaulted — a missing
    Advanced row means the two dashboards disagree, and inventing TS%/usage would corrupt the
    signals downstream.
    """
    adv_by_id = {int(row["PLAYER_ID"]): row for row in advanced}
    lines: list[StatLine] = []
    for row in base:
        pid = int(row["PLAYER_ID"])
        adv = adv_by_id.get(pid)
        if adv is None:
            continue
        lines.append(
            StatLine(
                nba_player_id=pid,
                name=str(row["PLAYER_NAME"]),
                team_abbr=str(row["TEAM_ABBREVIATION"]),
                season=season,
                games_played=int(row.get("GP") or 0),
                minutes=_num(row, "MIN"),
                points=_num(row, "PTS"),
                rebounds=_num(row, "REB"),
                assists=_num(row, "AST"),
                fg3_pct=_num(row, "FG3_PCT"),
                fg3a=_num(row, "FG3A"),
                ts_pct=_num(adv, "TS_PCT"),
                usage_pct=_num(adv, "USG_PCT"),
            )
        )
    return lines


def fetch_season_stats(season: int) -> list[StatLine]:
    """One Base and one Advanced dashboard call for the season."""
    label = season_label(season)
    base = leaguedashplayerstats.LeagueDashPlayerStats(
        season=label, per_mode_detailed="PerGame", timeout=_TIMEOUT_S
    ).get_normalized_dict()["LeagueDashPlayerStats"]
    time.sleep(_REQUEST_DELAY_S)
    advanced = leaguedashplayerstats.LeagueDashPlayerStats(
        season=label,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced",
        timeout=_TIMEOUT_S,
    ).get_normalized_dict()["LeagueDashPlayerStats"]
    time.sleep(_REQUEST_DELAY_S)
    lines = rows_to_stat_lines(base, advanced, season=season)
    logger.info("nba_stats.season_fetched", season=season, players=len(lines))
    return lines


def team_nba_ids(abbreviations: Iterable[str]) -> dict[str, int]:
    """Map our team abbreviations to nba_api's own (stable, unrelated) team ids.

    nba_api's static team data has no season dimension, so this is a plain lookup rather than a
    network call. Abbreviations with no match in nba_api's data are silently omitted.
    """
    nba_by_abbr = {t["abbreviation"]: int(t["id"]) for t in nba_teams.get_teams()}
    return {abbr: nba_by_abbr[abbr] for abbr in abbreviations if abbr in nba_by_abbr}


def fetch_rosters(season: int, team_nba_ids: dict[str, int]) -> list[RosterEntry]:
    """One roster call per team. ``team_nba_ids`` maps team abbreviation to NBA team id."""
    label = season_label(season)
    entries: list[RosterEntry] = []
    for abbr, nba_team_id in sorted(team_nba_ids.items()):
        rows = commonteamroster.CommonTeamRoster(
            team_id=nba_team_id, season=label, timeout=_TIMEOUT_S
        ).get_normalized_dict()["CommonTeamRoster"]
        for row in rows:
            entries.append(
                RosterEntry(
                    nba_player_id=int(row["PLAYER_ID"]),
                    name=str(row["PLAYER"]),
                    team_abbr=abbr,
                    position=(str(row["POSITION"]) or None) if row.get("POSITION") else None,
                    jersey=(str(row["NUM"]) or None) if row.get("NUM") else None,
                    age=float(row.get("AGE") or 0.0),
                    experience=parse_experience(str(row.get("EXP", ""))),
                )
            )
        time.sleep(_REQUEST_DELAY_S)
    logger.info("nba_stats.rosters_fetched", season=season, players=len(entries))
    return entries
