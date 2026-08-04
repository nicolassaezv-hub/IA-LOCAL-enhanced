#!/usr/bin/env python3
"""
ASTRA Autonomous Scheduler (v6.0.1-prod)
========================================
Provider-agnostic scheduler for 24/7 operation on any Linux VM.
Runs via systemd timers or cron — NO Base44 dependency.

Usage:
    python scheduler/autonomous_scheduler.py --init           # First-run: generate all datasets
    python scheduler/autonomous_scheduler.py --timeframe H1    # Run one H1 cycle
    python scheduler/autonomous_scheduler.py --timeframe H4    # Run one H4 cycle
    python scheduler/autonomous_scheduler.py --timeframe D1    # Run one D1 cycle
    python scheduler/autonomous_scheduler.py --status          # System health JSON
    python scheduler/autonomous_scheduler.py --add-symbol NZDUSD  # Add new symbol
"""
import sys
import os
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infra.db.database import get_database, DatabaseAdapter

logging.basicConfig(
    level=os.environ.get("ASTRA_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("astra.scheduler")

ROLLING_WINDOW = int(os.environ.get("ASTRA_ROLLING_WINDOW_SIZE", "2000"))
TIMEFRAMES = ["H1", "H4", "D1"]
DEFAULT_SYMBOLS = [
    ("EURUSD", "EUR/USD", 0.0001),
    ("GBPUSD", "GBP/USD", 0.0001),
    ("USDJPY", "USD/JPY", 0.01),
    ("AUDUSD", "AUD/USD", 0.0001),
]

# YFinance interval mapping
YF_INTERVAL = {"H1": "1h", "H4": "1h", "D1": "1d"}
YF_PERIOD = {"H1": "5d", "H4": "20d", "D1": "3mo"}


def fetch_yfinance(symbol: str, timeframe: str, count: int = 2000):
    """Download OHLCV data from Yahoo Finance. Returns DataFrame."""
    import yfinance as yf
    import pandas as pd

    ticker_str = f"{symbol}=X" if len(symbol) == 6 else symbol
    interval = YF_INTERVAL[timeframe]
    period = YF_PERIOD[timeframe]

    df = yf.download(ticker_str, interval=interval, period=period, progress=False)
    if df is None or df.empty:
        raise ValueError(f"No data returned for {symbol} {timeframe}")

    # Handle MultiIndex columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "datetime" in cl or cl == "index" or cl == "date":
            col_map[c] = "timestamp"
        elif cl == "open":
            col_map[c] = "open"
        elif cl == "high":
            col_map[c] = "high"
        elif cl == "low":
            col_map[c] = "low"
        elif cl == "close":
            col_map[c] = "close"
        elif "volume" in cl:
            col_map[c] = "volume"
    df = df.rename(columns=col_map)

    # Ensure required columns
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"Missing column {col} in yfinance data")
    if "volume" not in df.columns:
        df["volume"] = 0

    df["pair"] = symbol
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    df = df[["timestamp", "open", "high", "low", "close", "volume", "pair"]]

    # For H4: resample 1h to 4h
    if timeframe == "H4":
        df = df.set_index("timestamp")
        df = df.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum", "pair": "last"
        }).dropna().reset_index()

    # Trim to rolling window
    if len(df) > count:
        df = df.iloc[-count:]

    return df


def save_dataset_csv(df, symbol: str, timeframe: str) -> str:
    """Save DataFrame as CSV. Returns the file path."""
    data_dir = PROJECT_ROOT / "forex" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{symbol}_{timeframe}.csv"
    df.to_csv(path, index=False)
    return str(path)


def load_dataset_csv(symbol: str, timeframe: str):
    """Load existing dataset CSV. Returns DataFrame or None."""
    import pandas as pd
    path = PROJECT_ROOT / "forex" / "data" / f"{symbol}_{timeframe}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


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
            if existing and existing[0].get("status") == "ready":
                logger.info(f"SKIP {code} {tf} — already exists ({existing[0]['candle_count']} candles)")
                results.append({"symbol": code, "timeframe": tf, "action": "skip"})
                continue

            logger.info(f"GENERATE {code} {tf}...")
            try:
                df = fetch_yfinance(code, tf, ROLLING_WINDOW)
                path = save_dataset_csv(df, code, tf)
                db.upsert_dataset_registry({
                    "symbol": code, "timeframe": tf,
                    "candle_count": len(df),
                    "rolling_window_size": ROLLING_WINDOW,
                    "last_candle_timestamp": str(df["timestamp"].iloc[-1]),
                    "blob_path": path,
                    "status": "ready"
                })
                logger.info(f"  → {len(df)} candles saved to {path}")
                results.append({"symbol": code, "timeframe": tf, "action": "generated", "candles": len(df)})
            except Exception as e:
                logger.error(f"  → FAILED: {e}")
                db.upsert_dataset_registry({
                    "symbol": code, "timeframe": tf, "status": "error",
                    "last_error": str(e), "blob_path": ""
                })
                results.append({"symbol": code, "timeframe": tf, "action": "error", "error": str(e)})

    return results


