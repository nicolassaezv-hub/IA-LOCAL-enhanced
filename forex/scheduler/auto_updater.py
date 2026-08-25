"""
VI.5.B — Auto Dataset Updater
Actualiza automáticamente los CSVs de pares activos usando el DataRouter.
Se ejecuta vía el AutonomousScheduler en cada ciclo H1/H4/D1.
"""
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_INDEX_PATH = Path(os.environ.get("ASTRA_CSV_INDEX_PATH", "astra_csv_index.json"))
if not _INDEX_PATH.is_absolute():
    _INDEX_PATH = _PROJECT_ROOT / _INDEX_PATH


class AutoUpdater:
    """
    Actualiza incrementalmente los datasets de pares activos.
    Usa RollingDataset para actualización validada, bloqueada y atómica.
    """

    def __init__(self, database=None):
        self._last_update: dict[str, datetime] = {}
        self._update_log: list[dict] = []
        if database is None:
            from infra.db.database import get_database

            database = get_database()
        self.database = database

    def _load_active_pairs(self) -> list[dict]:
        """Intersect the legacy CSV index with lifecycle-active symbols."""
        try:
            if not _INDEX_PATH.exists():
                return []
            with open(_INDEX_PATH) as f:
                index = json.load(f)
            active_symbols = {
                row["symbol_code"] for row in self.database.get_data_symbols()
            }
            return [
                entry for entry in index.values()
                if str(entry.get("pair", "")).upper() in active_symbols
            ]
        except Exception:
            return []

    def update_pair(self, pair: str, tf: str = "H1",
                    bars_fetch: int = 10) -> dict:
        """
        Actualiza un par específico: descarga las últimas N velas y hace rolling update.
        Retorna dict con resultado de la actualización.
        """
        result = {"pair": pair, "tf": tf, "ts": datetime.now().isoformat(),
                  "ok": False, "rows_added": 0, "source": None, "error": None}
        try:
            active_symbols = {
                row["symbol_code"] for row in self.database.get_data_symbols()
            }
            if pair.upper() not in active_symbols:
                result["error"] = "Símbolo no activo en supported_symbols"
                return result

            from forex.data.data_router import DataRouter
            router = DataRouter(pair, tf)
            df_new = router.fetch(bars=bars_fetch)
            if df_new is None or df_new.empty:
                result["error"] = "Sin datos nuevos del DataRouter"
                return result

            result["source"] = router.source_used

            from forex.data.rolling_dataset import RollingDataset
            rd = RollingDataset(pair, tf)
            stored = rd.update_frame(df_new)
            result["rows_added"] = stored["added"]

            result["ok"] = True
            self._last_update[f"{pair}_{tf}"] = datetime.now()
            self._update_log.append({**result, "status": "ok"})
            logger.info(f"[AutoUpdater] {pair}/{tf} actualizado (+{result['rows_added']} filas, src={result['source']})")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"[AutoUpdater] Error actualizando {pair}/{tf}: {e}")

        return result

    def update_all(self, bars_fetch: int = 5) -> list[dict]:
        """Actualiza todos los pares del índice de CSVs."""
        active = self._load_active_pairs()
        if not active:
            logger.warning("[AutoUpdater] Índice de CSVs vacío — nada que actualizar.")
            return []
        results = []
        for entry in active:
            r = self.update_pair(entry["pair"], entry.get("tf", "H1"), bars_fetch)
            results.append(r)
        return results

    def status(self) -> str:
        lines = ["\n  🔄 Auto Updater"]
        if not self._update_log:
            lines.append("  Sin actualizaciones registradas.")
            return "\n".join(lines)
        last = self._update_log[-10:]
        lines.append(f"  Últimas {len(last)} actualizaciones:")
        for r in reversed(last):
            icon = "✅" if r["ok"] else "❌"
            lines.append(
                f"    {icon} {r['pair']}/{r['tf']}  +{r['rows_added']} filas  "
                f"src={r.get('source','?')}  {r['ts'][:19]}"
            )
        return "\n".join(lines)

    def last_update_time(self, pair: str, tf: str = "H1") -> Optional[datetime]:
        return self._last_update.get(f"{pair}_{tf}")


_updater: Optional[AutoUpdater] = None


def get_auto_updater() -> AutoUpdater:
    global _updater
    if _updater is None:
        _updater = AutoUpdater()
    return _updater
