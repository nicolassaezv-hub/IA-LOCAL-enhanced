"""
forex/data/csv_bulk_generator.py
=================================
Genera en lote los CSVs de Forex que ASTRA usa para entrenamiento y
predicción. Descarga datos reales via YahooProvider cuando está disponible,
y cae a datos sintéticos (mismo pipeline que `generate_test_csv.py`) cuando
no hay conexión / yfinance no está instalado. Los CSVs se guardan en la
estructura estándar del proyecto: CSVs/<TF>/<PAIR>.csv

Uso desde la consola de ASTRA:
    generar csvs forex
    generar csvs forex H1,H4
    generar csvs forex H1,H4,D1 800
    generar csvs forex sinteticos
    generate forex csvs

También expuesto como función Python:
    from forex.data.csv_bulk_generator import cmd_generate_all_csvs
    print(cmd_generate_all_csvs(""))
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


# ── Configuración por defecto ─────────────────────────────────────────────
DEFAULT_PAIRS: Tuple[str, ...] = (
    # Majors
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    # Crosses populares
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD",
    # Metales
    "XAUUSD", "XAGUSD",
)
DEFAULT_TIMEFRAMES: Tuple[str, ...] = ("H1", "H4", "D1")
DEFAULT_BARS: int = 500

VALID_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _csv_dir(tf: str) -> Path:
    d = _project_root() / "CSVs" / tf.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Parsing de argumentos ─────────────────────────────────────────────────
def _parse_args(argstr: str):
    """
    Devuelve (pairs, timeframes, bars, force_synthetic).
    Formato aceptado (posicional, sencillo):
        [pairs] [timeframes] [bars] [sinteticos|synthetic]
      donde pairs y timeframes son listas separadas por coma.
    Si un token contiene ":" o "=" se interpreta como pair:timeframe override.
    Faltas -> defaults.
    """
    tokens = [t for t in (argstr or "").strip().split() if t]
    pairs: List[str] = list(DEFAULT_PAIRS)
    tfs: List[str] = list(DEFAULT_TIMEFRAMES)
    bars: int = DEFAULT_BARS
    force_synthetic = False

    # flags simples
    remaining: List[str] = []
    for t in tokens:
        low = t.lower()
        if low in ("sinteticos", "sintetico", "synthetic", "fake", "--synthetic"):
            force_synthetic = True
        else:
            remaining.append(t)

    seen_pairs = False
    seen_tfs = False
    for t in remaining:
        if t.isdigit():
            bars = max(50, int(t))
            continue
        parts = [p.strip().upper() for p in t.split(",") if p.strip()]
        if not parts:
            continue
        # Heurística: si TODOS los tokens son timeframes válidos -> es lista de TF
        if all(p in VALID_TIMEFRAMES for p in parts):
            tfs = parts
            seen_tfs = True
        else:
            pairs = parts
            seen_pairs = True

    return pairs, tfs, bars, force_synthetic


# ── Generación sintética (fallback) ───────────────────────────────────────
_SYNTH_START_PRICE = {
    "EURUSD": 1.0800, "GBPUSD": 1.2700, "USDJPY": 150.0, "USDCHF": 0.9000,
    "AUDUSD": 0.6600, "NZDUSD": 0.6100, "USDCAD": 1.3500,
    "EURGBP": 0.8500, "EURJPY": 162.0, "GBPJPY": 190.0,
    "AUDJPY": 99.0,   "EURAUD": 1.6300,
    "XAUUSD": 2350.0, "XAGUSD": 28.50,
}


def _synthetic_fetch(pair: str, tf: str, bars: int):
    """Reusa la lógica de generate_test_csv.py para datos OHLCV creíbles."""
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from generate_test_csv import generate_synthetic_data, add_indicators  # type: ignore

    price = _SYNTH_START_PRICE.get(pair.upper(), 1.0000)
    vol = 0.005 if pair.upper() in ("XAUUSD", "XAGUSD") else 0.002
    df = generate_synthetic_data(
        symbol=pair.upper(), n_candles=bars, start_price=price,
        volatility=vol, timeframe=tf.upper() if tf.upper() in ("H1", "H4", "D1") else "H1",
    )
    if df is None:
        return None
    # generate_synthetic_data ya agrega indicadores; nos quedamos con OHLCV+pair
    keep = ["timestamp", "open", "high", "low", "close", "volume"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["pair"] = pair.upper()
    return df


# ── Descarga real (Yahoo) ────────────────────────────────────────────────
def _try_yahoo(pair: str, tf: str, bars: int):
    try:
        from forex.data.yahoo_provider import get_yahoo_provider
    except Exception:
        return None
    yp = get_yahoo_provider()
    if not yp.is_available():
        return None
    try:
        return yp.fetch(pair, tf, bars)
    except Exception:
        return None


# ── Motor principal ──────────────────────────────────────────────────────
def generate_all_csvs(
    pairs: Iterable[str] = DEFAULT_PAIRS,
    timeframes: Iterable[str] = DEFAULT_TIMEFRAMES,
    bars: int = DEFAULT_BARS,
    force_synthetic: bool = False,
    verbose: bool = True,
):
    """
    Genera CSVs para todas las combinaciones pair × timeframe.
    Devuelve un dict con el resumen: {'ok': [...], 'skip': [...], 'fail': [...]}.
    """
    results = {"ok": [], "skip": [], "fail": []}
    tfs = [t.upper() for t in timeframes if t.upper() in VALID_TIMEFRAMES]
    if not tfs:
        return {"ok": [], "skip": [], "fail": [("<config>", "Timeframes inválidos")]}

    for tf in tfs:
        out_dir = _csv_dir(tf)
        for pair in pairs:
            pair_u = pair.upper()
            out_path = out_dir / f"{pair_u}.csv"
            if verbose:
                print(f"  · {pair_u} [{tf}] ", end="", flush=True)

            df = None
            source = "synthetic"
            if not force_synthetic:
                df = _try_yahoo(pair_u, tf, bars)
                if df is not None and len(df) > 0:
                    source = "yahoo"
            if df is None or len(df) == 0:
                df = _synthetic_fetch(pair_u, tf, bars)
                source = "synthetic"

            if df is None or len(df) == 0:
                results["fail"].append((f"{pair_u}/{tf}", "sin datos"))
                if verbose:
                    print("FAIL")
                continue

            try:
                df.to_csv(out_path, index=False)
                results["ok"].append((f"{pair_u}/{tf}", str(out_path), source, len(df)))
                if verbose:
                    print(f"OK ({source}, {len(df)} filas) -> {out_path.relative_to(_project_root())}")
            except Exception as ex:
                results["fail"].append((f"{pair_u}/{tf}", str(ex)))
                if verbose:
                    print(f"FAIL ({ex})")

    return results


# ── Comando ───────────────────────────────────────────────────────────────
def cmd_generate_all_csvs(argstr: str = "") -> str:
    pairs, tfs, bars, force_synth = _parse_args(argstr)

    print("\n" + "═" * 66)
    print("  ASTRA · Generador masivo de CSVs Forex")
    print("═" * 66)
    print(f"  Pares       : {', '.join(pairs)}")
    print(f"  Timeframes  : {', '.join(tfs)}")
    print(f"  Velas       : {bars}")
    print(f"  Fuente      : {'sintética (forzada)' if force_synth else 'Yahoo → sintético (fallback)'}")
    print("─" * 66)

    res = generate_all_csvs(pairs=pairs, timeframes=tfs, bars=bars,
                            force_synthetic=force_synth, verbose=True)

    ok, fail = res["ok"], res["fail"]
    by_source: dict = {}
    for _, _, src, _ in ok:
        by_source[src] = by_source.get(src, 0) + 1

    lines = [
        "",
        f"✔ Generados : {len(ok)}",
        *[f"    · {src:>9}: {n}" for src, n in by_source.items()],
        f"✖ Errores  : {len(fail)}",
    ]
    for key, msg in fail[:10]:
        lines.append(f"    · {key}: {msg}")
    if ok:
        root = _project_root()
        sample_dirs = sorted({str(Path(p).parent.relative_to(root)) for _, p, _, _ in ok})
        lines.append("  Rutas destino:")
        for d in sample_dirs:
            lines.append(f"    - {d}/")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(cmd_generate_all_csvs(" ".join(sys.argv[1:])))
