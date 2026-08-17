#!/usr/bin/env python3
"""
ASTRA Autonomous Scheduler
==========================
Provider-agnostic scheduler for 24/7 operation on any Linux VM.
Runs via systemd timers or cron — NO Base44 dependency.

Usage:
    python scheduler/autonomous_scheduler.py --init           # First-run: generate all datasets
    python scheduler/autonomous_scheduler.py --timeframe H1    # Update H1 + predict
    python scheduler/autonomous_scheduler.py --timeframe H4    # Update H4 context only
    python scheduler/autonomous_scheduler.py --timeframe D1    # Update D1 context only
    python scheduler/autonomous_scheduler.py --status          # System health JSON
    python scheduler/autonomous_scheduler.py --add-symbol NZDUSD  # Add new symbol
"""
import sys
import os
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from astra_version import ASTRA_VERSION
from infra.db.database import get_database, DatabaseAdapter
from runtime_paths import forex_dataset_path
from forex.data.data_router import DataRouter
from forex.data.rolling_dataset import (
    ROLLING_WINDOW,
    RollingDataset,
    exclude_incomplete_candles,
)

logging.basicConfig(
    level=os.environ.get("ASTRA_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("astra.scheduler")

_configured_window = os.environ.get("ASTRA_ROLLING_WINDOW_SIZE")
if _configured_window not in (None, str(ROLLING_WINDOW)):
    logger.warning(
        "Ignoring ASTRA_ROLLING_WINDOW_SIZE=%s; production contract is %s",
        _configured_window,
        ROLLING_WINDOW,
    )

FETCH_BARS = ROLLING_WINDOW + 1
TIMEFRAMES = ["H1", "H4", "D1"]
PREDICTION_TIMEFRAME = "H1"
BOOTSTRAP_REVALIDATION_ISSUE = "initial_training_not_production_eligible"
DEFAULT_SYMBOLS = [
    ("EURUSD", "EUR/USD", 0.0001),
    ("GBPUSD", "GBP/USD", 0.0001),
    ("USDJPY", "USD/JPY", 0.01),
    ("AUDUSD", "AUD/USD", 0.0001),
]

def fetch_market_data(symbol: str, timeframe: str, count: int = FETCH_BARS):
    """Fetch real market data through ASTRA's canonical provider router."""
    router = DataRouter(symbol, timeframe)
    df = router.fetch(bars=count, raise_on_failure=True)
    return df, router.source_used


def _dataset_path(symbol: str, timeframe: str) -> Path:
    """Return the only path used for new production dataset writes."""
    return forex_dataset_path(symbol, timeframe, project_root=PROJECT_ROOT)


def _legacy_dataset_path(symbol: str, timeframe: str) -> Path:
    """Return the former mixed code/data path for read-only compatibility."""
    return PROJECT_ROOT / "forex" / "data" / f"{symbol}_{timeframe}.csv"


def save_dataset_csv(df, symbol: str, timeframe: str) -> str:
    """Compatibility wrapper using the canonical atomic dataset transaction."""
    path = _dataset_path(symbol, timeframe)
    dataset = RollingDataset(
        symbol, timeframe, max_rows=ROLLING_WINDOW, csv_path=path
    )
    return dataset.apply(df, include_existing=False)["path"]


def load_dataset_csv(symbol: str, timeframe: str):
    """Load a canonical dataset, with explicit legacy read compatibility."""
    import pandas as pd
    path = _dataset_path(symbol, timeframe)
    if not path.exists():
        path = _legacy_dataset_path(symbol, timeframe)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


def registry_entry_readiness(
    entry: dict | None,
    *,
    project_root: Path | str | None = None,
) -> dict:
    """Return evidence for the canonical production rolling-dataset contract.

    This is deliberately read-only.  ``ready`` requires registry metadata and
    the persisted CSV to agree, plus the existing :class:`RollingDataset`
    validation contract, exactly 2000 rows, and only closed candles.
    """
    reasons: list[str] = []
    if not entry:
        return {
            "ready": False,
            "status": "missing",
            "path": None,
            "actual_candle_count": 0,
            "reasons": ["Dataset registry entry is missing"],
        }

    registry_status = str(entry.get("status") or "pending").lower()
    if registry_status != "ready":
        reasons.append(f"Registry status is {registry_status!r}, not 'ready'")
    if entry.get("candle_count") != ROLLING_WINDOW:
        reasons.append(
            f"Registry candle_count is {entry.get('candle_count')!r}; "
            f"expected {ROLLING_WINDOW}"
        )
    if entry.get("rolling_window_size", ROLLING_WINDOW) != ROLLING_WINDOW:
        reasons.append(
            "Registry rolling_window_size does not match the production "
            f"window ({ROLLING_WINDOW})"
        )

    raw_path = entry.get("blob_path")
    if not raw_path:
        reasons.append("Registry blob_path is missing")
        return {
            "ready": False,
            "status": "pending" if registry_status == "pending" else "invalid",
            "path": None,
            "actual_candle_count": 0,
            "reasons": reasons,
        }

    path = Path(raw_path)
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_file():
        reasons.append(f"Dataset CSV does not exist: {path}")
        return {
            "ready": False,
            "status": "pending" if registry_status == "pending" else "invalid",
            "path": str(path),
            "actual_candle_count": 0,
            "reasons": reasons,
        }

    actual_count = 0
    try:
        dataset = RollingDataset(
            entry["symbol"],
            entry["timeframe"],
            max_rows=ROLLING_WINDOW,
            csv_path=path,
        )
        if not dataset.load():
            reasons.append("Dataset CSV cannot be loaded as canonical OHLCV data")
        else:
            validation = dataset.validate()
            persisted = dataset.get_df()
            actual_count = len(persisted)
            if not validation["ok"]:
                reasons.extend(validation.get("issues") or ["Dataset validation failed"])
            if actual_count != ROLLING_WINDOW:
                reasons.append(
                    f"Persisted candle count is {actual_count}; expected {ROLLING_WINDOW}"
                )
            closed_count = len(
                exclude_incomplete_candles(persisted, entry["timeframe"])
            )
            if closed_count != actual_count:
                reasons.append(
                    f"Dataset contains {actual_count - closed_count} incomplete candle(s)"
                )
            if actual_count != entry.get("candle_count"):
                reasons.append(
                    "Registry candle_count does not match the persisted CSV "
                    f"({entry.get('candle_count')!r} != {actual_count})"
                )
            actual_last = str(persisted["timestamp"].iloc[-1]) if actual_count else None
            if actual_last != str(entry.get("last_candle_timestamp")):
                reasons.append(
                    "Registry last_candle_timestamp does not match the persisted CSV "
                    f"({entry.get('last_candle_timestamp')!r} != {actual_last!r})"
                )
    except Exception as exc:
        reasons.append(f"Dataset verification raised {type(exc).__name__}: {exc}")

    ready = registry_status == "ready" and not reasons
    return {
        "ready": ready,
        "status": "ready" if ready else (
            "pending" if registry_status == "pending" and actual_count < ROLLING_WINDOW
            else "invalid"
        ),
        "path": str(path),
        "actual_candle_count": actual_count,
        "reasons": reasons,
    }


def _registry_entry_is_ready(entry: dict | None) -> bool:
    """Backward-compatible boolean wrapper for scheduler call sites."""
    return registry_entry_readiness(entry)["ready"]


def _upsert_successful_dataset(
    db: DatabaseAdapter,
    symbol: str,
    timeframe: str,
    stored: dict,
) -> str:
    """Update registry only after the dataset transaction has committed."""
    candle_count = int(stored["rows"])
    status = "ready" if candle_count == ROLLING_WINDOW else "pending"
    db.upsert_dataset_registry({
        "symbol": symbol,
        "timeframe": timeframe,
        "candle_count": candle_count,
        "rolling_window_size": ROLLING_WINDOW,
        "last_candle_timestamp": str(stored["last_timestamp"]),
        "blob_path": stored["path"],
        "status": status,
        "last_error": None,
    })
    return status


def run_init(db: DatabaseAdapter):
    """First-run: generate datasets for all supported symbols × all timeframes."""
    symbols = db.get_supported_symbols()
    if not symbols:
        logger.info("No symbols in DB — seeding defaults...")
        for code, name, pip in DEFAULT_SYMBOLS:
            db.add_symbol(code, name, pip)
        symbols = db.get_supported_symbols()

    results = []
    for sym in symbols:
        code = sym["symbol_code"]
        for tf in TIMEFRAMES:
            existing = db.get_dataset_registry(code, tf)
            entry = existing[0] if existing else None
            if _registry_entry_is_ready(entry):
                logger.info(f"SKIP {code} {tf} — already exists ({existing[0]['candle_count']} candles)")
                results.append({"symbol": code, "timeframe": tf, "action": "skip"})
                continue

            logger.info(f"GENERATE {code} {tf}...")
            result = run_rolling_update(db, code, tf)
            results.append({"symbol": code, "timeframe": tf, **result})

    return results


def run_rolling_update(db: DatabaseAdapter, symbol: str, timeframe: str) -> dict:
    """Acquire, validate and atomically update one production rolling dataset."""
    registry = db.get_dataset_registry(symbol, timeframe)
    entry = registry[0] if registry else None
    path = _dataset_path(symbol, timeframe)
    existed_before = path.is_file()
    logger.info(
        "UPDATE %s %s - current=%s",
        symbol,
        timeframe,
        entry.get("last_candle_timestamp") if entry else "none",
    )

    try:
        df_new, source = fetch_market_data(symbol, timeframe, FETCH_BARS)
        dataset = RollingDataset(
            symbol, timeframe, max_rows=ROLLING_WINDOW, csv_path=path
        )
        stored = dataset.update_frame(df_new)
        status = _upsert_successful_dataset(db, symbol, timeframe, stored)
    except Exception as exc:
        logger.error("UPDATE FAILED %s %s: %s", symbol, timeframe, exc)
        return {"action": "error", "error": str(exc)}

    if status != "ready":
        logger.warning(
            "%s %s remains pending: %s/%s closed candles",
            symbol, timeframe, stored["rows"], ROLLING_WINDOW,
        )
        return {
            "action": "pending",
            "status": status,
            "total": stored["rows"],
            "added": stored["added"],
            "source": source,
        }

    action = "updated" if existed_before else "generated"
    logger.info(
        "%s %s %s: +%s, total=%s, source=%s",
        symbol, timeframe, action, stored["added"], stored["rows"], source,
    )
    return {
        "action": action,
        "status": status,
        "total": stored["rows"],
        "candles": stored["rows"],
        "added": stored["added"],
        "source": source,
    }


def _resolve_prediction_dataset(
    db: DatabaseAdapter,
    symbol: str,
    timeframe: str,
    *,
    required: bool,
) -> str | None:
    """Resolve and validate one scheduler dataset path."""
    registry = db.get_dataset_registry(symbol, timeframe)
    entry = registry[0] if registry else None

    candidates: list[Path | str] = []
    if entry and entry.get("status") == "ready":
        if entry.get("blob_path"):
            candidates.append(entry["blob_path"])

    candidates.extend((
        _dataset_path(symbol, timeframe),
        _legacy_dataset_path(symbol, timeframe),
    ))

    checked = []
    for raw_path in candidates:
        path = Path(raw_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        checked.append(str(path))
        if path.is_file():
            return str(path)

    message = f"Dataset CSV not found for {symbol} {timeframe}"
    if checked:
        message += f"; checked: {', '.join(checked)}"
    if required:
        raise FileNotFoundError(message)

    logger.info("  Optional MTF dataset unavailable: %s", message)
    return None


def run_prediction(db: DatabaseAdapter, symbol: str, timeframe: str) -> dict:
    """Run the H1 prediction pipeline for a symbol.

    H4 and D1 scheduler cycles maintain context datasets only.  The integrated
    predictor uses an H1 primary dataset enriched with those higher timeframes.
    """
    if timeframe != PREDICTION_TIMEFRAME:
        logger.info(
            "  PREDICT SKIPPED %s %s — executable predictions are %s-only",
            symbol,
            timeframe,
            PREDICTION_TIMEFRAME,
        )
        return {
            "action": "skip",
            "reason": "prediction_timeframe_not_supported",
            "timeframe": timeframe,
            "supported_timeframe": PREDICTION_TIMEFRAME,
        }

    try:
        filepath = _resolve_prediction_dataset(db, symbol, timeframe, required=True)
        path_h4 = _resolve_prediction_dataset(db, symbol, "H4", required=False)
        path_d1 = _resolve_prediction_dataset(db, symbol, "D1", required=False)

        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
        pipeline = ForexIntegratedPipeline()
        pipeline.closed_loop_database = db
        h1_registry = db.get_dataset_registry(symbol, timeframe)
        if h1_registry:
            entry = h1_registry[0]
            pipeline.closed_loop_dataset_provenance = {
                "registry_id": entry.get("id"),
                "blob_path": entry.get("blob_path"),
                "candle_count": entry.get("candle_count"),
                "rolling_window_size": entry.get("rolling_window_size"),
                "last_candle_timestamp": entry.get("last_candle_timestamp"),
                "last_updated": entry.get("last_updated"),
            }
        result = pipeline.predict(
            filepath=filepath,
            pair=symbol,
            path_h4=path_h4,
            path_d1=path_d1,
        )
        if result is None:
            return {"action": "skip", "reason": "pipeline_returned_none"}
        if not isinstance(result, dict):
            raise TypeError(
                "ForexIntegratedPipeline.predict() must return a dict, "
                f"got {type(result).__name__}"
            )
        if result.get("error"):
            raise RuntimeError(str(result["error"]))

        final_action = result.get("action")
        if not final_action:
            raise ValueError(
                "ForexIntegratedPipeline.predict() result is missing canonical 'action'"
            )
        final_action = str(final_action).upper()

        confidence = result.get("confidence")
        if confidence is None:
            confidence = float(result.get("signal_strength", 50.0)) / 100.0
        else:
            confidence = float(confidence)
            if confidence > 1.0:
                confidence /= 100.0

        pred = {
            "symbol": symbol,
            "pair": symbol,
            "timeframe": timeframe,
            "action": final_action,
            "direction": final_action,
            "raw_action": result.get("raw_action"),
            "prediction_id": result.get("prediction_id"),
            "confidence": confidence,
            "reliability_score": result.get("reliability_score"),
            "entry_price": float(result.get("entry_price", 0)),
            "stop_loss": float(result.get("stop_loss", 0)),
            "take_profit": float(result.get("take_profit", 0)),
            "features_snapshot": result.get("features", {}),
            # Release of the ASTRA runtime that generated this prediction.
            "pipeline_version": f"v{ASTRA_VERSION}",
            "predicted_at": datetime.now().isoformat(),
            "candle_timestamp": result.get("candle_timestamp"),
            "horizon_candles": result.get("horizon_candles"),
            "model_identity": result.get("model_identity"),
        }
        registry = db.get_dataset_registry(symbol, timeframe)
        if registry:
            dataset_entry = registry[0]
            pred["candle_timestamp"] = (
                pred["candle_timestamp"]
                or dataset_entry.get("last_candle_timestamp")
                or pred["predicted_at"]
            )
            pred["dataset_provenance"] = {
                "registry_id": dataset_entry.get("id"),
                "blob_path": dataset_entry.get("blob_path"),
                "candle_count": dataset_entry.get("candle_count"),
                "rolling_window_size": dataset_entry.get("rolling_window_size"),
                "last_candle_timestamp": dataset_entry.get("last_candle_timestamp"),
                "last_updated": dataset_entry.get("last_updated"),
            }
        else:
            pred["candle_timestamp"] = pred["candle_timestamp"] or pred["predicted_at"]
        saved = None
        if pred.get("prediction_id") and hasattr(db, "get_prediction"):
            saved = db.get_prediction(pred["prediction_id"])
        if saved is None:
            saved = db.save_prediction(pred)
        logger.info(f"  PREDICT {symbol} {timeframe} → {pred['direction']} conf={pred['confidence']:.2f}")
        return {"action": "predicted", "prediction": saved}
    except Exception as e:
        logger.error(f"  PREDICT FAILED {symbol} {timeframe}: {e}")
        return {"action": "error", "error": str(e)}


def run_closed_loop_maintenance(
    db: DatabaseAdapter,
    symbol: str,
    timeframe: str,
) -> dict:
    """Mature outcomes and persist retrain eligibility from the H1 dataset."""
    if timeframe != PREDICTION_TIMEFRAME:
        return {"action": "skip", "reason": "closed_loop_is_h1_only"}
    required_methods = (
        "get_pending_predictions",
        "get_finalized_outcomes",
        "get_retrain_runs",
    )
    if not all(hasattr(db, method) for method in required_methods):
        return {"action": "skip", "reason": "database_has_no_closed_loop_contract"}
    registry = db.get_dataset_registry(symbol, timeframe)
    if not registry:
        return {"action": "error", "error": "dataset registry entry is missing"}
    entry = registry[0]
    if entry.get("status") != "ready":
        return {"action": "skip", "reason": "dataset_is_not_ready"}
    try:
        path = Path(
            _resolve_prediction_dataset(db, symbol, timeframe, required=True)
        )
        from forex.prediction.outcome_tracker import OutcomeTracker
        from forex.prediction.model_storage import ModelStorage
        from forex.prediction.retrain_manager import RetrainManager

        manager = RetrainManager(
            database=db,
            storage=ModelStorage(PROJECT_ROOT / "models" / "forex"),
        )
        provenance = {
            "registry_id": entry.get("id"),
            "blob_path": entry.get("blob_path"),
            "candle_count": entry.get("candle_count"),
            "rolling_window_size": entry.get("rolling_window_size"),
            "last_candle_timestamp": entry.get("last_candle_timestamp"),
            "last_updated": entry.get("last_updated"),
        }
        reconciliation = manager.reconcile()
        symbol_issues = [
            issue for issue in reconciliation["issues"]
            if issue.get("symbol") == symbol
        ]
        bootstrap_result = None
        audit = manager.audit_pair_model(symbol)
        bootstrap_allowed = (
            len(symbol_issues) == 1
            and symbol_issues[0].get("code") == BOOTSTRAP_REVALIDATION_ISSUE
            and audit.get("bootstrap_revalidation") is True
        )
        if bootstrap_allowed:
            from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

            pipeline = ForexIntegratedPipeline()
            pipeline.storage = manager.storage
            pipeline.closed_loop_database = db
            pipeline.closed_loop_dataset_provenance = provenance
            bootstrap_result = pipeline.bootstrap_revalidate(
                str(path),
                pair=symbol,
                path_h4=_resolve_prediction_dataset(db, symbol, "H4", required=False),
                path_d1=_resolve_prediction_dataset(db, symbol, "D1", required=False),
                manager=manager,
            )
            reconciliation = manager.reconcile()
            symbol_issues = [
                issue for issue in reconciliation["issues"]
                if issue.get("symbol") == symbol
            ]
        if symbol_issues:
            return {
                "action": "error",
                "error": "model provenance reconciliation failed",
                "issues": symbol_issues,
                "bootstrap_revalidation": bootstrap_result,
            }
        finalized = OutcomeTracker(database=db).evaluate_from_csv(
            path, pair=symbol, timeframe=timeframe
        )
        pending = manager.ensure_pending_from_outcomes(
            symbol, timeframe=timeframe, dataset_provenance=provenance
        )
        return {
            "action": "maintained",
            "outcomes_finalized": finalized,
            "retrain_run_id": pending.get("run_id") if pending else None,
            "retrain_status": pending.get("status") if pending else None,
            "bootstrap_revalidation": bootstrap_result,
        }
    except Exception as exc:
        logger.error("  CLOSED LOOP FAILED %s %s: %s", symbol, timeframe, exc)
        return {"action": "error", "error": str(exc)}


def detect_new_symbols(db: DatabaseAdapter) -> list:
    """Find symbols in supported_symbols without datasets. Generate missing."""
    symbols = db.get_supported_symbols()
    generated = []
    for sym in symbols:
        code = sym["symbol_code"]
        for tf in TIMEFRAMES:
            existing = db.get_dataset_registry(code, tf)
            entry = existing[0] if existing else None
            if not _registry_entry_is_ready(entry):
                logger.info(f"NEW SYMBOL DETECTED: {code} {tf} — generating...")
                result = run_rolling_update(db, code, tf)
                if result.get("action") != "error":
                    generated.append({"symbol": code, "timeframe": tf, **result})
    return generated


def _evaluate_h1_model_gate(
    db: DatabaseAdapter,
    symbol: str,
    timeframe: str,
) -> dict:
    """Evaluate model eligibility after the cycle's dataset update attempt."""
    if timeframe != PREDICTION_TIMEFRAME:
        return {"prediction_eligible": False, "reason": "prediction_is_h1_only"}

    bootstrap_revalidation = False
    if hasattr(db, "get_retrain_runs"):
        try:
            from forex.prediction.retrain_manager import RetrainManager
            from forex.prediction.model_storage import ModelStorage

            manager = RetrainManager(
                database=db,
                storage=ModelStorage(PROJECT_ROOT / "models" / "forex"),
            )
            reconciliation = manager.reconcile()
            symbol_issues = [
                issue for issue in reconciliation["issues"]
                if issue.get("symbol") == symbol
            ]
            audit = manager.audit_pair_model(symbol)
            bootstrap_revalidation = (
                len(symbol_issues) == 1
                and symbol_issues[0].get("code")
                == BOOTSTRAP_REVALIDATION_ISSUE
                and audit.get("bootstrap_revalidation") is True
            )
            if symbol_issues and not bootstrap_revalidation:
                logger.error(
                    "Model provenance mismatch - blocking H1 prediction for %s",
                    symbol,
                )
                return {
                    "prediction_eligible": False,
                    "reason": "model_provenance_reconciliation_failed",
                    "issues": symbol_issues,
                    "audit_reason": audit.get("reason"),
                }
            if not audit.get("eligible") and not bootstrap_revalidation:
                logger.warning(
                    "Model for %s is not production eligible - blocking H1 prediction: %s",
                    symbol,
                    audit.get("reason", "unknown"),
                )
                return {
                    "prediction_eligible": False,
                    "reason": "model_not_production_eligible",
                    "audit_reason": audit.get("reason", "UNKNOWN"),
                }
            if bootstrap_revalidation:
                logger.info(
                    "Legacy alias restricted to bootstrap revalidation for %s",
                    symbol,
                )
                return {
                    "prediction_eligible": False,
                    "bootstrap_revalidation": True,
                    "reason": "bootstrap_revalidation_required",
                    "audit_reason": audit.get("reason"),
                }
        except Exception as exc:
            logger.error(
                "Model provenance reconciliation failed closed for %s: %s",
                symbol,
                exc,
            )
            return {
                "prediction_eligible": False,
                "reason": "model_provenance_check_failed",
                "error": f"{type(exc).__name__}: {exc}",
            }

    try:
        from robustness.model_integrity_checker import check_model_before_cycle

        if not check_model_before_cycle(symbol, timeframe):
            logger.warning(
                "Model for %s %s failed integrity check - prediction blocked",
                symbol,
                timeframe,
            )
            return {
                "prediction_eligible": False,
                "reason": "model_integrity_check_failed",
            }
    except Exception as exc:
        logger.error(
            "Model integrity check failed closed for %s %s: %s",
            symbol,
            timeframe,
            exc,
        )
        return {
            "prediction_eligible": False,
            "reason": "model_integrity_check_error",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {"prediction_eligible": True, "reason": "production_eligible"}


def run_cycle(db: DatabaseAdapter, timeframe: str):
    """Update one timeframe and run a prediction only for the H1 cycle."""
    from scheduler.run_state import is_scheduler_run_stale, utc_timestamp

    recovered_at = utc_timestamp()
    for previous in db.get_scheduler_runs(limit=1000):
        if not is_scheduler_run_stale(previous):
            continue
        reason = (
            "Interrupted scheduler process detected before a new cycle; "
            "the prior run was not completed"
        )
        db.update_scheduler_run(previous["id"], {
            "status": "interrupted",
            "finished_at": recovered_at,
            "recovered_at": recovered_at,
            "interruption_reason": reason,
            "errors_count": max(1, int(previous.get("errors_count") or 0)),
        })
        logger.warning(
            "Recovered stale scheduler run #%s (%s) as interrupted",
            previous.get("id"),
            previous.get("timeframe"),
        )
    run = db.create_scheduler_run({
        "timeframe": timeframe,
        "started_at": utc_timestamp(),
        "status": "running"
    })
    run_id = run["id"]
    logger.info(f"=== CYCLE START: {timeframe} (run #{run_id}) ===")

    symbols = db.get_supported_symbols()
    symbols_processed = 0
    predictions_generated = 0
    errors_count = 0
    results = []

    # 1. Detect new symbols
    new = detect_new_symbols(db)
    if new:
        logger.info(f"New symbol datasets generated: {len(new)}")
        symbols = db.get_supported_symbols()

    # 2. Rolling update + prediction for each symbol
    for sym in symbols:
        code = sym["symbol_code"]
        symbols_processed += 1

        update_result = run_rolling_update(db, code, timeframe)
        results.append({"symbol": code, "update": update_result})

        model_gate = None
        if timeframe == PREDICTION_TIMEFRAME:
            model_gate = _evaluate_h1_model_gate(db, code, timeframe)

        if update_result.get("action") == "error":
            errors_count += 1

        if model_gate is not None and not (
            model_gate.get("prediction_eligible")
            or model_gate.get("bootstrap_revalidation")
        ):
            errors_count += 1
            results.append({
                "symbol": code,
                "predict": {
                    "action": "skip",
                    **{
                        key: value for key, value in model_gate.items()
                        if key != "prediction_eligible"
                    },
                },
            })
            continue

        if (
            timeframe == PREDICTION_TIMEFRAME
            and update_result.get("action") in ("updated", "generated")
        ):
            closed_loop_result = run_closed_loop_maintenance(db, code, timeframe)
            results.append({"symbol": code, "closed_loop": closed_loop_result})
            if closed_loop_result.get("action") == "error":
                errors_count += 1
            if model_gate and model_gate.get("bootstrap_revalidation"):
                try:
                    from forex.prediction.retrain_manager import RetrainManager
                    from forex.prediction.model_storage import ModelStorage

                    post_manager = RetrainManager(
                        database=db,
                        storage=ModelStorage(PROJECT_ROOT / "models" / "forex"),
                    )
                    post_reconciliation = post_manager.reconcile()
                    post_issues = [
                        issue for issue in post_reconciliation["issues"]
                        if issue.get("symbol") == code
                    ]
                    post_audit = post_manager.audit_pair_model(code)
                    production_eligible = (
                        not post_issues and post_audit.get("eligible") is True
                    )
                except Exception as exc:
                    logger.error(
                        "Bootstrap post-reconciliation failed closed for %s: %s",
                        code,
                        exc,
                    )
                    production_eligible = False
                if not production_eligible:
                    if closed_loop_result.get("action") != "error":
                        errors_count += 1
                    logger.error(
                        "Bootstrap revalidation did not produce an eligible alias; "
                        "prediction remains blocked for %s",
                        code,
                    )
                    results.append({
                        "symbol": code,
                        "predict": {
                            "action": "skip",
                            "reason": "bootstrap_revalidation_not_production_eligible",
                        },
                    })
                    continue
            pred_result = run_prediction(db, code, timeframe)
            results.append({"symbol": code, "predict": pred_result})
            if pred_result.get("action") == "predicted":
                predictions_generated += 1
            elif pred_result.get("action") == "error":
                errors_count += 1

    # 3. Update scheduler run
    db.update_scheduler_run(run_id, {
        "status": "completed" if errors_count == 0 else "partial",
        "finished_at": utc_timestamp(),
        "symbols_processed": symbols_processed,
        "predictions_generated": predictions_generated,
        "errors_count": errors_count
    })

    logger.info(f"=== CYCLE END: {timeframe} — processed={symbols_processed} "
                f"predictions={predictions_generated} errors={errors_count} ===")

    return {
        "run_id": run_id,
        "timeframe": timeframe,
        "symbols_processed": symbols_processed,
        "predictions_generated": predictions_generated,
        "errors_count": errors_count,
        "results": results
    }


def get_status(db: DatabaseAdapter) -> dict:
    """Return scheduler health backed by registry and persisted CSV evidence."""
    try:
        health = dict(db.get_system_health())
        entries = db.get_dataset_registry()
        declared_ready = [
            entry for entry in entries if entry.get("status") == "ready"
        ]
        verified_ready = [
            entry for entry in declared_ready if _registry_entry_is_ready(entry)
        ]
        inconsistent = len(declared_ready) - len(verified_ready)
        active_symbols = int(health.get("symbols_active", 0) or 0)
        expected_datasets = active_symbols * len(TIMEFRAMES)
        complete = expected_datasets > 0 and len(verified_ready) == expected_datasets
        health.update({
            "datasets_verified_ready": len(verified_ready),
            "datasets_registry_inconsistent": inconsistent,
            "datasets_expected": expected_datasets,
            "healthy": bool(health.get("healthy")) and complete and inconsistent == 0,
            "health_evidence": "registry_and_persisted_csv_verified",
        })
        return health
    except Exception as exc:
        return {
            "healthy": False,
            "health_evidence": "verification_error",
            "error": f"{type(exc).__name__}: {exc}",
        }


def main():
    parser = argparse.ArgumentParser(description="ASTRA Autonomous Scheduler")
    parser.add_argument("--init", action="store_true", help="Generate initial datasets")
    parser.add_argument("--timeframe", type=str, help="Run cycle for H1/H4/D1")
    parser.add_argument("--status", action="store_true", help="Print system health JSON")
    parser.add_argument("--add-symbol", type=str, help="Add a new symbol (e.g. EURUSD)")
    args = parser.parse_args()

    try:
        db = get_database()
    except Exception as exc:
        if args.init or args.timeframe:
            payload = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            if args.init:
                payload["init"] = []
            print(json.dumps(payload, indent=2, default=str))
            raise SystemExit(1)
        raise

    if args.status:
        health = get_status(db)
        print(json.dumps(health, indent=2, default=str))
        return

    if args.add_symbol:
        code = args.add_symbol.upper()
        if len(code) != 6 or not code.isalpha():
            print(json.dumps({"ok": False, "error": "Symbol must be 6 letters"}))
            sys.exit(1)
        sym = db.add_symbol(code, code, 0.0001)
        print(json.dumps({"ok": True, "symbol": code, "message": f"Added {code}. Datasets will generate on next cycle."}))
        return

    if args.init:
        try:
            result = run_init_with_deployment_check(db)
        except Exception as exc:
            print(json.dumps({
                "ok": False,
                "init": [],
                "error": f"{type(exc).__name__}: {exc}",
            }, indent=2, default=str))
            raise SystemExit(1)
        deployment = result.get("deployment")
        internal_failure = "deployment_error" in result
        incomplete = bool(deployment is not None and deployment.get("ready") is not True)
        exit_code = 1 if internal_failure else (2 if incomplete else 0)
        payload = {"ok": exit_code == 0, "init": result["init_results"]}
        if "deployment" in result:
            payload["deployment"] = result["deployment"]
        if "deployment_error" in result:
            payload["deployment_error"] = result["deployment_error"]
        print(json.dumps(payload, indent=2, default=str))
        if exit_code:
            raise SystemExit(exit_code)
        return

    if args.timeframe:
        tf = args.timeframe.upper()
        if tf not in TIMEFRAMES:
            print(json.dumps({"ok": False, "error": f"Invalid timeframe: {tf}. Must be H1, H4, or D1"}))
            sys.exit(1)
        try:
            result = run_cycle(db, tf)
        except Exception as exc:
            print(json.dumps({
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }, indent=2, default=str))
            raise SystemExit(1)
        partial = int(result.get("errors_count", 0)) > 0
        print(json.dumps({
            "ok": not partial,
            "cycle": result,
        }, indent=2, default=str))
        if partial:
            raise SystemExit(2)
        return

    parser.print_help()


# ─────────────────────────────────────────────────────────
# First Deployment Experience — hook automatico
# ─────────────────────────────────────────────────────────
def run_init_with_deployment_check(db: DatabaseAdapter, force: bool = False) -> dict:
    """
    run_init() + First Deployment Experience.
    Ejecuta el init normal y luego, si es primera vez (o force=True),
    lanza el validador de despliegue completo.
    """
    # 1. Init normal
    init_results = run_init(db)

    # 2. Detectar si es primera vez (sin predicciones previas)
    is_first = True
    try:
        preds = db.get_predictions(limit=1)
        is_first = not preds
    except Exception:
        pass

    if is_first or force:
        logger.info("=== First Deployment Experience: iniciando validacion automatica ===")
        try:
            from deployment.first_run_validator import run_first_deployment_check
            deploy_result = run_first_deployment_check(
                db=db,
                force=force,
            )
            logger.info(f"=== First Deployment Experience: {deploy_result['deployment_status']} | "
                       f"Readiness: {deploy_result['readiness_status']} ===")
            return {
                "init_results": init_results,
                "deployment": deploy_result,
            }
        except Exception as e:
            logger.error(f"First Deployment Experience fallo: {e}")
            import traceback; traceback.print_exc()
            return {
                "init_results": init_results,
                "deployment_error": str(e),
            }
    else:
        logger.info("No es primera instalacion — saltando First Deployment Experience")
        return {"init_results": init_results}


if __name__ == "__main__":
    main()
