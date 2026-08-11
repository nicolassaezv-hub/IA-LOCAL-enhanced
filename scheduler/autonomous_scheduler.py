#!/usr/bin/env python3
"""
ASTRA Autonomous Scheduler (v6.0.1-prod)
========================================
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

from infra.db.database import get_database, DatabaseAdapter
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


def _dataset_path(symbol: str, timeframe: str, registry_entry: dict = None) -> Path:
    canonical = PROJECT_ROOT / "forex" / "data" / f"{symbol}_{timeframe}.csv"
    raw_path = registry_entry.get("blob_path") if registry_entry else None
    if raw_path:
        path = Path(raw_path)
        path = path if path.is_absolute() else PROJECT_ROOT / path
        if path.exists() or not canonical.exists():
            return path
    return canonical


def save_dataset_csv(df, symbol: str, timeframe: str) -> str:
    """Compatibility wrapper using the canonical atomic dataset transaction."""
    path = _dataset_path(symbol, timeframe)
    dataset = RollingDataset(
        symbol, timeframe, max_rows=ROLLING_WINDOW, csv_path=path
    )
    return dataset.apply(df, include_existing=False)["path"]


def load_dataset_csv(symbol: str, timeframe: str):
    """Load existing dataset CSV. Returns DataFrame or None."""
    import pandas as pd
    path = PROJECT_ROOT / "forex" / "data" / f"{symbol}_{timeframe}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


def _registry_entry_is_ready(entry: dict | None) -> bool:
    """Ready means exactly 2000 persisted candles and matching metadata."""
    if not entry or entry.get("status") != "ready":
        return False
    if entry.get("candle_count") != ROLLING_WINDOW:
        return False
    if entry.get("rolling_window_size", ROLLING_WINDOW) != ROLLING_WINDOW:
        return False
    raw_path = entry.get("blob_path")
    if not raw_path:
        return False
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        return False
    try:
        dataset = RollingDataset(
            entry["symbol"],
            entry["timeframe"],
            max_rows=ROLLING_WINDOW,
            csv_path=path,
        )
        if not dataset.load() or not dataset.validate()["ok"]:
            return False
        persisted = dataset.get_df()
        return (
            len(persisted) == ROLLING_WINDOW
            and len(exclude_incomplete_candles(persisted, entry["timeframe"]))
            == ROLLING_WINDOW
            and str(persisted["timestamp"].iloc[-1])
            == str(entry.get("last_candle_timestamp"))
        )
    except Exception:
        return False


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
    path = _dataset_path(symbol, timeframe, entry)
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

    raw_path = None
    if entry and entry.get("status") == "ready":
        raw_path = entry.get("blob_path")

    if not raw_path:
        canonical = PROJECT_ROOT / "forex" / "data" / f"{symbol}_{timeframe}.csv"
        if canonical.is_file():
            raw_path = canonical

    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.is_file():
            return str(path)

    message = f"Dataset CSV not found for {symbol} {timeframe}"
    if raw_path:
        message += f": {raw_path}"
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
            "confidence": confidence,
            "reliability_score": result.get("reliability_score"),
            "entry_price": float(result.get("entry_price", 0)),
            "stop_loss": float(result.get("stop_loss", 0)),
            "take_profit": float(result.get("take_profit", 0)),
            "features_snapshot": result.get("features", {}),
            "pipeline_version": "v6.0.1",
            "predicted_at": datetime.now().isoformat()
        }
        saved = db.save_prediction(pred)
        logger.info(f"  PREDICT {symbol} {timeframe} → {pred['direction']} conf={pred['confidence']:.2f}")
        return {"action": "predicted", "prediction": saved}
    except Exception as e:
        logger.error(f"  PREDICT FAILED {symbol} {timeframe}: {e}")
        return {"action": "error", "error": str(e)}


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


def run_cycle(db: DatabaseAdapter, timeframe: str):
    """Update one timeframe and run a prediction only for the H1 cycle."""
    run = db.create_scheduler_run({
        "timeframe": timeframe,
        "started_at": datetime.now().isoformat(),
        "status": "running"
    })
    run_id = run["id"]
    logger.info(f"=== CYCLE START: {timeframe} (run #{run_id}) ===")

    symbols = db.get_supported_symbols()
    symbols_processed = 0

    # ── Model integrity check before executable prediction cycles ──
    if timeframe == PREDICTION_TIMEFRAME:
        try:
            from robustness.model_integrity_checker import check_model_before_cycle
            blocked_symbols = []
            for sym in symbols:
                code = sym["symbol_code"]
                if not check_model_before_cycle(code, timeframe):
                    blocked_symbols.append(code)
                    logger.warning(f"Model for {code} {timeframe} failed integrity check — BLOCKED for this cycle")
            if blocked_symbols:
                symbols = [s for s in symbols if s["symbol_code"] not in blocked_symbols]
                logger.info(f"Blocked {len(blocked_symbols)} symbols due to model issues: {blocked_symbols}")
        except Exception as e:
            logger.warning(f"Model integrity check skipped: {e}")
    predictions_generated = 0
    errors_count = 0
    results = []

    # 1. Detect new symbols
    new = detect_new_symbols(db)
    if new:
        logger.info(f"New symbol datasets generated: {len(new)}")
        symbols = db.get_supported_symbols()  # refresh

    # 2. Rolling update + prediction for each symbol
    for sym in symbols:
        code = sym["symbol_code"]
        symbols_processed += 1

        update_result = run_rolling_update(db, code, timeframe)
        results.append({"symbol": code, "update": update_result})

        if (
            timeframe == PREDICTION_TIMEFRAME
            and update_result.get("action") in ("updated", "generated")
        ):
            pred_result = run_prediction(db, code, timeframe)
            results.append({"symbol": code, "predict": pred_result})
            if pred_result.get("action") == "predicted":
                predictions_generated += 1
            elif pred_result.get("action") == "error":
                errors_count += 1
        elif update_result.get("action") == "error":
            errors_count += 1

    # 3. Update scheduler run
    db.update_scheduler_run(run_id, {
        "status": "completed" if errors_count == 0 else "partial",
        "finished_at": datetime.now().isoformat(),
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
    """Return system health as a dict."""
    return db.get_system_health()


def main():
    parser = argparse.ArgumentParser(description="ASTRA Autonomous Scheduler")
    parser.add_argument("--init", action="store_true", help="Generate initial datasets")
    parser.add_argument("--timeframe", type=str, help="Run cycle for H1/H4/D1")
    parser.add_argument("--status", action="store_true", help="Print system health JSON")
    parser.add_argument("--add-symbol", type=str, help="Add a new symbol (e.g. EURUSD)")
    args = parser.parse_args()

    db = get_database()

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
        result = run_init_with_deployment_check(db)
        payload = {"ok": True, "init": result["init_results"]}
        if "deployment" in result:
            payload["deployment"] = result["deployment"]
        if "deployment_error" in result:
            payload["deployment_error"] = result["deployment_error"]
        print(json.dumps(payload, indent=2, default=str))
        return

    if args.timeframe:
        tf = args.timeframe.upper()
        if tf not in TIMEFRAMES:
            print(json.dumps({"ok": False, "error": f"Invalid timeframe: {tf}. Must be H1, H4, or D1"}))
            sys.exit(1)
        result = run_cycle(db, tf)
        print(json.dumps({"ok": True, "cycle": result}, indent=2, default=str))
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
