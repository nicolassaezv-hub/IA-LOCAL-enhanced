"""
VI.6.C — CSV Migration Tool
Convierte CSVs existentes al formato rolling compatible.
Genera índice de CSVs activos para el scheduler.
"""
import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

from forex.data.rolling_dataset import ROLLING_WINDOW


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_INDEX_PATH = Path(os.environ.get("ASTRA_CSV_INDEX_PATH", "astra_csv_index.json"))
if not _INDEX_PATH.is_absolute():
    _INDEX_PATH = _PROJECT_ROOT / _INDEX_PATH
_DEFAULT_CSV_ROOT = _PROJECT_ROOT / "CSVs"

_REQUIRED_COLS = {"timestamp", "open", "high", "low", "close", "volume"}
_COL_ALIASES = {
    "date": "timestamp", "time": "timestamp",
    "Date": "timestamp", "Time": "timestamp", "Datetime": "timestamp",
    "Open": "open", "High": "high", "Low": "low", "Close": "close",
    "Volume": "volume", "Vol": "volume", "tick_volume": "volume",
}


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres de columnas al schema estándar."""
    df = df.rename(columns={k: v for k, v in _COL_ALIASES.items() if k in df.columns})
    if "timestamp" not in df.columns:
        for c in df.columns:
            if "date" in c.lower() or "time" in c.lower():
                df = df.rename(columns={c: "timestamp"})
                break
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def migrate_csv(csv_path: str, pair: str = None, tf: str = None,
                max_rows: int = ROLLING_WINDOW, output_dir: str = None) -> dict:
    """
    Migra un CSV existente al formato rolling.
    Normaliza columnas, ajusta tamaño y guarda en la ruta estándar.
    """
    p = Path(csv_path)
    if not p.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {csv_path}"}

    try:
        df = pd.read_csv(p)
    except Exception as e:
        return {"ok": False, "error": f"Error leyendo CSV: {e}"}

    df = _normalize_df(df)

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        return {"ok": False, "error": f"Columnas faltantes tras normalización: {missing}"}

    original_rows = len(df)
    df = df.tail(max_rows).reset_index(drop=True)

    inferred_pair = pair or p.stem.replace("_", "").upper()
    inferred_tf = tf or "H1"

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = _DEFAULT_CSV_ROOT / inferred_tf
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{inferred_pair}.csv"

    df.to_csv(out_path, index=False)

    _update_index(inferred_pair, inferred_tf, str(out_path), len(df))

    return {
        "ok": True,
        "pair": inferred_pair,
        "tf": inferred_tf,
        "original_rows": original_rows,
        "final_rows": len(df),
        "output_path": str(out_path),
    }


def _update_index(pair: str, tf: str, csv_path: str, rows: int):
    """Actualiza el índice JSON de CSVs activos."""
    try:
        index = {}
        if _INDEX_PATH.exists():
            with open(_INDEX_PATH) as f:
                index = json.load(f)
        key = f"{pair}_{tf}"
        index[key] = {
            "pair": pair,
            "tf": tf,
            "csv_path": csv_path,
            "rows": rows,
            "last_updated": datetime.now().isoformat(),
        }
        with open(_INDEX_PATH, "w") as f:
            json.dump(index, f, indent=2)
    except Exception:
        pass


def list_active_csvs() -> list[dict]:
    """Lista todos los CSVs activos registrados en el índice."""
    try:
        if not _INDEX_PATH.exists():
            return []
        with open(_INDEX_PATH) as f:
            index = json.load(f)
        return list(index.values())
    except Exception:
        return []


def scan_csv_directory(csv_root: str = None) -> list[dict]:
    """
    Escanea el directorio CSVs/ y registra todos los que encuentra.
    Devuelve lista de CSVs encontrados.
    """
    root = Path(csv_root) if csv_root else _DEFAULT_CSV_ROOT
    found = []
    if not root.exists():
        return found
    for tf_dir in root.iterdir():
        if not tf_dir.is_dir():
            continue
        tf = tf_dir.name
        for csv_file in tf_dir.glob("*.csv"):
            pair = csv_file.stem.replace("_", "").upper()
            try:
                df = pd.read_csv(csv_file, nrows=1)
                rows = sum(1 for _ in open(csv_file)) - 1
                _update_index(pair, tf, str(csv_file), rows)
                found.append({"pair": pair, "tf": tf, "path": str(csv_file), "rows": rows})
            except Exception:
                pass
    return found


def status() -> str:
    csvs = list_active_csvs()
    if not csvs:
        return "Índice de CSVs vacío. Ejecuta 'migrar csv' o 'escanear csvs'."
    lines = [f"  CSVs activos en índice ({len(csvs)}):"]
    for c in csvs:
        lines.append(
            f"    {c['pair']}/{c['tf']} — {c.get('rows', '?')} filas  "
            f"updated: {c.get('last_updated', 'N/A')[:10]}"
        )
    return "\n".join(lines)
