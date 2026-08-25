"""Model registry: versioned artifacts + registry.json with an explicit ``active`` pointer.

Registration only happens for a model that beat baseline; promotion (flipping ``active``) is a
separate, explicit step — training never auto-activates (docs/ml_lifecycle.md).
"""

import json
from pathlib import Path
from typing import Any, cast

import joblib

REGISTRY_PATH = Path("ml/registry.json")
MODELS_DIR = Path("ml/models")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if path.exists():
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return {"active": None, "versions": []}


def save_registry(registry: dict[str, Any], path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def register_model(
    model: Any,
    *,
    metrics: dict[str, float],
    feature_names: list[str],
    training_window: dict[str, Any],
    date_str: str,
    git_commit: str,
    algorithm: str = "unknown",
    registry_path: Path = REGISTRY_PATH,
    models_dir: Path = MODELS_DIR,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    version = len(registry["versions"]) + 1
    filename = f"model_v{version}_{date_str}.pkl"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, models_dir / filename)

    entry = {
        "version": version,
        "filename": filename,
        "date": date_str,
        "algorithm": algorithm,
        "metrics": metrics,
        "features": feature_names,
        "training_window": training_window,
        "git_commit": git_commit,
    }
    registry["versions"].append(entry)
    save_registry(registry, registry_path)
    return entry


def set_active(version: int, path: Path = REGISTRY_PATH) -> None:
    registry = load_registry(path)
    registry["active"] = version
    save_registry(registry, path)


def active_entry(path: Path = REGISTRY_PATH) -> dict[str, Any] | None:
    registry = load_registry(path)
    active = registry.get("active")
    if active is None:
        return None
    for entry in registry["versions"]:
        if entry["version"] == active:
            return cast(dict[str, Any], entry)
    return None
