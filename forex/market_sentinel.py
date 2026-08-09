"""
V.10 — Market Sentinel ⭐⭐⭐⭐⭐
================================
Daemon de vigilancia continua. Corre en segundo plano vigilando los activos
configurados 24/7 y ejecutando el pipeline completo cada vez que aparece una
nueva vela o se cumple el intervalo programado.

Es el componente que convierte a ASTRA de herramienta reactiva a plataforma activa.

Integracion:
    from forex.market_sentinel import MarketSentinel
    sentinel = MarketSentinel()
    sentinel.add_pair("EURUSD")
    sentinel.start()
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
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


class SentinelState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class SentinelAsset:
    pair: str
    timeframes: list[str] = field(default_factory=lambda: ["H1", "H4", "D1"])
    enabled: bool = True
    last_scan: datetime | None = None
    last_signal: str = "HOLD"
    last_reliability: float = 0.0
    scan_count: int = 0
    error_count: int = 0

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "timeframes": self.timeframes,
            "enabled": self.enabled,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "last_signal": self.last_signal,
            "last_reliability": self.last_reliability,
            "scan_count": self.scan_count,
            "error_count": self.error_count,
        }


@dataclass
class SentinelSignal:
    pair: str = ""
    timeframe: str = ""
    signal: str = "HOLD"
    reliability_score: float = 0.0
    decision: str = "HOLD"
    regime: str = ""
    mtf_coherent: bool = False
    circuit_breaker: bool = False
    timestamp: str = ""
    notified: bool = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


DEFAULT_CONFIG = {
    "scan_interval_sec": 60,
    "reliability_notify_threshold": 85.0,
    "reliability_display_threshold": 70.0,
    "circuit_breaker_max_errors": 5,
    "circuit_breaker_window_min": 30,
}


class MarketSentinel:
    """Daemon de vigilancia continua de mercados."""

    def __init__(
        self,
        db_path: str = "memoria.db",
        config: dict | None = None,
        pipeline_func: Callable | None = None,
    ):
        self.db_path = db_path
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.pipeline_func = pipeline_func
        self._assets: dict[str, SentinelAsset] = {}
        self._signals: list[SentinelSignal] = []
        self._state = SentinelState.IDLE
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._circuit_breaker_errors: list[datetime] = []
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentinel_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    timeframe TEXT,
                    signal TEXT,
                    reliability_score REAL,
                    decision TEXT,
                    regime TEXT,
                    mtf_coherent INTEGER,
                    circuit_breaker INTEGER,
                    notified INTEGER,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentinel_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Asset management ──
    def add_pair(self, pair: str, timeframes: list[str] | None = None):
        with self._lock:
            self._assets[pair.upper()] = SentinelAsset(
                pair=pair.upper(),
                timeframes=timeframes or ["H1", "H4", "D1"],
            )

    def remove_pair(self, pair: str):
        with self._lock:
            self._assets.pop(pair.upper(), None)

    def get_assets(self) -> dict[str, SentinelAsset]:
        with self._lock:
            return dict(self._assets)

    # ── Circuit Breaker ──
    def _check_circuit_breaker(self) -> bool:
        now = datetime.utcnow()
        window_start = now.timestamp() - (self.config["circuit_breaker_window_min"] * 60)
        self._circuit_breaker_errors = [t for t in self._circuit_breaker_errors if t.timestamp() >= window_start]
        return len(self._circuit_breaker_errors) >= self.config["circuit_breaker_max_errors"]

    def _record_error(self):
        self._circuit_breaker_errors.append(datetime.utcnow())

    def reset_circuit_breaker(self):
        self._circuit_breaker_errors.clear()

    # ── Scan one asset ──
    def _scan_asset(self, asset: SentinelAsset) -> SentinelSignal | None:
        if not asset.enabled:
            return None

        if self._check_circuit_breaker():
            return SentinelSignal(
                pair=asset.pair,
                circuit_breaker=True,
                decision="NO_OPERAR",
                timestamp=datetime.utcnow().isoformat(),
            )

        if self.pipeline_func is None:
            return SentinelSignal(
                pair=asset.pair,
                signal="HOLD",
                decision="HOLD",
                timestamp=datetime.utcnow().isoformat(),
            )

        try:
            result = self.pipeline_func(asset.pair, asset.timeframes[0] if asset.timeframes else "H1")
            signal = SentinelSignal(
                pair=asset.pair,
                timeframe=asset.timeframes[0] if asset.timeframes else "H1",
                signal=result.get("signal", "HOLD") if isinstance(result, dict) else "HOLD",
                reliability_score=result.get("reliability_score", 0.0) if isinstance(result, dict) else 0.0,
                decision=result.get("decision", "HOLD") if isinstance(result, dict) else "HOLD",
                regime=result.get("regime", "") if isinstance(result, dict) else "",
                mtf_coherent=result.get("mtf_coherent", False) if isinstance(result, dict) else False,
                timestamp=datetime.utcnow().isoformat(),
            )

            if signal.reliability_score >= self.config["reliability_notify_threshold"]:
                signal.notified = True

            asset.last_scan = datetime.utcnow()
            asset.last_signal = signal.signal
            asset.last_reliability = signal.reliability_score
            asset.scan_count += 1

            self._store_signal(signal)
            return signal

        except Exception:
            asset.error_count += 1
            self._record_error()
            return None

    # ── Main loop ──
    def _loop(self):
        while self._state == SentinelState.RUNNING:
            with self._lock:
                assets = list(self._assets.values())

            for asset in assets:
                signal = self._scan_asset(asset)
                if signal:
                    with self._lock:
                        self._signals.append(signal)
                        if len(self._signals) > 1000:
                            self._signals = self._signals[-500:]

            time.sleep(self.config["scan_interval_sec"])

    # ── Start/Stop ──
    def start(self):
        if self._state == SentinelState.RUNNING:
            return
        self._state = SentinelState.RUNNING
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._state = SentinelState.STOPPED
        if self._thread:
            self._thread.join(timeout=10)

    def pause(self):
        self._state = SentinelState.PAUSED

    def resume(self):
        if self._state == SentinelState.PAUSED:
            self._state = SentinelState.RUNNING

    # ── Status ──
    def get_status(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "circuit_breaker_active": self._check_circuit_breaker(),
                "assets_monitored": len(self._assets),
                "total_scans": sum(a.scan_count for a in self._assets.values()),
                "total_signals": len(self._signals),
                "recent_signals": [s.to_dict() for s in self._signals[-10:]],
                "assets": {k: v.to_dict() for k, v in self._assets.items()},
            }

    def get_active_signals(self, min_reliability: float = 0.0) -> list[dict]:
        with self._lock:
            return [
                s.to_dict() for s in self._signals
                if s.reliability_score >= min_reliability and s.signal in ("BUY", "SELL")
            ]

    # ── Storage ──
    def _store_signal(self, signal: SentinelSignal):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO sentinel_signals
                (pair, timeframe, signal, reliability_score, decision, regime,
                 mtf_coherent, circuit_breaker, notified, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.pair, signal.timeframe, signal.signal,
                signal.reliability_score, signal.decision, signal.regime,
                int(signal.mtf_coherent), int(signal.circuit_breaker),
                int(signal.notified), signal.timestamp,
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_signal_history(self, pair: str = "", limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            if pair:
                rows = conn.execute(
                    "SELECT * FROM sentinel_signals WHERE pair=? ORDER BY id DESC LIMIT ?",
                    (pair, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sentinel_signals ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
            cols = ["id", "pair", "timeframe", "signal", "reliability_score",
                    "decision", "regime", "mtf_coherent", "circuit_breaker",
                    "notified", "timestamp"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []


# ── CLI ──
def cmd_sentinel_status(args: str = "") -> str:
    """Comando CLI: sentinel_status"""
    sentinel = MarketSentinel()
    status = sentinel.get_status()
    lines = [
        f"{_C('Market Sentinel')} — state={_G(status['state'])}",
        f"  Activos vigilados: {status['assets_monitored']}",
        f"  Total scans: {status['total_scans']}",
        f"  Total signals: {status['total_signals']}",
        f"  Circuit Breaker: {_R('ACTIVO') if status['circuit_breaker_active'] else _G('OK')}",
    ]
    if status["assets"]:
        lines.append(f"\n  {_C('Activos')}:")
        for pair, a in status["assets"].items():
            lines.append(
                f"    {pair}: scans={a['scan_count']}, last={a['last_signal']} "
                f"(R={a['last_reliability']:.1f}), errors={a['error_count']}"
            )
    return "\n".join(lines)


def cmd_sentinel_signals(args: str = "") -> str:
    """Comando CLI: sentinel_signals [pair] [limit]"""
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    limit = int(parts[1]) if len(parts) > 1 else 20
    sentinel = MarketSentinel()
    signals = sentinel.get_signal_history(pair=pair, limit=limit)
    if not signals:
        return f"{_Y('Sin signals registradas')}"
    lines = [f"{_C('Signals del Sentinel')} ({len(signals)})"]
    for s in signals:
        icon = _G(s["signal"]) if s["signal"] in ("BUY", "SELL") else _Y(s["signal"])
        notif = _B("NOTIFIED") if s["notified"] else ""
        lines.append(
            f"  {s['timestamp'][:19]} | {s['pair']} {s['timeframe']} | "
            f"{icon} | R={s['reliability_score']:.1f} | {s['regime']} | {notif}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    def mock_pipeline(pair, tf):
        return {"signal": "BUY", "reliability_score": 88.0, "decision": "BUY", "regime": "trending_bullish", "mtf_coherent": True}

    sentinel = MarketSentinel(config={"scan_interval_sec": 2})
    sentinel.pipeline_func = mock_pipeline
    sentinel.add_pair("EURUSD")
    sentinel.start()
    time.sleep(5)
    sentinel.stop()
    print(cmd_sentinel_status())
    print()
    print(cmd_sentinel_signals())
