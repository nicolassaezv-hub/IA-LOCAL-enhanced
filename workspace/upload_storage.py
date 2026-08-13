"""Safe, dependency-free storage for FastAPI-compatible upload objects."""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from pathlib import Path

from workspace.path_safety import resolve_user_path, validate_upload_filename

_CHUNK_SIZE = 1024 * 1024


def _safe_storage_parts(filename: str | None) -> tuple[str, str]:
    original = validate_upload_filename(filename)
    source = Path(original)
    suffix = re.sub(r"[^A-Za-z0-9.]", "", source.suffix)[:20]
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", source.stem).strip("._-")
    return (stem[:80] or "upload", suffix)


async def store_upload(upload: object, upload_root: str | os.PathLike[str]) -> tuple[Path, str, int]:
    """Stream an upload to a unique file and remove partial data after failure."""
    root = Path(upload_root).resolve(strict=True)
    original = validate_upload_filename(getattr(upload, "filename", None))
    _, suffix = _safe_storage_parts(original)
    temp_path: Path | None = None
    size = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".",
            suffix=".part",
            dir=root,
            delete=False,
        ) as destination:
            temp_path = Path(destination.name)
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                destination.write(chunk)
                size += len(chunk)

        final_path = resolve_user_path(root, f"{uuid.uuid4().hex}{suffix}")
        while final_path.exists():
            final_path = resolve_user_path(root, f"{uuid.uuid4().hex}{suffix}")
        os.replace(temp_path, final_path)
        return final_path, original, size
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
