"""Match players between providers by name.

``nba_api`` keys players by NBA's id; the database keys them by balldontlie's. There is no shared
identifier, so the first sync pairs them by name. Exact normalised full-name matching covers about
98.6% of an NBA season; the remainder are nickname-versus-legal-name cases ("Nic Claxton" against
Nicolas), which a second pass resolves using last name plus current team.
"""

import re
import unicodedata

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def normalize_name(value: str) -> str:
    """Lowercase, strip accents and punctuation, and drop generational suffixes."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    folded = folded.lower().replace(".", "").replace("'", "").replace("-", " ")
    folded = _SUFFIXES.sub("", folded)
    return " ".join(folded.split())


def _last_name(value: str) -> str:
    parts = normalize_name(value).split()
    return parts[-1] if parts else ""


def match_players(
    nba_names: list[tuple[int, str, str]],
    db_players: list[tuple[int, str, str]],
) -> tuple[dict[int, int], list[int]]:
    """Pair NBA players to database players.

    Each input tuple is ``(id, full_name, team_abbr)``. Returns the mapping from NBA id to database
    player id, plus the NBA ids that could not be paired. A database player is never assigned twice.
    """
    by_full: dict[str, list[int]] = {}
    by_last_team: dict[tuple[str, str], list[int]] = {}
    for db_id, name, team in db_players:
        by_full.setdefault(normalize_name(name), []).append(db_id)
        by_last_team.setdefault((_last_name(name), team.upper()), []).append(db_id)

    matched: dict[int, int] = {}
    taken: set[int] = set()
    unmatched: list[int] = []

    # Pass 1: exact normalised full name.
    deferred: list[tuple[int, str, str]] = []
    for nba_id, name, team in nba_names:
        candidates = [c for c in by_full.get(normalize_name(name), []) if c not in taken]
        if len(candidates) == 1:
            matched[nba_id] = candidates[0]
            taken.add(candidates[0])
        else:
            deferred.append((nba_id, name, team))

    # Pass 2: last name plus team. Ambiguous groups are left unmatched rather than guessed.
    for nba_id, name, team in deferred:
        key = (_last_name(name), team.upper())
        candidates = [c for c in by_last_team.get(key, []) if c not in taken]
        if len(candidates) == 1:
            matched[nba_id] = candidates[0]
            taken.add(candidates[0])
        else:
            unmatched.append(nba_id)

    return matched, unmatched
