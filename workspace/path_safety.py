"""Filesystem boundaries for paths supplied by Workspace/API clients."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable


class UnsafePathError(ValueError):
    """Raised when a client-controlled path escapes its allowed boundary."""


def _validate_relative_syntax(candidate: str | os.PathLike[str]) -> str:
    raw = os.fspath(candidate)
    if not raw or "\x00" in raw:
        raise UnsafePathError("path must be a non-empty relative path")

    # Check both flavours so Windows paths are rejected on Linux and vice versa.
    for pure_path in (PurePosixPath(raw), PureWindowsPath(raw)):
        if pure_path.is_absolute() or pure_path.drive or pure_path.root:
            raise UnsafePathError("absolute paths are not allowed")
        if ".." in pure_path.parts:
            raise UnsafePathError("parent traversal is not allowed")
    return raw


def resolve_user_path(
    root: str | os.PathLike[str],
    candidate: str | os.PathLike[str],
    *,
    must_exist: bool = False,
    require_file: bool = False,
) -> Path:
    """Resolve a relative client path and prove that it remains below ``root``."""
    raw = _validate_relative_syntax(candidate)
    root_path = Path(root).resolve(strict=True)
    resolved = (root_path / raw).resolve(strict=False)
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise UnsafePathError("path escapes the allowed root") from exc

    if must_exist and not resolved.exists():
        raise FileNotFoundError(resolved)
    if require_file and not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def resolve_user_path_in_roots(
    base_root: str | os.PathLike[str],
    candidate: str | os.PathLike[str],
    allowed_roots: Iterable[str | os.PathLike[str]],
    *,
    require_file: bool = False,
) -> Path:
    """Resolve from a stable base, then require membership in an allowed subtree."""
    resolved = resolve_user_path(
        base_root,
        candidate,
        must_exist=require_file,
        require_file=require_file,
    )
    for allowed_root in allowed_roots:
        allowed = Path(allowed_root).resolve(strict=True)
        try:
            resolved.relative_to(allowed)
            return resolved
        except ValueError:
            continue
    raise UnsafePathError("path is outside the allowed roots")


def validate_upload_filename(filename: str | None) -> str:
    """Return a safe display basename; upload names must never contain a path."""
    raw = _validate_relative_syntax(filename or "upload")
    if len(PurePosixPath(raw).parts) != 1 or len(PureWindowsPath(raw).parts) != 1:
        raise UnsafePathError("upload filename must not contain directories")
    return raw
