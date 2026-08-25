"""SQLAlchemy ORM models.

Every model is imported here so ``Base.metadata`` (and Alembic autogenerate) sees all tables.
"""

from backend.app.models.base import Base
from backend.app.models.game import Game
from backend.app.models.injury import Injury
from backend.app.models.model_prediction import ModelPrediction
from backend.app.models.player import Player
from backend.app.models.player_stat import PlayerStat
from backend.app.models.standing import Standing
from backend.app.models.team import Team
from backend.app.models.team_stat import TeamStat
from backend.app.models.user import User

__all__ = [
    "Base",
    "Game",
    "Injury",
    "ModelPrediction",
    "Player",
    "PlayerStat",
    "Standing",
    "Team",
    "TeamStat",
    "User",
]
