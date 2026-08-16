"""Safely add non-secret runtime defaults to an existing systemd env file."""
from __future__ import annotations

import argparse
from pathlib import Path


def ensure_runtime_cache_defaults(environment_file: Path, cache_root: Path) -> list[str]:
    """Append missing cache keys without changing any existing assignment."""
    content = environment_file.read_text(encoding="utf-8")
    existing = {
        line.strip().removeprefix("export ").split("=", 1)[0]
        for line in content.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    defaults = {
        "XDG_CACHE_HOME": str(cache_root),
        "MPLCONFIGDIR": str(cache_root / "matplotlib"),
    }
    missing = [key for key in defaults if key not in existing]
    if missing:
        separator = "" if not content or content.endswith("\n") else "\n"
        additions = "".join(f"{key}={defaults[key]}\n" for key in missing)
        with environment_file.open("a", encoding="utf-8") as handle:
            handle.write(separator + additions)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    args = parser.parse_args()
    ensure_runtime_cache_defaults(args.environment_file, args.cache_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
