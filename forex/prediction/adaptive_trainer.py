"""
VI.1.B — Adaptive Training Budget
Ajusta automáticamente n_trials de Optuna según la urgencia y el historial.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_DB_PATH = Path(__file__).parent.parent.parent / "astra_hparam_cache.db"

_DEFAULTS = {
    "production":   50,   # entrenamiento completo con dataset grande
    "adaptive":     15,   # reentrenamiento periódico (scheduler H1/H4)
    "quick":         8,   # reentrenamiento de emergencia o test
    "initial":      30,   # primer entrenamiento de un par nuevo
}

_MIN_TRIALS = 5
_MAX_TRIALS = 100


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_budget_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pair        TEXT,
            horizon     TEXT,
            mode        TEXT,
            n_trials    INTEGER,
            accuracy    REAL,
            duration_s  REAL,
            created_at  TEXT
        )
    """)
    conn.commit()
    return conn


class AdaptiveTrainer:
    """
    Gestiona el budget de trials de Optuna.
    Aprende del historial: si en los últimos N entrenamientos
    la precisión plafonó antes del máximo, reduce trials futuros.
    """

    def get_trials(self, pair: str, horizon: str = "H1",
                   mode: str = "production") -> int:
        """
        Devuelve el número de trials recomendado para este par/horizon/modo.
        Modes: 'production' | 'adaptive' | 'quick' | 'initial'
        """
        base = _DEFAULTS.get(mode, _DEFAULTS["production"])
        adjustment = self._calculate_adjustment(pair, horizon)
        trials = max(_MIN_TRIALS, min(_MAX_TRIALS, base + adjustment))
        return trials

    def _calculate_adjustment(self, pair: str, horizon: str) -> int:
        """
        Ajuste basado en historial:
        - Si la precisión mejoró mucho en los últimos runs → +10 (aún hay margen)
        - Si la precisión se estancó → -10 (ya llegó al plateau)
        - Si no hay historial → 0
        """
        try:
            with _get_conn() as conn:
                rows = conn.execute("""
                    SELECT n_trials, accuracy FROM training_budget_log
                    WHERE pair=? AND horizon=?
                    ORDER BY created_at DESC LIMIT 5
                """, (pair.upper(), horizon)).fetchall()
                if len(rows) < 2:
                    return 0
                accuracies = [r[1] for r in rows if r[1] is not None]
                if len(accuracies) < 2:
                    return 0
                improvement = max(accuracies) - min(accuracies)
                if improvement > 5:
                    return 10
                elif improvement < 1:
                    return -10
                return 0
        except Exception:
            return 0

    def log_result(self, pair: str, horizon: str, mode: str,
                   n_trials: int, accuracy: float, duration_s: float):
        """Registra el resultado de un entrenamiento para aprender del historial."""
        try:
            with _get_conn() as conn:
                conn.execute("""
                    INSERT INTO training_budget_log
                        (pair, horizon, mode, n_trials, accuracy, duration_s, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pair.upper(), horizon, mode, n_trials,
                      accuracy, duration_s, datetime.now().isoformat()))
                conn.commit()
        except Exception:
            pass

    def recommended_mode(self, is_scheduler: bool = False,
                         is_first_train: bool = False,
                         force_production: bool = False) -> str:
        """Determina el modo adecuado según el contexto."""
        if force_production:
            return "production"
        if is_first_train:
            return "initial"
        if is_scheduler:
            return "adaptive"
        return "production"

    def status(self, pair: str = None) -> str:
        """Resumen del historial de budgets."""
        try:
            with _get_conn() as conn:
                q = "SELECT pair, horizon, mode, n_trials, accuracy, created_at FROM training_budget_log"
                args = []
                if pair:
                    q += " WHERE pair=?"
                    args.append(pair.upper())
                q += " ORDER BY created_at DESC LIMIT 10"
                rows = conn.execute(q, args).fetchall()
                if not rows:
                    return "Sin historial de entrenamientos."
                lines = ["  Budget adaptativo — últimos entrenamientos:"]
                for r in rows:
                    lines.append(
                        f"    {r[0]}/{r[1]} ({r[2]}) — {r[3]} trials  "
                        f"acc={r[4]:.1f}%  {r[5][:10]}"
                    )
                return "\n".join(lines)
        except Exception:
            return "Error leyendo historial."


_adaptive = AdaptiveTrainer()


def get_adaptive_trainer() -> AdaptiveTrainer:
    return _adaptive
