"""
VI.8.C — Model Quality History
Registro histórico de precisión de modelos verificada con resultados reales.
El outcome_tracker (V.14) alimenta este módulo.
El Opportunity Score pondera más a los modelos con mayor precisión histórica verificada.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent.parent / "astra_model_quality.db"
_HISTORY_WINDOW_DAYS = 30
_MIN_SAMPLES_FOR_TRUST = 10   # mínimo de muestras para considerar el historial fiable


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_outcomes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pair        TEXT NOT NULL,
            horizon     TEXT NOT NULL,
            model_name  TEXT NOT NULL,
            predicted   TEXT NOT NULL,      -- BUY / SELL / HOLD
            actual      TEXT,               -- resultado real (puede ser NULL si no verificado)
            correct     INTEGER,            -- 1 = correcto, 0 = incorrecto, NULL = pendiente
            op_score    REAL,
            ts          TEXT NOT NULL,
            verified_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_accuracy_cache (
            pair        TEXT,
            horizon     TEXT,
            model_name  TEXT,
            samples     INTEGER,
            accuracy    REAL,
            last_updated TEXT,
            PRIMARY KEY (pair, horizon, model_name)
        )
    """)
    conn.commit()
    return conn


class ModelQualityHistory:
    """
    Rastrea y calcula la precisión histórica de modelos por par/horizonte.
    Ventana deslizante de 30 días.
    """

    def record_prediction(self, pair: str, horizon: str, model_name: str,
                          predicted: str, op_score: float = 0.0):
        """Registra una predicción para seguimiento futuro."""
        try:
            with _get_conn() as conn:
                conn.execute("""
                    INSERT INTO model_outcomes
                        (pair, horizon, model_name, predicted, op_score, ts)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pair.upper(), horizon, model_name, predicted,
                      op_score, datetime.now().isoformat()))
                conn.commit()
        except Exception:
            pass

    def record_outcome(self, pair: str, horizon: str, model_name: str,
                       prediction_ts: str, actual: str):
        """
        Registra el resultado real de una predicción anterior.
        Actualiza la precisión del modelo en el caché.
        """
        try:
            with _get_conn() as conn:
                # Buscar la predicción más cercana al timestamp dado
                row = conn.execute("""
                    SELECT id, predicted FROM model_outcomes
                    WHERE pair=? AND horizon=? AND model_name=? AND actual IS NULL
                    ORDER BY ABS(julianday(ts) - julianday(?)) LIMIT 1
                """, (pair.upper(), horizon, model_name, prediction_ts)).fetchone()

                if not row:
                    return

                pred_id, predicted = row
                correct = 1 if predicted == actual else 0
                conn.execute("""
                    UPDATE model_outcomes
                    SET actual=?, correct=?, verified_at=?
                    WHERE id=?
                """, (actual, correct, datetime.now().isoformat(), pred_id))
                conn.commit()
                self._refresh_accuracy_cache(pair, horizon, model_name, conn)
        except Exception:
            pass

    def _refresh_accuracy_cache(self, pair: str, horizon: str, model_name: str,
                                 conn: sqlite3.Connection):
        """Recalcula y cachea la precisión del modelo."""
        cutoff = (datetime.now() - timedelta(days=_HISTORY_WINDOW_DAYS)).isoformat()
        rows = conn.execute("""
            SELECT COUNT(*), SUM(correct) FROM model_outcomes
            WHERE pair=? AND horizon=? AND model_name=?
              AND correct IS NOT NULL AND ts > ?
        """, (pair.upper(), horizon, model_name, cutoff)).fetchone()

        if not rows or rows[0] == 0:
            return

        samples, correct_sum = rows
        accuracy = (correct_sum / samples) * 100
        conn.execute("""
            INSERT INTO model_accuracy_cache
                (pair, horizon, model_name, samples, accuracy, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(pair, horizon, model_name) DO UPDATE SET
                samples=excluded.samples,
                accuracy=excluded.accuracy,
                last_updated=excluded.last_updated
        """, (pair.upper(), horizon, model_name, samples, accuracy,
              datetime.now().isoformat()))
        conn.commit()

    def get_accuracy(self, pair: str, horizon: str = "H1",
                     model_name: str = "ensemble") -> Optional[float]:
        """
        Devuelve la precisión verificada del modelo en los últimos 30 días.
        None si hay menos de MIN_SAMPLES_FOR_TRUST muestras verificadas.
        """
        try:
            with _get_conn() as conn:
                row = conn.execute("""
                    SELECT accuracy, samples FROM model_accuracy_cache
                    WHERE pair=? AND horizon=? AND model_name=?
                """, (pair.upper(), horizon, model_name)).fetchone()
                if not row:
                    return None
                accuracy, samples = row
                if samples < _MIN_SAMPLES_FOR_TRUST:
                    return None
                return float(accuracy)
        except Exception:
            return None

    def get_win_rate(self, pair: str, horizon: str = "H1") -> float:
        """
        Devuelve el win rate para uso en OpScore.
        Si no hay historial suficiente, devuelve el win rate por defecto (50%).
        """
        acc = self.get_accuracy(pair, horizon)
        return acc if acc is not None else 50.0

    def list_history(self, limit: int = 20) -> list[dict]:
        """Lista los últimos registros de precisión."""
        try:
            with _get_conn() as conn:
                rows = conn.execute("""
                    SELECT pair, horizon, model_name, accuracy, samples, last_updated
                    FROM model_accuracy_cache
                    ORDER BY last_updated DESC LIMIT ?
                """, (limit,)).fetchall()
                return [
                    {"pair": r[0], "horizon": r[1], "model": r[2],
                     "accuracy": r[3], "samples": r[4], "updated": r[5]}
                    for r in rows
                ]
        except Exception:
            return []

    def status(self) -> str:
        items = self.list_history()
        if not items:
            return "Sin historial de precisión verificada. Se necesitan al menos 10 predicciones confirmadas."
        lines = [f"  Model Quality History (ventana 30 días):"]
        for it in items[:10]:
            stars = "★" * min(5, max(1, int(it["accuracy"] / 20)))
            lines.append(
                f"    {it['pair']}/{it['horizon']} ({it['model']}) — "
                f"{it['accuracy']:.1f}% ({it['samples']} muestras) {stars}"
            )
        return "\n".join(lines)


_quality_history = ModelQualityHistory()


def get_quality_history() -> ModelQualityHistory:
    return _quality_history