def run_rolling_update(db: DatabaseAdapter, symbol: str, timeframe: str) -> dict:
    """Update a rolling dataset: add new candles, remove oldest, maintain window size."""
    import pandas as pd

    registry = db.get_dataset_registry(symbol, timeframe)
    if not registry or registry[0].get("status") != "ready":
        logger.info(f"SKIP {symbol} {timeframe} — no ready dataset, generating...")
        df = fetch_yfinance(symbol, timeframe, ROLLING_WINDOW)
        path = save_dataset_csv(df, symbol, timeframe)
        db.upsert_dataset_registry({
            "symbol": symbol, "timeframe": timeframe,
            "candle_count": len(df), "rolling_window_size": ROLLING_WINDOW,
            "last_candle_timestamp": str(df["timestamp"].iloc[-1]),
            "blob_path": path, "status": "ready"
        })
        return {"action": "generated", "candles": len(df)}

    reg = registry[0]
    last_ts = reg.get("last_candle_timestamp")
    logger.info(f"UPDATE {symbol} {timeframe} — last candle: {last_ts}")

    try:
        df_new = fetch_yfinance(symbol, timeframe, ROLLING_WINDOW)
    except Exception as e:
        logger.error(f"  → fetch failed: {e}")
        return {"action": "error", "error": str(e)}

    df_existing = load_dataset_csv(symbol, timeframe)
    if df_existing is not None and last_ts:
        last_dt = pd.to_datetime(last_ts)
        new_candles = df_new[df_new["timestamp"] > last_dt]
        if new_candles.empty:
            logger.info(f"  → no new candles (last={last_ts})")
            return {"action": "skip", "reason": "no_new_candles", "rows": len(df_existing)}

        # Append new, trim to window
        combined = pd.concat([df_existing, new_candles], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        if len(combined) > ROLLING_WINDOW:
            combined = combined.iloc[-ROLLING_WINDOW:]

        path = save_dataset_csv(combined, symbol, timeframe)
        db.upsert_dataset_registry({
            "symbol": symbol, "timeframe": timeframe,
            "candle_count": len(combined),
            "rolling_window_size": ROLLING_WINDOW,
            "last_candle_timestamp": str(combined["timestamp"].iloc[-1]),
            "blob_path": path, "status": "ready"
        })
        added = len(new_candles)
        logger.info(f"  → +{added} candles, total={len(combined)}")
        return {"action": "updated", "added": added, "total": len(combined)}
    else:
        path = save_dataset_csv(df_new, symbol, timeframe)
        db.upsert_dataset_registry({
            "symbol": symbol, "timeframe": timeframe,
            "candle_count": len(df_new),
            "rolling_window_size": ROLLING_WINDOW,
            "last_candle_timestamp": str(df_new["timestamp"].iloc[-1]),
            "blob_path": path, "status": "ready"
        })
        return {"action": "generated", "candles": len(df_new)}


def run_prediction(db: DatabaseAdapter, symbol: str, timeframe: str) -> dict:
    """Run the prediction pipeline for a symbol+timeframe."""
    try:
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
        pipeline = ForexIntegratedPipeline()
        result = pipeline.predict(symbol=symbol, timeframe=timeframe)
        if result is None:
            return {"action": "skip", "reason": "pipeline_returned_none"}

        pred = {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": getattr(result, "signal", getattr(result, "direction", "hold")),
            "confidence": float(getattr(result, "confidence", getattr(result, "signal_strength", 50)) / 100.0),
            "entry_price": float(getattr(result, "entry_price", 0)),
            "stop_loss": float(getattr(result, "stop_loss", 0)),
            "take_profit": float(getattr(result, "take_profit", 0)),
            "features_snapshot": getattr(result, "features", {}),
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
            if not existing or existing[0].get("status") != "ready":
                logger.info(f"NEW SYMBOL DETECTED: {code} {tf} — generating...")
                try:
                    df = fetch_yfinance(code, tf, ROLLING_WINDOW)
                    path = save_dataset_csv(df, code, tf)
                    db.upsert_dataset_registry({
                        "symbol": code, "timeframe": tf,
                        "candle_count": len(df),
                        "rolling_window_size": ROLLING_WINDOW,
                        "last_candle_timestamp": str(df["timestamp"].iloc[-1]),
                        "blob_path": path, "status": "ready"
                    })
                    generated.append({"symbol": code, "timeframe": tf, "candles": len(df)})
                except Exception as e:
                    logger.error(f"  → failed: {e}")
    return generated


def run_cycle(db: DatabaseAdapter, timeframe: str):
    """Execute one full scheduler cycle for a given timeframe."""
    run = db.create_scheduler_run({
        "timeframe": timeframe,
        "started_at": datetime.now().isoformat(),
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
        symbols = db.get_supported_symbols()  # refresh

    # 2. Rolling update + prediction for each symbol
    for sym in symbols:
        code = sym["symbol_code"]
        symbols_processed += 1

        update_result = run_rolling_update(db, code, timeframe)
        results.append({"symbol": code, "update": update_result})

        if update_result.get("action") in ("updated", "generated"):
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
        results = run_init(db)
        print(json.dumps({"ok": True, "init": results}, indent=2, default=str))
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


if __name__ == "__main__":
    main()
