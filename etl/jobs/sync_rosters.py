"""Sync current rosters, player season stats and derived insights from nba_api.

Local-only: the NBA blocks datacenter IPs, so this never runs in CI or on the deployed host
(docs/superpowers/specs/2026-08-30-current-rosters-and-player-insights-design.md). Run it by hand
when rosters change.

Run as: ``python -m etl.jobs.sync_rosters``
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.models.team import Team
from etl.core.names import match_players
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from etl.providers.nba_stats import RosterEntry, StatLine, fetch_rosters, fetch_season_stats
from ml.pipeline.player_signals import SeasonLine, breakout_signal, regression_signal

logger = get_logger("etl.sync_rosters")

DEFAULT_ROSTER_SEASON = 2026
DEFAULT_STAT_SEASONS = [2022, 2023, 2024, 2025]

STAT_UPDATE_COLS = [
    "team_id",
    "games_played",
    "minutes",
    "points",
    "rebounds",
    "assists",
    "fg3_pct",
    "fg3a",
    "ts_pct",
    "usage_pct",
]
INSIGHT_UPDATE_COLS = ["score", "detail", "generated_at"]


def _split_name(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


async def run(
    session: AsyncSession,
    *,
    roster_season: int,
    stat_seasons: list[int],
    rosters: list[RosterEntry],
    stat_lines: list[StatLine],
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="sync_rosters")

    teams = (await session.execute(select(Team))).scalars().all()
    team_id_by_abbr = {team.abbreviation: team.id for team in teams}
    abbr_by_team_id = {team.id: team.abbreviation for team in teams}

    db_players = (await session.execute(select(Player))).scalars().all()

    # Players already keyed by a stable NBA id join directly and skip name matching entirely,
    # so a repeat sync never turns an earlier match (or insert) into a fresh ambiguous lookup.
    player_id_by_nba_id: dict[int, int] = {
        player.nba_player_id: player.id for player in db_players if player.nba_player_id is not None
    }
    matched: dict[int, int] = {}
    name_match_entries: list[RosterEntry] = []
    for entry in rosters:
        player_id = player_id_by_nba_id.get(entry.nba_player_id)
        if player_id is not None:
            matched[entry.nba_player_id] = player_id
        else:
            name_match_entries.append(entry)

    db_tuples = [
        (
            player.id,
            f"{player.first_name} {player.last_name}",
            abbr_by_team_id.get(player.team_id, "") if player.team_id is not None else "",
        )
        for player in db_players
        if player.nba_player_id is None
    ]
    nba_tuples = [
        (entry.nba_player_id, entry.name, entry.team_abbr) for entry in name_match_entries
    ]
    name_matched, unmatched = match_players(nba_tuples, db_tuples)
    matched.update(name_matched)

    # Insert the players no pass could pair, keyed by NBA id so later syncs join directly.
    entry_by_nba_id = {entry.nba_player_id: entry for entry in rosters}
    for nba_id in unmatched:
        entry = entry_by_nba_id[nba_id]
        first, last = _split_name(entry.name)
        player = Player(
            external_id=-nba_id,  # negative keeps it clear of balldontlie's id space
            first_name=first,
            last_name=last,
            position=entry.position,
            jersey_number=entry.jersey,
            team_id=team_id_by_abbr.get(entry.team_abbr),
            nba_player_id=nba_id,
            roster_season=roster_season,
        )
        session.add(player)
        await session.flush()
        matched[nba_id] = player.id
    if unmatched:
        logger.info("sync_rosters.inserted_unmatched", count=len(unmatched))

    try:
        # Anyone previously rostered for this season who is no longer on a roster is cleared
        # first, so a traded or waived player does not linger on a team page.
        await session.execute(
            update(Player).where(Player.roster_season == roster_season).values(roster_season=None)
        )
        for nba_id, player_id in matched.items():
            entry = entry_by_nba_id[nba_id]
            await session.execute(
                update(Player)
                .where(Player.id == player_id)
                .values(
                    nba_player_id=nba_id,
                    roster_season=roster_season,
                    team_id=team_id_by_abbr.get(entry.team_abbr),
                    position=entry.position,
                    jersey_number=entry.jersey,
                )
            )
        summary.rows_processed = len(matched)

        # Season stats, restricted to rostered players and to the requested seasons. A traded
        # player can have two rows for the same season (one per team); the table's unique
        # constraint is (player_id, season), so only the stint with more games played is kept —
        # it best represents the player's year, and keeping both would also fail the upsert and
        # let the signal functions compare two partial stints against each other.
        stat_rows_by_key: dict[tuple[int, int], dict[str, Any]] = {}
        for line in stat_lines:
            if line.season not in stat_seasons:
                continue
            stat_player_id = matched.get(line.nba_player_id)
            if stat_player_id is None:
                continue
            key = (stat_player_id, line.season)
            existing = stat_rows_by_key.get(key)
            if existing is not None and existing["games_played"] >= line.games_played:
                continue
            stat_rows_by_key[key] = {
                "player_id": stat_player_id,
                "season": line.season,
                "team_id": team_id_by_abbr.get(line.team_abbr),
                "games_played": line.games_played,
                "minutes": line.minutes,
                "points": line.points,
                "rebounds": line.rebounds,
                "assists": line.assists,
                "fg3_pct": line.fg3_pct,
                "fg3a": line.fg3a,
                "ts_pct": line.ts_pct,
                "usage_pct": line.usage_pct,
            }
        stat_rows = list(stat_rows_by_key.values())
        if stat_rows:
            await upsert(
                session,
                PlayerSeasonStat,
                stat_rows,
                conflict_cols=["player_id", "season"],
                update_cols=STAT_UPDATE_COLS,
            )

        # Recompute insights from scratch: a flag that no longer holds must disappear.
        insight_season = max(stat_seasons)
        await session.execute(delete(PlayerInsight).where(PlayerInsight.season == insight_season))

        lines_by_player: dict[int, list[SeasonLine]] = {}
        for row in stat_rows:
            lines_by_player.setdefault(int(row["player_id"]), []).append(
                SeasonLine(
                    season=int(row["season"]),
                    games_played=int(row["games_played"]),
                    minutes=float(row["minutes"]),
                    points=float(row["points"]),
                    rebounds=float(row["rebounds"]),
                    assists=float(row["assists"]),
                    fg3_pct=float(row["fg3_pct"]),
                    fg3a=float(row["fg3a"]),
                    ts_pct=float(row["ts_pct"]),
                    usage_pct=float(row["usage_pct"]),
                )
            )

        now = datetime.now(UTC)
        insight_rows: list[dict[str, Any]] = []
        for nba_id, player_id in matched.items():
            lines = lines_by_player.get(player_id, [])
            entry = entry_by_nba_id[nba_id]
            for insight in (
                regression_signal(lines),
                breakout_signal(lines, age=entry.age, experience=entry.experience),
            ):
                if insight is None:
                    continue
                insight_rows.append(
                    {
                        "player_id": player_id,
                        "season": insight_season,
                        "kind": insight.kind,
                        "score": insight.score,
                        "detail": insight.detail,
                        "generated_at": now,
                    }
                )
        if insight_rows:
            await upsert(
                session,
                PlayerInsight,
                insight_rows,
                conflict_cols=["player_id", "season", "kind"],
                update_cols=INSIGHT_UPDATE_COLS,
            )

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    summary.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "sync_rosters.done",
        rostered=len(matched),
        stats=len(stat_rows),
        insights=len(insight_rows),
    )
    return summary


async def main() -> None:
    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal

    configure_logging()
    async with SessionLocal() as session:
        teams = (await session.execute(select(Team))).scalars().all()
        # nba_api's team ids are stable and unrelated to ours; look them up from its static data.
        from nba_api.stats.static import teams as nba_teams

        nba_by_abbr = {t["abbreviation"]: int(t["id"]) for t in nba_teams.get_teams()}
        team_nba_ids = {
            team.abbreviation: nba_by_abbr[team.abbreviation]
            for team in teams
            if team.abbreviation in nba_by_abbr
        }

        rosters = fetch_rosters(DEFAULT_ROSTER_SEASON, team_nba_ids)
        stat_lines: list[StatLine] = []
        for season in DEFAULT_STAT_SEASONS:
            stat_lines.extend(fetch_season_stats(season))

        summary = await run(
            session,
            roster_season=DEFAULT_ROSTER_SEASON,
            stat_seasons=DEFAULT_STAT_SEASONS,
            rosters=rosters,
            stat_lines=stat_lines,
        )
    logger.info("etl.job.summary", **summary.as_dict())


if __name__ == "__main__":
    asyncio.run(main())
