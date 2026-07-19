"""
V.14 — Aprendizaje Basado en Resultados
========================================
Cada prediccion se evalua posteriormente contra el resultado real del mercado.
Automatiza el feedback que antes era manual (el usuario votaba).

El Sentinel (V.10) dispara la evaluacion N horas despues de cada señal.

Integracion:
    from forex.prediction.outcome_tracker import OutcomeTracker
    tracker = OutcomeTracker()
    tracker.record_prediction("EURUSD", "H1", "BUY", 1.0850, reliability=82.0)
    # ... N velas despues ...
    result = tracker.evaluate_prediction(pred_id, actual_price=1.0900)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

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


@dataclass
class PredictionRecord:
    id: int | None = None
    pair: str = ""
    timeframe: str = ""
    signal: str = "HOLD"
    entry_price: float = 0.0
    reliability_score: float = 0.0
    regime: str = ""
    mtf_coherent: bool = False
    news_active: bool = False
    timestamp: str = ""
    evaluated: bool = False
    actual_price: float = 0.0
    outcome: str = ""
    price_change: float = 0.0
    direction_correct: bool = False
    evaluation_time: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class OutcomeStats:
    pair: str = ""
    total_predictions: int = 0
    evaluated: int = 0
    correct: int = 0
    incorrect: int = 0
    win_rate: float = 0.0
    avg_reliability: float = 0.0
    avg_price_change: float = 0.0
    best_reliability: float = 0.0
    worst_reliability: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class OutcomeTracker:
    """Evaluador automatico de resultados de predicciones."""

    def __init__(self, db_path: str = "memoria.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outcome_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    timeframe TEXT,
                    signal TEXT,
                    entry_price REAL,
                    reliability_score REAL,
                    regime TEXT,
                    mtf_coherent INTEGER,
                    news_active INTEGER,
                    timestamp TEXT,
                    evaluated INTEGER DEFAULT 0,
                    actual_price REAL DEFAULT 0,
                    outcome TEXT DEFAULT '',
                    price_change REAL DEFAULT 0,
                    direction_correct INTEGER DEFAULT 0,
                    evaluation_time TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcome_pair ON outcome_predictions(pair)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcome_evaluated ON outcome_predictions(evaluated)
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Record a prediction ──
    def record_prediction(
        self,
        pair: str,
        timeframe: str,
        signal: str,
        entry_price: float,
        reliability_score: float = 0.0,
        regime: str = "",
        mtf_coherent: bool = False,
        news_active: bool = False,
    ) -> int:
        ts = datetime.utcnow().isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                INSERT INTO outcome_predictions
                (pair, timeframe, signal, entry_price, reliability_score,
                 regime, mtf_coherent, news_active, timestamp, evaluated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                pair, timeframe, signal, entry_price, reliability_score,
                regime, int(mtf_coherent), int(news_active), ts,
            ))
            pred_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return pred_id
        except Exception:
            return -1

    # ── Evaluate a prediction ──
    def evaluate_prediction(
        self,
        pred_id: int,
        actual_price: float,
    ) -> PredictionRecord | None:
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT * FROM outcome_predictions WHERE id=?",
                (pred_id,),
            ).fetchone()
            if not row:
                conn.close()
                return None

            signal = row[3]
            entry_price = row[4]
            price_change = actual_price - entry_price

            if signal == "BUY":
                direction_correct = price_change > 0
                outcome = "win" if direction_correct else "loss"
            elif signal == "SELL":
                direction_correct = price_change < 0
                outcome = "win" if direction_correct else "loss"
            else:
                direction_correct = abs(price_change) < 0.0001
                outcome = "neutral"

            eval_time = datetime.utcnow().isoformat()
            conn.execute("""
                UPDATE outcome_predictions
                SET evaluated=1, actual_price=?, outcome=?, price_change=?,
                    direction_correct=?, evaluation_time=?
                WHERE id=?
            """, (actual_price, outcome, price_change, int(direction_correct), eval_time, pred_id))
            conn.commit()
            conn.close()

            return PredictionRecord(
                id=pred_id,
                pair=row[1],
                timeframe=row[2],
                signal=signal,
                entry_price=entry_price,
                reliability_score=row[5],
                regime=row[6],
                mtf_coherent=bool(row[7]),
                news_active=bool(row[8]),
                timestamp=row[9],
                evaluated=True,
                actual_price=actual_price,
                outcome=outcome,
                price_change=price_change,
                direction_correct=direction_correct,
                evaluation_time=eval_time,
            )
        except Exception:
            return None

    # ── Get pending predictions ──
    def get_pending(self, pair: str = "", limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            if pair:
                rows = conn.execute(
                    "SELECT * FROM outcome_predictions WHERE evaluated=0 AND pair=? ORDER BY id DESC LIMIT ?",
                    (pair, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM outcome_predictions WHERE evaluated=0 ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
            cols = ["id", "pair", "timeframe", "signal", "entry_price",
                    "reliability_score", "regime", "mtf_coherent", "news_active",
                    "timestamp", "evaluated", "actual_price", "outcome",
                    "price_change", "direction_correct", "evaluation_time"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []

    # ── Get stats ──
    def get_stats(self, pair: str = "") -> OutcomeStats:
        stats = OutcomeStats(pair=pair)
        try:
            conn = sqlite3.connect(self.db_path)
            if pair:
                rows = conn.execute(
                    "SELECT signal, reliability_score, evaluated, direction_correct, price_change FROM outcome_predictions WHERE pair=?",
                    (pair,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT signal, reliability_score, evaluated, direction_correct, price_change FROM outcome_predictions",
                ).fetchall()
            conn.close()

            stats.total_predictions = len(rows)
            evaluated = [r for r in rows if r[2]]
            stats.evaluated = len(evaluated)
            stats.correct = sum(1 for r in evaluated if r[3])
            stats.incorrect = stats.evaluated - stats.correct
            stats.win_rate = stats.correct / stats.evaluated if stats.evaluated > 0 else 0.0

            if rows:
                rels = [r[1] for r in rows if r[1] is not None]
                if rels:
                    stats.avg_reliability = sum(rels) / len(rels)
                    stats.best_reliability = max(rels)
                    stats.worst_reliability = min(rels)

                changes = [r[4] for r in evaluated if r[4] is not None]
                if changes:
                    stats.avg_price_change = sum(changes) / len(changes)

        except Exception:
            pass
        return stats

    # ── Get history ──
    def get_history(self, pair: str = "", limit: int = 50, evaluated_only: bool = False) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT * FROM outcome_predictions"
            conditions = []
            params = []
            if pair:
                conditions.append("pair=?")
                params.append(pair)
            if evaluated_only:
                conditions.append("evaluated=1")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            conn.close()
            cols = ["id", "pair", "timeframe", "signal", "entry_price",
                    "reliability_score", "regime", "mtf_coherent", "news_active",
                    "timestamp", "evaluated", "actual_price", "outcome",
                    "price_change", "direction_correct", "evaluation_time"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []

    # ── Auto-evaluate old predictions (called by scheduler) ──
    def auto_evaluate(self, price_func: callable, max_age_hours: int = 24) -> int:
        pending = self.get_pending(limit=100)
        evaluated = 0
        for p in pending:
            ts = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")) if p["timestamp"] else None
            if ts and (datetime.utcnow() - ts.replace(tzinfo=None)) >= timedelta(hours=max_age_hours):
                try:
                    actual = price_func(p["pair"])
                    if actual and self.evaluate_prediction(p["id"], actual):
                        evaluated += 1
                except Exception:
                    pass
        return evaluated


# ── CLI ──
def cmd_outcome_stats(args: str = "") -> str:
    """Comando CLI: outcome_stats [pair]"""
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    tracker = OutcomeTracker()
    stats = tracker.get_stats(pair=pair)
    lines = [
        f"{_C('Outcome Stats')} — {pair or 'ALL'}",
        f"  Total predicciones: {stats.total_predictions}",
        f"  Evaluadas: {stats.evaluated}",
        f"  Correctas: {_G(str(stats.correct))} / Incorrectas: {_R(str(stats.incorrect))}",
        f"  Win Rate: {_G(f'{stats.win_rate:.1%}') if stats.win_rate >= 0.5 else _R(f'{stats.win_rate:.1%}')}",
        f"  Avg Reliability: {stats.avg_reliability:.1f}",
        f"  Avg Price Change: {stats.avg_price_change:.5f}",
    ]
    return "\n".join(lines)


def cmd_outcome_history(args: str = "") -> str:
    """Comando CLI: outcome_history [pair] [limit]"""
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    limit = int(parts[1]) if len(parts) > 1 else 20
    tracker = OutcomeTracker()
    history = tracker.get_history(pair=pair, limit=limit, evaluated_only=True)
    if not history:
        return f"{_Y('Sin predicciones evaluadas')}"
    lines = [f"{_C('Outcome History')} ({len(history)})"]
    for h in history:
        icon = _G("WIN") if h["outcome"] == "win" else _R("LOSS") if h["outcome"] == "loss" else _Y("NEUTRAL")
        lines.append(
            f"  {h['timestamp'][:19]} | {h['pair']} {h['timeframe']} | "
            f"{h['signal']} | {icon} | R={h['reliability_score']:.1f} | "
            f"entry={h['entry_price']:.5f} → actual={h['actual_price']:.5f} | "
            f"Δ={h['price_change']:.5f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    tracker = OutcomeTracker()
    pid = tracker.record_prediction("EURUSD", "H1", "BUY", 1.0850, reliability_score=82.0, regime="trending_bullish")
    print(f"Recorded prediction id={pid}")
    result = tracker.evaluate_prediction(pid, actual_price=1.0900)
    if result:
        print(f"Evaluated: outcome={result.outcome}, correct={result.direction_correct}, change={result.price_change:.5f}")
    print(cmd_outcome_stats("EURUSD"))
    print()
    print(cmd_outcome_history("EURUSD"))
