"""Portable runtime-state paths with backward-compatible local defaults."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
FOREX_DATASET_RELATIVE_ROOT = Path("data") / "forex"


def configured_project_path(environment_name: str, default_relative: str) -> Path:
    environment_value = os.environ.get(environment_name)
    configured = Path(environment_value if environment_value else default_relative)
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def forex_dataset_root(project_root: Path | str | None = None) -> Path:
    """Return the canonical runtime root for production Forex datasets."""
    root = PROJECT_ROOT if project_root is None else Path(project_root)
    return root / FOREX_DATASET_RELATIVE_ROOT


def forex_dataset_path(
    symbol: str,
    timeframe: str,
    *,
    project_root: Path | str | None = None,
) -> Path:
    """Return one canonical production rolling-dataset path."""
    return forex_dataset_root(project_root) / f"{symbol}_{timeframe}.csv"
