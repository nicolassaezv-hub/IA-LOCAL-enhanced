"""
VI.1.C — Model Cache Manager
Versioning inteligente: evita reentrenar si el dataset no cambió significativamente.
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "astra_hparam_cache.db"
_CHANGE_THRESHOLD = 0.05   # 5% cambio en datos → reentrenar
_ACCURACY_MIN     = 0.52   # precisión mínima aceptable para mantener modelo


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_version_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            pair         TEXT,
            horizon      TEXT,
            model_path   TEXT,
            data_hash    TEXT,
            row_count    INTEGER,
            accuracy     REAL,
            created_at   TEXT,
            is_active    INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    return conn


def _csv_hash(csv_path: str) -> tuple[str, int]:
    """Hash del CSV y número de filas."""
    try:
        p = Path(csv_path)
        if not p.exists():
            return "no_file", 0
        size = p.stat().st_size
        rows = 0
        with open(p, "rb") as f:
            content = f.read()
            rows = content.count(b"\n")
            h = hashlib.md5(content[:2048] + content[-2048:] + str(size).encode()).hexdigest()[:16]
        return h, rows
    except Exception:
        return "unknown", 0


class ModelCacheManager:
    """
    Gestiona versiones de modelos entrenados.
    Decide si es necesario reentrenar comparando el dataset actual con el anterior.
    """

    def should_retrain(self, pair: str, horizon: str = "H1",
                       csv_path: str = "") -> tuple[bool, str]:
        """
        Retorna (debe_reentrenar, motivo).
        Si no es necesario, el modelo existente sigue siendo válido.
        """
        try:
            with _get_conn() as conn:
                row = conn.execute("""
                    SELECT data_hash, row_count, accuracy FROM model_version_log
                    WHERE pair=? AND horizon=? AND is_active=1
                    ORDER BY created_at DESC LIMIT 1
                """, (pair.upper(), horizon)).fetchone()

                if not row:
                    return True, "Sin modelo previo — entrenamiento inicial"

                old_hash, old_rows, accuracy = row

                if accuracy is not None and accuracy < _ACCURACY_MIN:
                    return True, f"Precisión ({accuracy:.1f}%) por debajo del mínimo ({_ACCURACY_MIN*100:.0f}%)"

                if not csv_path:
                    return False, "Sin CSV nuevo — manteniendo modelo existente"

                new_hash, new_rows = _csv_hash(csv_path)

                if old_rows > 0:
                    change_ratio = abs(new_rows - old_rows) / old_rows
                    if change_ratio > _CHANGE_THRESHOLD:
                        return True, f"Dataset cambió {change_ratio*100:.1f}% ({old_rows}→{new_rows} filas)"

                if new_hash == old_hash:
                    return False, "Dataset sin cambios — modelo vigente válido"

                return False, "Cambio mínimo en datos — modelo existente es suficiente"

        except Exception as e:
            return True, f"Error verificando caché: {e}"

    def register_model(self, pair: str, horizon: str = "H1",
                       model_path: str = "", csv_path: str = "",
                       accuracy: float = 0.0):
        """Registra un modelo recién entrenado."""
        data_hash, row_count = _csv_hash(csv_path)
        try:
            with _get_conn() as conn:
                conn.execute("""
                    UPDATE model_version_log SET is_active=0
                    WHERE pair=? AND horizon=?
                """, (pair.upper(), horizon))
                conn.execute("""
                    INSERT INTO model_version_log
                        (pair, horizon, model_path, data_hash, row_count, accuracy, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (pair.upper(), horizon, model_path, data_hash,
                      row_count, accuracy, datetime.now().isoformat()))
                conn.commit()
        except Exception:
            pass

    def list_active_models(self) -> list[dict]:
        """Lista todos los modelos activos registrados."""
        try:
            with _get_conn() as conn:
                rows = conn.execute("""
                    SELECT pair, horizon, accuracy, row_count, created_at
                    FROM model_version_log WHERE is_active=1
                    ORDER BY created_at DESC
                """).fetchall()
                return [
                    {"pair": r[0], "horizon": r[1], "accuracy": r[2],
                     "row_count": r[3], "created_at": r[4]}
                    for r in rows
                ]
        except Exception:
            return []

    def status(self) -> str:
        models = self.list_active_models()
        if not models:
            return "Sin modelos registrados en el model cache."
        lines = [f"  Model Cache ({len(models)} modelos activos):"]
        for m in models:
            lines.append(
                f"    {m['pair']}/{m['horizon']} — "
                f"acc={m['accuracy']:.1f}%  rows={m['row_count']}  {m['created_at'][:10]}"
            )
        return "\n".join(lines)


_model_cache = ModelCacheManager()


def get_model_cache() -> ModelCacheManager:
    return _model_cache
