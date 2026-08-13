"""Portable runtime-state paths with backward-compatible local defaults."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def configured_project_path(environment_name: str, default_relative: str) -> Path:
    environment_value = os.environ.get(environment_name)
    configured = Path(environment_value if environment_value else default_relative)
    return configured if configured.is_absolute() else PROJECT_ROOT / configured
