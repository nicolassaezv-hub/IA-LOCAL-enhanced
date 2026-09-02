#!/usr/bin/env python3
"""Run one direct-MT5 Forex shadow replay in disposable local state."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forex.replay.historical_replay import (
    HistoricalReplay,
    HistoricalReplayConfig,
    bound_sources_for_replay,
    capture_mt5_sources,
    snapshot_paths,
    verify_snapshots,
)
from infra.db.database import configured_sqlite_path
from runtime_paths import forex_dataset_path, forex_model_root, symbol_qualification_root


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="EURUSD,USDJPY")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    return parser.parse_args(argv)


def _symbols(value: str) -> tuple[str, ...]:
    symbols = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    if symbols != ("EURUSD", "USDJPY"):
        raise ValueError("REPLAY_SYMBOL_SCOPE_INVALID")
    return symbols


def _critical_paths(symbols: tuple[str, ...]) -> list[Path]:
    model_root = forex_model_root(PROJECT_ROOT)
    paths = [configured_sqlite_path()]
    for symbol in symbols:
        paths.extend(
            forex_dataset_path(symbol, timeframe, project_root=PROJECT_ROOT)
            for timeframe in ("H1", "H4", "D1")
        )
        paths.extend((
            model_root / "shadow" / f"{symbol}.pkl",
            model_root / f"latest_{symbol}.pkl",
            symbol_qualification_root(PROJECT_ROOT) / symbol / "evidence.json",
        ))
    quarantine = model_root / "legacy_quarantine"
    if quarantine.is_dir():
        paths.extend(path for path in quarantine.rglob("*") if path.is_file())
    return paths


def _real_state(symbols: tuple[str, ...]) -> dict:
    path = configured_sqlite_path().resolve()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        lifecycle = {
            symbol: dict(connection.execute(
                "SELECT symbol_code,status,qualified_at,updated_at FROM supported_symbols "
                "WHERE symbol_code=?", (symbol,)
            ).fetchone())
            for symbol in symbols
        }
        canaries = [
            dict(row) for row in connection.execute(
                "SELECT prediction_id,symbol,candle_timestamp,action,direction_score,"
                "decision_percentile,model_identity,model_generation,entry_price,status,"
                "resolved,execution_mode FROM predictions WHERE execution_mode='shadow' "
                "AND symbol IN ('EURUSD','USDJPY') ORDER BY prediction_id"
            ).fetchall()
        ]
    finally:
        connection.close()
    payload = json.dumps(
        {"lifecycle": lifecycle, "canaries": canaries},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        "lifecycle": lifecycle,
        "canaries": canaries,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main(argv=None) -> int:
    args = _parse_args(argv)
    symbols = _symbols(args.symbols)
    critical = snapshot_paths(_critical_paths(symbols))
    real_before = _real_state(symbols)
    with tempfile.TemporaryDirectory(prefix="astra-forex-replay-") as temporary:
        root = Path(temporary)
        log_path = root / "replay.log"
        with log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            captured, metadata = capture_mt5_sources(symbols)
            bounded = bound_sources_for_replay(captured, args.end)
            replay = HistoricalReplay(
                HistoricalReplayConfig(
                    start=args.start,
                    end=args.end,
                    symbols=symbols,
                    root=root,
                ),
                bounded,
                metadata,
            )
            result = replay.run()
        result["temporary_log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
        result["temporary_state_root"] = "deleted_on_exit"
    real_after = _real_state(symbols)
    changed = verify_snapshots(critical)
    result["real_state_isolation"] = {
        "changed_paths": changed,
        "real_state_fingerprint_before": real_before["sha256"],
        "real_state_fingerprint_after": real_after["sha256"],
        "real_db_unchanged": str(configured_sqlite_path().resolve()) not in changed,
        "canonical_datasets_unchanged": not any(
            str(forex_dataset_path(symbol, timeframe, project_root=PROJECT_ROOT).resolve()) in changed
            for symbol in symbols for timeframe in ("H1", "H4", "D1")
        ),
        "shadow_models_unchanged": not any(
            str((forex_model_root(PROJECT_ROOT) / "shadow" / f"{symbol}.pkl").resolve()) in changed
            for symbol in symbols
        ),
        "canaries_unchanged": real_before["canaries"] == real_after["canaries"],
        "lifecycle_unchanged": real_before["lifecycle"] == real_after["lifecycle"],
        "production_aliases_absent": all(
            not (forex_model_root(PROJECT_ROOT) / f"latest_{symbol}.pkl").exists()
            for symbol in symbols
        ),
        "lifecycle": {
            symbol: real_after["lifecycle"][symbol]["status"] for symbol in symbols
        },
    }
    result["production_promotion_executed"] = False
    result["activation_executed"] = False
    result["trading_executed"] = False
    result["operational_pass"] = bool(
        result["lookahead_violations"] == 0
        and result["duplicate_predictions"] == 0
        and result["authority_preflight_pass"]
        and result["initial_rolling_datasets_all_2000"]
        and not changed
        and result["real_state_isolation"]["canaries_unchanged"]
        and result["real_state_isolation"]["lifecycle_unchanged"]
        and result["real_state_isolation"]["production_aliases_absent"]
        and all(
            item["pending_directional"] == 0
            and item["predictions_generated"] == item["eligible_h1_events"]
            and item["eligible_h1_events"] + item["ineligible_h1_events"]
            == item["events"]["H1"]
            and item["generations"]
            and item["generations"][0]["generation"] == 1
            for item in result["symbols"].values()
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["operational_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
