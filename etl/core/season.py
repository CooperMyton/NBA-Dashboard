"""NBA season helpers. Season is the start year (2024 ⇒ 2024–25); see docs/decisions.md D-010."""

from datetime import date


def current_nba_season(today: date) -> int:
    """Return the current season's start year.

    The season starting in October of year Y is season Y; before October we are still in
    (or just after) season Y-1.
    """
    return today.year if today.month >= 10 else today.year - 1
