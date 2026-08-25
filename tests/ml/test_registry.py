"""Tests for the model registry."""

import pathlib

from ml.pipeline.registry import active_entry, load_registry, register_model, set_active


def test_register_versions_and_activate(tmp_path: pathlib.Path) -> None:
    registry_path = tmp_path / "registry.json"
    models_dir = tmp_path / "models"

    entry = register_model(
        {"fake": "model"},
        metrics={"accuracy": 0.62, "log_loss": 0.60},
        feature_names=["a", "b"],
        training_window={"seasons": [2023]},
        date_str="20240101",
        git_commit="abc123",
        registry_path=registry_path,
        models_dir=models_dir,
    )
    assert entry["version"] == 1
    assert (models_dir / entry["filename"]).exists()

    registry = load_registry(registry_path)
    assert registry["active"] is None  # registering does not auto-activate
    assert registry["versions"][0]["metrics"]["accuracy"] == 0.62

    set_active(1, registry_path)
    assert active_entry(registry_path) is not None
    assert active_entry(registry_path)["version"] == 1  # type: ignore[index]

    second = register_model(
        {"fake": "model2"},
        metrics={"accuracy": 0.64, "log_loss": 0.58},
        feature_names=["a", "b"],
        training_window={"seasons": [2023]},
        date_str="20240108",
        git_commit="def456",
        registry_path=registry_path,
        models_dir=models_dir,
    )
    assert second["version"] == 2
    # Active pointer unchanged until an explicit promotion.
    assert active_entry(registry_path)["version"] == 1  # type: ignore[index]
