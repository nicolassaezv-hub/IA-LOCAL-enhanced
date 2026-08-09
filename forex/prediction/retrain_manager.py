"""
V.13 — Reentrenamiento Adaptativo
=================================
Monitor de degradacion del modelo. Dispara el reentrenamiento solo cuando
hay evidencia real de que el modelo actual ya no es optimo.

Triggers:
  - Win rate cae > 10% vs. historico
  - Cambio de regimen de mercado (V.4)
  - N filas nuevas acumuladas (umbral configurable)
  - Reentrenamiento programado (semanal/mensual)
  - Solicitud manual del usuario

Integracion:
    from forex.prediction.retrain_manager import RetrainManager
    mgr = RetrainManager()
    needed, reason = mgr.check_retrain_needed(pair="EURUSD", current_win_rate=0.45)
    if needed:
        mgr.trigger_retrain(pair="EURUSD")
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

try:
    from colorama import Fore, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

if HAS_COLOR:
    _C = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _B = lambda s: f"{Fore.BLUE}{s}{Style.RESET_ALL}"
else:
    _C = _G = _Y = _R = _B = lambda s: s


class RetrainTrigger(str, Enum):
    WIN_RATE_DROP = "win_rate_drop"
    REGIME_CHANGE = "regime_change"
    NEW_DATA_THRESHOLD = "new_data_threshold"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    ACCURACY_DROP = "accuracy_drop"
    NONE = "none"


@dataclass
class RetrainDecision:
    needed: bool = False
    trigger: RetrainTrigger = RetrainTrigger.NONE
    reason: str = ""
    details: dict = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "needed": self.needed,
            "trigger": self.trigger.value,
            "reason": self.reason,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class RetrainRecord:
    pair: str = ""
    timeframe: str = ""
    trigger: str = ""
    old_model: str = ""
    new_model: str = ""
    old_win_rate: float = 0.0
    new_win_rate: float = 0.0
    old_accuracy: float = 0.0
    new_accuracy: float = 0.0
    duration_sec: float = 0.0
    success: bool = False
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


DEFAULT_CONFIG = {
    "win_rate_drop_threshold": 0.10,
    "accuracy_drop_threshold": 0.05,
    "new_data_threshold": 500,
    "scheduled_interval_days": 7,
    "min_predictions_for_eval": 20,
}


class RetrainManager:
    """Monitor de degradacion y disparador de reentrenamiento."""

    def __init__(self, db_path: str = "memoria.db", config: dict | None = None):
        self.db_path = db_path
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retrain_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    timeframe TEXT,
                    trigger TEXT,
                    old_model TEXT,
                    new_model TEXT,
                    old_win_rate REAL,
                    new_win_rate REAL,
                    old_accuracy REAL,
                    new_accuracy REAL,
                    duration_sec REAL,
                    success INTEGER,
                    error TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_baseline (
                    pair TEXT,
                    timeframe TEXT,
                    model_name TEXT,
                    win_rate REAL,
                    accuracy REAL,
                    timestamp TEXT,
                    PRIMARY KEY (pair, timeframe, model_name)
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Store model baseline ──
    def store_baseline(
        self,
        pair: str,
        timeframe: str,
        model_name: str,
        win_rate: float,
        accuracy: float,
    ):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO model_baseline
                (pair, timeframe, model_name, win_rate, accuracy, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pair, timeframe, model_name, win_rate, accuracy, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Get baseline ──
    def get_baseline(self, pair: str, timeframe: str, model_name: str = "") -> dict | None:
        try:
            conn = sqlite3.connect(self.db_path)
            if model_name:
                row = conn.execute(
                    "SELECT * FROM model_baseline WHERE pair=? AND timeframe=? AND model_name=?",
                    (pair, timeframe, model_name),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM model_baseline WHERE pair=? AND timeframe=? ORDER BY timestamp DESC LIMIT 1",
                    (pair, timeframe),
                ).fetchone()
            conn.close()
            if row:
                return {
                    "pair": row[0],
                    "timeframe": row[1],
                    "model_name": row[2],
                    "win_rate": row[3],
                    "accuracy": row[4],
                    "timestamp": row[5],
                }
        except Exception:
            pass
        return None

    # ── Check if retrain needed ──
    def check_retrain_needed(
        self,
        pair: str = "",
        timeframe: str = "",
        current_win_rate: float | None = None,
        current_accuracy: float | None = None,
        model_name: str = "",
        new_rows_count: int = 0,
        last_regime: str = "",
        current_regime: str = "",
        last_retrain_date: datetime | None = None,
        prediction_count: int = 0,
    ) -> RetrainDecision:
        decision = RetrainDecision(timestamp=datetime.utcnow().isoformat())
        details: dict = {}

        baseline = self.get_baseline(pair, timeframe, model_name)
        if baseline:
            details["baseline_win_rate"] = baseline["win_rate"]
            details["baseline_accuracy"] = baseline["accuracy"]
            details["baseline_model"] = baseline["model_name"]

        # Trigger 1: Win rate drop
        if current_win_rate is not None and baseline:
            drop = baseline["win_rate"] - current_win_rate
            details["win_rate_drop"] = round(drop, 4)
            if drop >= self.config["win_rate_drop_threshold"] and prediction_count >= self.config["min_predictions_for_eval"]:
                decision.needed = True
                decision.trigger = RetrainTrigger.WIN_RATE_DROP
                decision.reason = f"Win rate cayo {drop:.1%} (baseline={baseline['win_rate']:.1%}, actual={current_win_rate:.1%})"
                decision.details = details
                return decision

        # Trigger 2: Accuracy drop
        if current_accuracy is not None and baseline:
            drop = baseline["accuracy"] - current_accuracy
            details["accuracy_drop"] = round(drop, 4)
            if drop >= self.config["accuracy_drop_threshold"]:
                decision.needed = True
                decision.trigger = RetrainTrigger.ACCURACY_DROP
                decision.reason = f"Accuracy cayo {drop:.1%} (baseline={baseline['accuracy']:.1%}, actual={current_accuracy:.1%})"
                decision.details = details
                return decision

        # Trigger 3: Regime change
        if last_regime and current_regime and last_regime != current_regime:
            decision.needed = True
            decision.trigger = RetrainTrigger.REGIME_CHANGE
            decision.reason = f"Regimen cambio de '{last_regime}' a '{current_regime}'"
            decision.details = {**details, "last_regime": last_regime, "current_regime": current_regime}
            return decision

        # Trigger 4: New data threshold
        if new_rows_count >= self.config["new_data_threshold"]:
            decision.needed = True
            decision.trigger = RetrainTrigger.NEW_DATA_THRESHOLD
            decision.reason = f"Nuevas filas acumuladas: {new_rows_count} (umbral={self.config['new_data_threshold']})"
            decision.details = {**details, "new_rows": new_rows_count}
            return decision

        # Trigger 5: Scheduled
        if last_retrain_date:
            interval_days = self.config["scheduled_interval_days"]
            if datetime.utcnow() - last_retrain_date >= timedelta(days=interval_days):
                decision.needed = True
                decision.trigger = RetrainTrigger.SCHEDULED
                decision.reason = f"Reentrenamiento programado (ultima vez: {last_retrain_date.strftime('%Y-%m-%d')})"
                decision.details = {**details, "last_retrain": last_retrain_date.isoformat(), "interval_days": interval_days}
                return decision

        decision.details = details
        return decision

    # ── Trigger retrain ──
    def trigger_retrain(
        self,
        pair: str,
        timeframe: str = "H1",
        trigger: RetrainTrigger = RetrainTrigger.MANUAL,
        retrain_func: Callable | None = None,
        old_model: str = "",
        old_win_rate: float = 0.0,
        old_accuracy: float = 0.0,
    ) -> RetrainRecord:
        import time as _time
        start = _time.time()
        record = RetrainRecord(
            pair=pair,
            timeframe=timeframe,
            trigger=trigger.value,
            old_model=old_model,
            old_win_rate=old_win_rate,
            old_accuracy=old_accuracy,
            timestamp=datetime.utcnow().isoformat(),
        )

        if retrain_func is None:
            record.success = True
            record.new_model = old_model
            record.new_win_rate = old_win_rate
            record.new_accuracy = old_accuracy
            record.duration_sec = _time.time() - start
            record.error = "No retrain_func provided — logged only"
        else:
            try:
                result = retrain_func(pair, timeframe)
                record.success = True
                record.new_model = result.get("model_name", "unknown") if isinstance(result, dict) else "unknown"
                record.new_win_rate = result.get("win_rate", 0.0) if isinstance(result, dict) else 0.0
                record.new_accuracy = result.get("accuracy", 0.0) if isinstance(result, dict) else 0.0
                record.duration_sec = _time.time() - start
            except Exception as e:
                record.success = False
                record.error = str(e)
                record.duration_sec = _time.time() - start

        self._log_retrain(record)
        return record

    # ── Manual trigger ──
    def manual_retrain(
        self,
        pair: str,
        timeframe: str = "H1",
        retrain_func: Callable | None = None,
    ) -> RetrainRecord:
        return self.trigger_retrain(
            pair=pair,
            timeframe=timeframe,
            trigger=RetrainTrigger.MANUAL,
            retrain_func=retrain_func,
        )

    # ── Get history ──
    def get_history(self, pair: str = "", limit: int = 20) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            if pair:
                rows = conn.execute(
                    "SELECT * FROM retrain_history WHERE pair=? ORDER BY id DESC LIMIT ?",
                    (pair, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM retrain_history ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
            cols = ["id", "pair", "timeframe", "trigger", "old_model", "new_model",
                    "old_win_rate", "new_win_rate", "old_accuracy", "new_accuracy",
                    "duration_sec", "success", "error", "timestamp"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []

    # ── Log ──
    def _log_retrain(self, record: RetrainRecord):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO retrain_history
                (pair, timeframe, trigger, old_model, new_model,
                 old_win_rate, new_win_rate, old_accuracy, new_accuracy,
                 duration_sec, success, error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.pair, record.timeframe, record.trigger,
                record.old_model, record.new_model,
                record.old_win_rate, record.new_win_rate,
                record.old_accuracy, record.new_accuracy,
                record.duration_sec, int(record.success), record.error,
                record.timestamp,
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass


# ── CLI ──
def cmd_retrain_check(args: str = "") -> str:
    """Comando CLI: retrain_check <pair> [current_win_rate] [model_name]"""
    parts = args.strip().split()
    if not parts:
        return "Uso: retrain_check <pair> [current_win_rate] [model_name]"
    pair = parts[0].upper()
    win_rate = float(parts[1]) if len(parts) > 1 else None
    model_name = parts[2] if len(parts) > 2 else ""
    mgr = RetrainManager()
    decision = mgr.check_retrain_needed(pair=pair, current_win_rate=win_rate, model_name=model_name)
    if decision.needed:
        return f"{_Y('Reentrenamiento necesario')} — trigger={_C(decision.trigger.value)}\n  {decision.reason}"
    return f"{_G('No necesita reentrenamiento')} — {pair} esta dentro de parametros optimos"


def cmd_retrain_history(args: str = "") -> str:
    """Comando CLI: retrain_history [pair] [limit]"""
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    limit = int(parts[1]) if len(parts) > 1 else 20
    mgr = RetrainManager()
    history = mgr.get_history(pair=pair, limit=limit)
    if not history:
        return f"{_Y('Sin historial de reentrenamientos')}"
    lines = [f"{_C('Historial de Reentrenamientos')} ({len(history)} registros)"]
    for h in history:
        icon = _G("OK") if h["success"] else _R("FAIL")
        lines.append(
            f"  {icon} {h['timestamp'][:19]} | {h['pair']} {h['timeframe']} | "
            f"trigger={h['trigger']} | {h['old_model']} → {h['new_model']} | "
            f"WR: {h['old_win_rate']:.1%} → {h['new_win_rate']:.1%}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mgr = RetrainManager()
    mgr.store_baseline("EURUSD", "H1", "RF", 0.65, 0.70)
    d = mgr.check_retrain_needed(pair="EURUSD", current_win_rate=0.50, model_name="RF", prediction_count=25)
    print(f"Needed={d.needed}, Trigger={d.trigger.value}, Reason={d.reason}")
    print(cmd_retrain_check("EURUSD 0.50 RF"))
    print(cmd_retrain_history())
