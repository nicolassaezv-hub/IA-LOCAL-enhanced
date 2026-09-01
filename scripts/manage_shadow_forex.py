#!/usr/bin/env python3
"""Explicit management CLI for the observational Forex shadow runtime."""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forex.prediction.shadow_runtime import ShadowForexRuntime, ShadowRuntimeConfig
from infra.db.database import PersistenceConflictError, get_database


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage ASTRA's non-trading Forex shadow runtime"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for command in ("train", "predict", "metrics"):
        subparser = commands.add_parser(command)
        subparser.add_argument("symbol", choices=("EURUSD", "USDJPY"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        database = get_database()
        runtime = ShadowForexRuntime(
            database,
            project_root=PROJECT_ROOT,
            config=ShadowRuntimeConfig.from_environment(),
        )
        with contextlib.redirect_stdout(sys.stderr):
            if args.command == "status":
                result = runtime.status()
            elif args.command == "train":
                result = runtime.train(args.symbol)
            elif args.command == "predict":
                result = runtime.run_shadow_prediction(args.symbol)
            else:
                result = runtime.metrics(args.symbol)
    except (
        FileNotFoundError,
        PersistenceConflictError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "result": result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
