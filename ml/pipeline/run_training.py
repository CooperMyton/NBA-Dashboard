"""Training orchestration: collect → features → time-split → train → evaluate → (register).

Registers only if the candidate beats baseline; promotes to ``active`` only when ``promote=True``.

Run as: ``python -m ml.pipeline.run_training``  (set ``ML_PROMOTE=1`` to activate a winner).
"""

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from ml.pipeline.baseline import baseline_probabilities, majority_class_probability
from ml.pipeline.collect import collect_games
from ml.pipeline.evaluate import beats_baseline, evaluate
from ml.pipeline.features import FEATURE_NAMES, build_training_data
from ml.pipeline.registry import MODELS_DIR, REGISTRY_PATH, register_model, set_active
from ml.pipeline.train import ALGORITHMS, predict_proba, train_by_name

logger = get_logger("ml.train")

MIN_GAMES = 10


async def run_training(
    session: AsyncSession,
    *,
    date_str: str,
    git_commit: str = "unknown",
    seasons: list[int] | None = None,
    promote: bool = False,
    eval_fraction: float = 0.2,
    registry_path: Path = REGISTRY_PATH,
    models_dir: Path = MODELS_DIR,
) -> dict[str, Any]:
    games = await collect_games(session, seasons=seasons)
    features, labels, _ = build_training_data(games)

    if len(features) < MIN_GAMES:
        logger.warning("ml.train.insufficient_data", games=len(features))
        return {"beats_baseline": False, "insufficient_data": True, "games": len(features)}

    split = int(len(features) * (1 - eval_fraction))
    x_train, y_train = features[:split], labels[:split]
    x_eval, y_eval = features[split:], labels[split:]

    base_prob = majority_class_probability(y_train)
    base_metrics = evaluate(y_eval, baseline_probabilities(base_prob, len(y_eval)))

    # Train every candidate algorithm, evaluate, and register those that beat baseline.
    candidates: list[dict[str, Any]] = []
    registered: list[dict[str, Any]] = []
    for name in ALGORITHMS:
        model = train_by_name(name, x_train, y_train)
        metrics = evaluate(y_eval, predict_proba(model, x_eval))
        won = beats_baseline(metrics, base_metrics)
        candidates.append({"algorithm": name, "metrics": metrics, "beats_baseline": won})
        logger.info("ml.train.candidate", algorithm=name, won=won, **metrics)
        if won:
            entry = register_model(
                model,
                metrics=metrics,
                feature_names=FEATURE_NAMES,
                training_window={"seasons": seasons, "n_train": len(x_train)},
                date_str=date_str,
                git_commit=git_commit,
                algorithm=name,
                registry_path=registry_path,
                models_dir=models_dir,
            )
            registered.append(entry)

    # Promote the best registered model: highest accuracy, tie-broken by lower log loss.
    best = None
    if registered:
        best = min(
            registered,
            key=lambda e: (-e["metrics"]["accuracy"], e["metrics"]["log_loss"]),
        )
    active_version = None
    if best and promote:
        set_active(best["version"], registry_path)
        active_version = best["version"]

    return {
        "n_train": len(x_train),
        "n_eval": len(x_eval),
        "baseline": base_metrics,
        "candidates": candidates,
        "registered": registered,
        "best": best,
        "active_version": active_version,
        "beats_baseline": bool(registered),
    }


def _git_commit() -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - commit hash is best-effort metadata
        return "unknown"


async def _main() -> int:
    import os
    from datetime import UTC, datetime

    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal

    configure_logging()
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    promote = os.environ.get("ML_PROMOTE") == "1"

    async with SessionLocal() as session:
        result = await run_training(
            session, date_str=date_str, git_commit=_git_commit(), promote=promote
        )
    return 0 if result["beats_baseline"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
