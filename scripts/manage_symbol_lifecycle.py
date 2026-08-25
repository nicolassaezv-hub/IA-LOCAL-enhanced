#!/usr/bin/env python3
"""Explicit CLI for ASTRA candidate → qualified → active transitions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forex.data.symbol_lifecycle import (
    activate_qualified_symbol,
    disable_symbol,
    qualify_candidate,
    register_candidate,
)
from infra.db.database import PersistenceConflictError, get_database


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage ASTRA's fail-closed symbol lifecycle"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "register-candidate",
        "qualify-symbol",
        "activate-symbol",
        "disable-symbol",
        "show-symbol",
    ):
        subparser = commands.add_parser(command)
        subparser.add_argument("symbol")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        database = get_database()
        if args.command == "register-candidate":
            result = register_candidate(database, args.symbol)
        elif args.command == "qualify-symbol":
            result = qualify_candidate(
                database,
                args.symbol,
                project_root=PROJECT_ROOT,
            )
            if result.get("result") != "PASS":
                print(json.dumps(result, indent=2, default=str))
                return 2
        elif args.command == "activate-symbol":
            result = activate_qualified_symbol(
                database,
                args.symbol,
                project_root=PROJECT_ROOT,
            )
        elif args.command == "disable-symbol":
            result = disable_symbol(database, args.symbol)
        else:
            result = database.get_symbol(args.symbol.upper())
            if result is None:
                raise PersistenceConflictError("Symbol is not registered")
    except (PersistenceConflictError, ValueError, FileNotFoundError) as exc:
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
