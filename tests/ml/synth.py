"""Deterministic synthetic season generator for ML tests.

Each team has a fixed latent strength; the home team wins when strength + home advantage + noise
favors it. This gives the model a learnable signal so it can beat the majority-class baseline.
"""

from datetime import date, timedelta

import numpy as np

from backend.app.models.game import Game
from backend.app.models.team import Team
from ml.pipeline.features import GameRecord


def synth_game_records(seed: int = 0, n_teams: int = 12, rounds: int = 24) -> list[GameRecord]:
    rng = np.random.default_rng(seed)
    strengths = {t: float(rng.normal(0, 1.2)) for t in range(1, n_teams + 1)}
    records: list[GameRecord] = []
    gid = 1
    day = 0
    for _ in range(rounds):
        teams = list(strengths)
        rng.shuffle(teams)
        for i in range(0, n_teams, 2):
            home, away = teams[i], teams[i + 1]
            day += 1
            pt = strengths[home] + 0.35 - strengths[away] + float(rng.normal(0, 0.5))
            margin = int(round(pt * 6))
            home_score, visitor_score = 105 + margin, 105 - margin
            if home_score == visitor_score:
                home_score += 1
            records.append(
                GameRecord(
                    game_id=gid,
                    season=2023,
                    game_date=date(2024, 1, 1) + timedelta(days=day),
                    home_team_id=home,
                    visitor_team_id=away,
                    home_score=home_score,
                    visitor_score=visitor_score,
                )
            )
            gid += 1
    return records


async def seed_synthetic_db(session, records: list[GameRecord]) -> None:  # type: ignore[no-untyped-def]
    team_ids = sorted({r.home_team_id for r in records} | {r.visitor_team_id for r in records})
    teams = {
        tid: Team(
            external_id=tid,
            abbreviation=f"T{tid:02d}",
            name=f"Team {tid}",
            full_name=f"Team {tid}",
            city="City",
            conference="East" if tid % 2 else "West",
            division="D",
        )
        for tid in team_ids
    }
    session.add_all(list(teams.values()))
    await session.flush()

    for r in records:
        session.add(
            Game(
                external_id=r.game_id,
                season=r.season,
                game_date=r.game_date,
                start_time=None,
                status="Final",
                postseason=False,
                period=4,
                home_team_id=teams[r.home_team_id].id,
                visitor_team_id=teams[r.visitor_team_id].id,
                home_team_score=r.home_score,
                visitor_team_score=r.visitor_score,
            )
        )
    await session.commit()
