"""Causal, temporary-state historical replay for the production-intended shadow path."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from forex.data.mt5_provider import MT5Provider
from forex.data.rolling_dataset import ROLLING_WINDOW, RollingDataset, normalize_dataset
from forex.data.symbol_catalog import get_symbol_spec, route_for_provider
from forex.prediction.shadow_runtime import (
    SHADOW_EXECUTION_MODE,
    SHADOW_HORIZON,
    SHADOW_MODEL_CONTRACT,
    ShadowForexRuntime,
    ShadowModelStorage,
    ShadowRuntimeConfig,
    mature_shadow_outcomes,
    shadow_retrain_due,
)
from infra.db.database import SQLiteDatabase


REPLAY_EXECUTION_MODE = "shadow_replay"
EVENT_PRIORITY = {"D1": 0, "H4": 1, "H1": 2}
SOURCE_COUNTS = {"H1": 3600, "H4": 2400, "D1": 2100}
_DURATION = {
    "H1": pd.Timedelta(hours=1),
    "H4": pd.Timedelta(hours=4),
    "D1": pd.Timedelta(days=1),
}


class ReplayLookaheadError(ValueError):
    pass


class ReplayDuplicateError(ValueError):
    pass


def _utc(value: Any) -> pd.Timestamp:
    moment = pd.Timestamp(value)
    if pd.isna(moment):
        raise ValueError("REPLAY_TIMESTAMP_INVALID")
    return moment.tz_localize("UTC") if moment.tzinfo is None else moment.tz_convert("UTC")


def candle_available_at(timestamp: Any, timeframe: str) -> pd.Timestamp:
    timeframe = str(timeframe).upper()
    if timeframe not in _DURATION:
        raise ValueError(f"REPLAY_TIMEFRAME_UNSUPPORTED: {timeframe}")
    return _utc(timestamp) + _DURATION[timeframe]


def _timestamps(frame: pd.DataFrame) -> pd.Series:
    parsed = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if parsed.isna().any():
        raise ValueError("REPLAY_SOURCE_TIMESTAMP_INVALID")
    return parsed


def visible_source(frame: pd.DataFrame, timeframe: str, replay_clock: Any) -> pd.DataFrame:
    clock = _utc(replay_clock)
    available = _timestamps(frame) + _DURATION[str(timeframe).upper()]
    return frame.loc[available <= clock].copy().reset_index(drop=True)


def initial_rolling_cut(frame: pd.DataFrame, timeframe: str, replay_start: Any) -> pd.DataFrame:
    visible = visible_source(frame, timeframe, replay_start)
    if len(visible) < ROLLING_WINDOW:
        raise ValueError(
            f"REPLAY_INITIAL_HISTORY_INSUFFICIENT: {timeframe} "
            f"has {len(visible)}; expected {ROLLING_WINDOW}"
        )
    return visible.tail(ROLLING_WINDOW).reset_index(drop=True)


@dataclass(frozen=True)
class ReplayEvent:
    available_at: pd.Timestamp
    symbol: str
    timeframe: str
    row_position: int


def build_event_queue(
    sources: Mapping[tuple[str, str], pd.DataFrame],
    start: Any,
    end: Any,
) -> list[ReplayEvent]:
    lower, upper = _utc(start), _utc(end)
    events: list[ReplayEvent] = []
    for (symbol, timeframe), frame in sources.items():
        code = str(symbol).upper()
        tf = str(timeframe).upper()
        available = _timestamps(frame) + _DURATION[tf]
        for position in np.flatnonzero(((available >= lower) & (available < upper)).to_numpy()):
            events.append(ReplayEvent(available.iloc[position], code, tf, int(position)))
    return sorted(
        events,
        key=lambda event: (
            event.available_at,
            EVENT_PRIORITY[event.timeframe],
            event.symbol,
        ),
    )


def source_sha256(frame: pd.DataFrame) -> str:
    return hashlib.sha256(_source_bytes(frame)).hexdigest()


def _source_bytes(frame: pd.DataFrame) -> bytes:
    frozen = frame.copy()
    frozen["timestamp"] = _timestamps(frozen).dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return frozen.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")


def assert_symbol_isolation(frame: pd.DataFrame, symbol: str) -> None:
    observed = {
        "".join(character for character in str(value).upper() if character.isalnum())
        for value in frame["pair"].dropna().unique()
    }
    if observed != {str(symbol).upper()}:
        raise ValueError(
            f"REPLAY_CROSS_SYMBOL_DATA: expected={symbol} observed={sorted(observed)}"
        )


def assert_training_causal(
    *,
    max_feature_timestamp: Any,
    max_target_timestamp: Any,
    replay_clock: Any,
) -> dict:
    clock = _utc(replay_clock)
    feature = _utc(max_feature_timestamp)
    target = _utc(max_target_timestamp)
    if feature > clock or target > clock:
        raise ReplayLookaheadError(
            f"FOREX HISTORICAL REPLAY FAILED — TRAINING_LOOKAHEAD: "
            f"feature={feature.isoformat()} target={target.isoformat()} "
            f"clock={clock.isoformat()}"
        )
    return {
        "lookahead_violation": False,
        "max_feature_timestamp": feature.isoformat(),
        "max_target_timestamp": target.isoformat(),
        "replay_clock": clock.isoformat(),
    }


def replay_prediction_id(symbol: str, candle: Any, generation: int) -> str:
    identity = "|".join((
        str(symbol).upper(),
        "H1",
        _utc(candle).isoformat(),
        SHADOW_MODEL_CONTRACT,
        str(int(generation)),
    ))
    return "shadow_pred_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def retrain_due(training_cutoff: Any, h1_timestamps, cadence: int = 168) -> bool:
    return shadow_retrain_due(training_cutoff, h1_timestamps, cadence)


@dataclass
class ReplayPredictionBook:
    predictions: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    duplicate_attempts: int = 0

    def record(self, prediction: dict) -> bool:
        key = (
            str(prediction["symbol"]).upper(),
            _utc(prediction["candle_timestamp"]).isoformat(),
            int(prediction["model_generation"]),
        )
        existing = {
            (
                str(row["symbol"]).upper(),
                _utc(row["candle_timestamp"]).isoformat(),
                int(row["model_generation"]),
            )
            for row in self.predictions
        }
        if key in existing:
            self.duplicate_attempts += 1
            raise ReplayDuplicateError(f"REPLAY_DUPLICATE_PREDICTION: {key}")
        self.predictions.append(dict(prediction))
        return True

    def mature(
        self, symbol: str, candles: pd.DataFrame, replay_clock: Any
    ) -> list[dict]:
        code = str(symbol).upper()
        frame = candles.loc[:, ["timestamp", "close"]].copy()
        frame["timestamp"] = _timestamps(frame)
        frame = frame.loc[
            frame["timestamp"] + pd.Timedelta(hours=1) <= _utc(replay_clock)
        ].sort_values("timestamp")
        existing = {row["prediction_id"] for row in self.outcomes}
        finalized: list[dict] = []
        for prediction in self.predictions:
            if (
                str(prediction["symbol"]).upper() != code
                or prediction.get("action") not in ("BUY", "SELL")
            ):
                continue
            prediction_id = prediction.get("prediction_id") or replay_prediction_id(
                code, prediction["candle_timestamp"], prediction["model_generation"]
            )
            if prediction_id in existing:
                continue
            entry = _utc(prediction["candle_timestamp"])
            future = frame.loc[frame["timestamp"] > entry].head(SHADOW_HORIZON)
            if len(future) < SHADOW_HORIZON:
                continue
            terminal = future.iloc[-1]
            entry_price = float(prediction["entry_price"])
            future_close = float(terminal["close"])
            action = prediction["action"]
            outcome = {
                "prediction_id": prediction_id,
                "symbol": code,
                "action": action,
                "entry_candle": entry.isoformat(),
                "evaluation_candle": _utc(terminal["timestamp"]).isoformat(),
                "entry_price": entry_price,
                "future_close": future_close,
                "future_return": (future_close - entry_price) / entry_price,
                "direction_correct": (
                    future_close > entry_price if action == "BUY" else future_close <= entry_price
                ),
                "model_identity": prediction.get("model_identity"),
                "model_generation": int(prediction["model_generation"]),
                "execution_mode": REPLAY_EXECUTION_MODE,
            }
            self.outcomes.append(outcome)
            existing.add(prediction_id)
            finalized.append(outcome)
        return finalized


def descriptive_metrics(predictions: Sequence[dict], outcomes: Sequence[dict]) -> dict:
    predictions = list(predictions)
    outcomes = list(outcomes)
    buy = [row for row in predictions if row.get("action") == "BUY"]
    sell = [row for row in predictions if row.get("action") == "SELL"]
    hold = [row for row in predictions if row.get("action") == "HOLD"]
    buy_outcomes = [row for row in outcomes if row.get("action") == "BUY"]
    sell_outcomes = [row for row in outcomes if row.get("action") == "SELL"]
    directional = buy_outcomes + sell_outcomes

    def accuracy(rows: Sequence[dict]) -> float:
        return sum(bool(row.get("direction_correct")) for row in rows) / len(rows) if rows else 0.0

    def mean_return(rows: Sequence[dict]) -> float:
        return float(np.mean([float(row["future_return"]) for row in rows])) if rows else 0.0

    def median_return(rows: Sequence[dict]) -> float:
        return float(np.median([float(row["future_return"]) for row in rows])) if rows else 0.0

    pooled = accuracy(directional)
    correct = sum(bool(row.get("direction_correct")) for row in directional)
    generations: dict[str, dict] = {}
    for generation in sorted({int(row["model_generation"]) for row in predictions}):
        gp = [row for row in predictions if int(row["model_generation"]) == generation]
        go = [row for row in outcomes if int(row["model_generation"]) == generation]
        generations[str(generation)] = {
            "prediction_count": len(gp),
            "buy_count": sum(row.get("action") == "BUY" for row in gp),
            "sell_count": sum(row.get("action") == "SELL" for row in gp),
            "hold_count": sum(row.get("action") == "HOLD" for row in gp),
            "matured_directional": len(go),
            "directional_accuracy": accuracy(go),
        }
    actual_up = sum(float(row["future_return"]) > 0.0 for row in directional)
    actual_down = len(directional) - actual_up
    naive = max(actual_up, actual_down) / len(directional) if directional else 0.0
    return {
        "total_predictions": len(predictions),
        "buy_count": len(buy),
        "sell_count": len(sell),
        "hold_count": len(hold),
        "directional_predictions": len(buy) + len(sell),
        "coverage": (len(buy) + len(sell)) / len(predictions) if predictions else 0.0,
        "matured_directional_outcomes": len(directional),
        "correct_directional_outcomes": correct,
        "incorrect_directional_outcomes": len(directional) - correct,
        "pooled_directional_accuracy": pooled,
        "buy_precision": accuracy(buy_outcomes),
        "sell_precision": accuracy(sell_outcomes),
        "average_future_return_after_buy": mean_return(buy_outcomes),
        "average_future_return_after_sell": mean_return(sell_outcomes),
        "median_future_return_after_buy": median_return(buy_outcomes),
        "median_future_return_after_sell": median_return(sell_outcomes),
        "naive_majority_direction_accuracy": naive,
        "reference_accuracy": 0.5,
        "predictive_sanity_label": (
            "ABOVE_50_REFERENCE" if pooled > 0.5 else "AT_OR_BELOW_50_REFERENCE"
        ),
        "by_generation": generations,
    }


def snapshot_paths(paths: Sequence[Path | str]) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    for raw in paths:
        path = Path(raw).resolve()
        snapshots[str(path)] = {
            "exists": path.is_file(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            "size": path.stat().st_size if path.is_file() else None,
        }
    return snapshots


def verify_snapshots(snapshots: Mapping[str, dict]) -> list[str]:
    changed: list[str] = []
    for raw, expected in snapshots.items():
        path = Path(raw)
        actual = {
            "exists": path.is_file(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            "size": path.stat().st_size if path.is_file() else None,
        }
        if actual != expected:
            changed.append(str(path.resolve()))
    return changed


@dataclass(frozen=True)
class HistoricalReplayConfig:
    start: Any
    end: Any
    symbols: tuple[str, ...]
    root: Path
    replay_session_id: str = "forex-replay-jul-aug-2026"
    retrain_candles: int = 168

    def __post_init__(self):
        object.__setattr__(self, "start", _utc(self.start))
        object.__setattr__(self, "end", _utc(self.end))
        object.__setattr__(self, "symbols", tuple(str(value).upper() for value in self.symbols))
        object.__setattr__(self, "root", Path(self.root).resolve())
        if self.start >= self.end or set(self.symbols) - {"EURUSD", "USDJPY"}:
            raise ValueError("REPLAY_CONFIGURATION_INVALID")

    @property
    def database_path(self) -> Path:
        return self.root / "state" / "replay.sqlite"

    @property
    def model_root(self) -> Path:
        return self.root / "models" / "forex" / "shadow"

    @property
    def dataset_root(self) -> Path:
        return self.root / "datasets"


def capture_mt5_sources(
    symbols: Sequence[str],
    *,
    counts: Mapping[str, int] = SOURCE_COUNTS,
) -> tuple[dict[tuple[str, str], pd.DataFrame], dict[tuple[str, str], dict]]:
    sources: dict[tuple[str, str], pd.DataFrame] = {}
    metadata: dict[tuple[str, str], dict] = {}
    for symbol in symbols:
        for timeframe in ("H1", "H4", "D1"):
            provider = MT5Provider()
            frame = provider.fetch(str(symbol).upper(), timeframe, int(counts[timeframe]))
            normalized = normalize_dataset(frame, str(symbol).upper())
            if len(normalized) != int(counts[timeframe]):
                raise ValueError(
                    f"REPLAY_SOURCE_ROWS_INVALID: {symbol}/{timeframe} "
                    f"{len(normalized)} != {counts[timeframe]}"
                )
            assert_symbol_isolation(normalized, str(symbol).upper())
            source_metadata = dict(provider.last_acquisition_metadata or {})
            if (
                source_metadata.get("provider") != "MT5"
                or source_metadata.get("server") != "IFCMarkets-Demo"
                or source_metadata.get("symbol") != str(symbol).upper()
                or source_metadata.get("timeframe") != timeframe
            ):
                raise ValueError(f"REPLAY_SOURCE_PROVENANCE_INVALID: {symbol}/{timeframe}")
            key = (str(symbol).upper(), timeframe)
            sources[key] = normalized.reset_index(drop=True)
            source_metadata["replay_captured_rows"] = len(normalized)
            metadata[key] = source_metadata
    return sources, metadata


def bound_sources_for_replay(
    sources: Mapping[tuple[str, str], pd.DataFrame], end: Any
) -> dict[tuple[str, str], pd.DataFrame]:
    """Retain no post-window rows except 12 H1 candles for outcome maturity."""
    upper = _utc(end)
    bounded: dict[tuple[str, str], pd.DataFrame] = {}
    for key, frame in sources.items():
        timeframe = key[1]
        available = _timestamps(frame) + _DURATION[timeframe]
        within = frame.loc[available < upper]
        if timeframe == "H1":
            post = frame.loc[available >= upper].head(SHADOW_HORIZON)
            within = pd.concat([within, post], ignore_index=True)
        bounded[key] = within.reset_index(drop=True)
    return bounded


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HistoricalReplay:
    def __init__(
        self,
        config: HistoricalReplayConfig,
        sources: Mapping[tuple[str, str], pd.DataFrame],
        source_metadata: Mapping[tuple[str, str], dict],
    ):
        self.config = config
        self.sources = {
            (symbol.upper(), timeframe.upper()): normalize_dataset(frame, symbol)
            for (symbol, timeframe), frame in sources.items()
        }
        self.source_metadata = {
            (symbol.upper(), timeframe.upper()): dict(value)
            for (symbol, timeframe), value in source_metadata.items()
        }
        required = {
            (symbol, timeframe)
            for symbol in config.symbols
            for timeframe in ("H1", "H4", "D1")
        }
        if set(self.sources) != required or set(self.source_metadata) != required:
            raise ValueError("REPLAY_SOURCE_SET_INVALID")
        for (symbol, _), frame in self.sources.items():
            assert_symbol_isolation(frame, symbol)
        config.root.mkdir(parents=True, exist_ok=True)
        config.database_path.parent.mkdir(parents=True, exist_ok=True)
        config.dataset_root.mkdir(parents=True, exist_ok=True)
        source_root = config.root / "sources"
        source_root.mkdir(parents=True, exist_ok=True)
        for (symbol, timeframe), frame in self.sources.items():
            source_path = source_root / f"{symbol}_{timeframe}.csv"
            source_path.write_bytes(_source_bytes(frame))
            source_path.chmod(0o444)
        self.database = SQLiteDatabase(str(config.database_path))
        runtime_config = ShadowRuntimeConfig.from_environment({
            "ASTRA_FOREX_SHADOW_MODE": "1",
            "ASTRA_FOREX_SHADOW_SYMBOLS": ",".join(config.symbols),
            "ASTRA_FOREX_RUNTIME_SYMBOLS": ",".join(config.symbols),
            "ASTRA_FOREX_RUNTIME_PROVIDER": "MT5",
            "ASTRA_SHADOW_RETRAIN_CANDLES": str(config.retrain_candles),
        })
        self.runtime = ShadowForexRuntime(
            self.database,
            project_root=config.root,
            config=runtime_config,
            storage=ShadowModelStorage(config.model_root),
        )
        self.datasets: dict[tuple[str, str], RollingDataset] = {}
        self.revealed_h1: dict[str, pd.DataFrame] = {}
        self.generations: dict[str, list[dict]] = {symbol: [] for symbol in config.symbols}
        self.event_counts = {
            symbol: {timeframe: 0 for timeframe in ("H1", "H4", "D1")}
            for symbol in config.symbols
        }
        self.duplicate_attempts = 0
        self.lookahead_violations = 0
        self.post_window_candles = 0

    def _qualify_temp_symbol(self, symbol: str) -> None:
        spec = get_symbol_spec(symbol)
        self.database.register_candidate(
            spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
        )
        with self.database._writable_connection() as connection:
            connection.execute(
                "UPDATE supported_symbols SET status='qualified', qualified_at=?, "
                "updated_at=? WHERE symbol_code=?",
                (self.config.start.isoformat(), self.config.start.isoformat(), symbol),
            )

    def _dataset_path(self, symbol: str, timeframe: str) -> Path:
        return self.config.dataset_root / f"{symbol}_{timeframe}.csv"

    def _upsert_registry(self, symbol: str, timeframe: str, clock: Any) -> dict:
        dataset = self.datasets[(symbol, timeframe)]
        frame = dataset.get_df()
        if frame is None:
            dataset.load()
            frame = dataset.get_df()
        path = dataset.csv_path
        digest = _file_sha256(path)
        metadata = dict(self.source_metadata[(symbol, timeframe)])
        metadata.update({
            "dataset_sha256": digest,
            "replay_session_id": self.config.replay_session_id,
            "replay_source_sha256": source_sha256(self.sources[(symbol, timeframe)]),
            "visible_cutoff": _utc(clock).isoformat(),
        })
        route = route_for_provider(symbol, "MT5")
        return self.database.upsert_dataset_registry({
            "symbol": symbol,
            "timeframe": timeframe,
            "candle_count": len(frame),
            "rolling_window_size": ROLLING_WINDOW,
            "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
            "blob_path": str(path.resolve()),
            "status": "ready" if len(frame) == ROLLING_WINDOW else "pending",
            "provider_used": "MT5",
            "external_ticker": route.external_ticker,
            "provider_class": route.provider_class,
            "source_fetched_at": _utc(clock).isoformat(),
            "source_sha256": digest,
            "acquisition_metadata": metadata,
        })

    def _record_training(self, symbol: str, result: dict, clock: Any) -> None:
        if result.get("action") != "trained":
            return
        try:
            causal = assert_training_causal(
                max_feature_timestamp=result["max_training_feature_timestamp"],
                max_target_timestamp=result["max_training_target_timestamp"],
                replay_clock=clock,
            )
        except ReplayLookaheadError:
            self.lookahead_violations += 1
            raise
        self.generations[symbol].append({
            "generation": int(result["model_generation"]),
            "training_cutoff": result["training_last_candle"],
            "training_clock": _utc(clock).isoformat(),
            "artifact_sha256": result["artifact_sha256"],
            "model_identity": result["model_identity"],
            "training_rows": int(result["training_rows"]),
            **causal,
        })

    def prepare(self) -> None:
        for symbol in self.config.symbols:
            self._qualify_temp_symbol(symbol)
            for timeframe in ("H1", "H4", "D1"):
                initial = initial_rolling_cut(
                    self.sources[(symbol, timeframe)], timeframe, self.config.start
                )
                dataset = RollingDataset(
                    symbol,
                    timeframe,
                    max_rows=ROLLING_WINDOW,
                    csv_path=self._dataset_path(symbol, timeframe),
                )
                dataset.apply(initial, include_existing=False, now=self.config.start)
                self.datasets[(symbol, timeframe)] = dataset
                registry = self._upsert_registry(symbol, timeframe, self.config.start)
                if registry.get("status") != "ready" or registry.get("candle_count") != 2000:
                    raise ValueError(f"REPLAY_INITIAL_DATASET_NOT_READY: {symbol}/{timeframe}")
            self.revealed_h1[symbol] = initial_rolling_cut(
                self.sources[(symbol, "H1")], "H1", self.config.start
            )
            trained = self.runtime.train(symbol, available_at=self.config.start)
            self._record_training(symbol, trained, self.config.start)

    def _reveal(self, event: ReplayEvent) -> None:
        key = (event.symbol, event.timeframe)
        row = self.sources[key].iloc[[event.row_position]].copy()
        if candle_available_at(row["timestamp"].iloc[0], event.timeframe) > event.available_at:
            raise ReplayLookaheadError("REPLAY_REVEAL_LOOKAHEAD")
        self.datasets[key].update_frame(row, now=event.available_at)
        self._upsert_registry(event.symbol, event.timeframe, event.available_at)
        self.event_counts[event.symbol][event.timeframe] += 1
        if event.timeframe == "H1":
            visible = pd.concat([self.revealed_h1[event.symbol], row], ignore_index=True)
            visible = visible.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
            self.revealed_h1[event.symbol] = visible.reset_index(drop=True)

    def _pending_directional(self) -> list[dict]:
        return [
            row
            for symbol in self.config.symbols
            for row in self.database.get_predictions(symbol, "H1", limit=100000)
            if row.get("execution_mode") == REPLAY_EXECUTION_MODE
            and row.get("action") in ("BUY", "SELL")
            and row.get("status") == "PENDING"
        ]

    def _process_h1(self, symbol: str, clock: Any) -> None:
        mature_shadow_outcomes(
            self.database,
            symbol,
            self.revealed_h1[symbol],
            available_at=clock,
            execution_mode=REPLAY_EXECUTION_MODE,
        )
        trained = self.runtime.train(symbol, available_at=clock)
        self._record_training(symbol, trained, clock)
        current = self.runtime.storage.load(symbol)["metadata"]
        h1 = self.datasets[(symbol, "H1")].get_df()
        candle = _utc(h1["timestamp"].iloc[-1])
        prediction_id = replay_prediction_id(symbol, candle, current["model_generation"])
        if self.database.get_prediction(prediction_id) is not None:
            self.duplicate_attempts += 1
            raise ReplayDuplicateError(f"REPLAY_DUPLICATE_PREDICTION: {prediction_id}")
        result = self.runtime.run_shadow_prediction(
            symbol,
            execution_mode=REPLAY_EXECUTION_MODE,
            predicted_at=clock,
        )
        stored = result["prediction"]
        # Runtime IDs use the same symbol/candle/generation uniqueness.  The
        # explicit replay ID check above guards re-entry without changing live IDs.
        if stored.get("execution_mode") != REPLAY_EXECUTION_MODE:
            raise ValueError("REPLAY_PREDICTION_MODE_INVALID")

    def _mature_post_window(self) -> None:
        post_events: list[ReplayEvent] = []
        for symbol in self.config.symbols:
            frame = self.sources[(symbol, "H1")]
            available = _timestamps(frame) + _DURATION["H1"]
            for position in np.flatnonzero((available >= self.config.end).to_numpy()):
                post_events.append(ReplayEvent(available.iloc[position], symbol, "H1", int(position)))
        post_events.sort(key=lambda event: (event.available_at, event.symbol))
        for event in post_events:
            if not self._pending_directional():
                break
            row = self.sources[(event.symbol, "H1")].iloc[[event.row_position]].copy()
            current_timestamps = set(
                pd.to_datetime(self.revealed_h1[event.symbol]["timestamp"], utc=True)
            )
            row_timestamp = _utc(row["timestamp"].iloc[0])
            if row_timestamp in current_timestamps:
                continue
            self.revealed_h1[event.symbol] = pd.concat(
                [self.revealed_h1[event.symbol], row], ignore_index=True
            ).sort_values("timestamp").reset_index(drop=True)
            self.post_window_candles += 1
            mature_shadow_outcomes(
                self.database,
                event.symbol,
                self.revealed_h1[event.symbol],
                available_at=event.available_at,
                execution_mode=REPLAY_EXECUTION_MODE,
            )

    def run(self) -> dict:
        self.prepare()
        queue = build_event_queue(self.sources, self.config.start, self.config.end)
        for event in queue:
            self._reveal(event)
            if event.timeframe == "H1":
                self._process_h1(event.symbol, event.available_at)
        prediction_count_before_maturity = sum(
            len([
                row for row in self.database.get_predictions(symbol, "H1", limit=100000)
                if row.get("execution_mode") == REPLAY_EXECUTION_MODE
            ])
            for symbol in self.config.symbols
        )
        self._mature_post_window()
        prediction_count_after_maturity = sum(
            len([
                row for row in self.database.get_predictions(symbol, "H1", limit=100000)
                if row.get("execution_mode") == REPLAY_EXECUTION_MODE
            ])
            for symbol in self.config.symbols
        )
        if prediction_count_before_maturity != prediction_count_after_maturity:
            raise ValueError("REPLAY_POST_WINDOW_PREDICTION_CREATED")

        symbols: dict[str, dict] = {}
        for symbol in self.config.symbols:
            predictions = [
                row for row in reversed(self.database.get_predictions(symbol, "H1", limit=100000))
                if row.get("execution_mode") == REPLAY_EXECUTION_MODE
            ]
            outcomes = self.database.get_shadow_outcomes(
                symbol, execution_mode=REPLAY_EXECUTION_MODE
            )
            symbols[symbol] = {
                "source": {
                    timeframe: {
                        "captured_rows": int(
                            self.source_metadata[(symbol, timeframe)].get(
                                "replay_captured_rows", len(self.sources[(symbol, timeframe)])
                            )
                        ),
                        "frozen_rows": len(self.sources[(symbol, timeframe)]),
                        "sha256": source_sha256(self.sources[(symbol, timeframe)]),
                        "first_timestamp": _utc(self.sources[(symbol, timeframe)]["timestamp"].iloc[0]).isoformat(),
                        "last_timestamp": _utc(self.sources[(symbol, timeframe)]["timestamp"].iloc[-1]).isoformat(),
                    }
                    for timeframe in ("H1", "H4", "D1")
                },
                "events": self.event_counts[symbol],
                "predictions_generated": len(predictions),
                "generations": self.generations[symbol],
                "retrain_count": max(0, len(self.generations[symbol]) - 1),
                "pending_directional": sum(
                    row.get("action") in ("BUY", "SELL") and row.get("status") == "PENDING"
                    for row in predictions
                ),
                "metrics": descriptive_metrics(predictions, outcomes),
            }
        return {
            "replay_session_id": self.config.replay_session_id,
            "start": self.config.start.isoformat(),
            "end": self.config.end.isoformat(),
            "source_provider": "MT5",
            "source_fallback_used": False,
            "initial_rolling_datasets_all_2000": True,
            "lookahead_violations": self.lookahead_violations,
            "duplicate_predictions": self.duplicate_attempts,
            "post_window_candles_used_only_for_maturity": self.post_window_candles,
            "symbols": symbols,
        }


__all__ = [
    "EVENT_PRIORITY",
    "HistoricalReplay",
    "HistoricalReplayConfig",
    "REPLAY_EXECUTION_MODE",
    "ReplayDuplicateError",
    "ReplayEvent",
    "ReplayLookaheadError",
    "ReplayPredictionBook",
    "SOURCE_COUNTS",
    "assert_symbol_isolation",
    "assert_training_causal",
    "build_event_queue",
    "bound_sources_for_replay",
    "candle_available_at",
    "capture_mt5_sources",
    "descriptive_metrics",
    "initial_rolling_cut",
    "replay_prediction_id",
    "retrain_due",
    "snapshot_paths",
    "source_sha256",
    "verify_snapshots",
    "visible_source",
]
