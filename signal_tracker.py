# signal_tracker.py
"""
ASTRA Forex — Signal Tracker (Fase 2)

Historial persistente de señales BUY/SELL/HOLD generadas por el predictor.
Almacenado en la misma memoria.db (tabla: forex_signals).

API pública:
  save_signal(signal_dict)              → int (id)
  get_signals(pair, limit, action)      → list[dict]
  get_last_signal(pair)                 → dict | None
  signal_stats(pair)                    → dict
  cmd_signal_history(pair, limit)       → str (para _print_result)
  cmd_signal_stats(pair)                → str
"""

import sqlite3
import time
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria.db")


# ══════════════════════════════════════════════════════════
#  INIT
# ══════════════════════════════════════════════════════════

def init_signal_db() -> None:
    """Crea la tabla forex_signals si no existe. Seguro llamar en cada inicio."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS forex_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pair            TEXT    NOT NULL,
            action          TEXT    NOT NULL,
            direction       TEXT,
            confidence      REAL,
            signal_strength REAL,
            adx             REAL,
            regime          TEXT,
            hold_reason     TEXT,
            csv_path        TEXT,
            generated_at    TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(cursor, row) -> dict:
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# ══════════════════════════════════════════════════════════
#  GUARDAR
# ══════════════════════════════════════════════════════════

def save_signal(signal: dict, csv_path: str = "") -> int:
    """
    Guarda una señal generada por el predictor.
    signal es el dict que devuelve ForexPredictor.signal() o
    ForexIntegratedPipeline.predict():
      pair, action, direction, confidence, signal_strength, adx, regime, hold_reason
    Devuelve el id del registro.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO forex_signals
            (pair, action, direction, confidence, signal_strength,
             adx, regime, hold_reason, csv_path, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        (signal.get("pair") or "UNKNOWN").upper().replace("/", "").replace("_", ""),
        signal.get("action",          "HOLD"),
        signal.get("direction",       ""),
        signal.get("confidence"),
        signal.get("signal_strength"),
        signal.get("adx"),
        signal.get("regime",          ""),
        signal.get("hold_reason",     ""),
        csv_path,
        _now(),
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


# ══════════════════════════════════════════════════════════
#  CONSULTAR
# ══════════════════════════════════════════════════════════

def get_signals(
    pair: str = None,
    limit: int = 20,
    action: str = None,
) -> list:
    """
    Devuelve señales históricas, las más recientes primero.
    Filtra por par y/o acción si se especifican.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    conditions = []
    params = []

    if pair:
        clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        conditions.append("pair = ?")
        params.append(clean)

    if action:
        conditions.append("action = ?")
        params.append(action.upper())

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    c.execute(
        f"SELECT * FROM forex_signals {where} ORDER BY id DESC LIMIT ?",
        params,
    )
    rows = c.fetchall()
    result = [_row_to_dict(c, r) for r in rows]
    conn.close()
    return result


def get_last_signal(pair: str) -> Optional[dict]:
    """Devuelve la señal más reciente de un par."""
    clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT * FROM forex_signals WHERE pair = ? ORDER BY id DESC LIMIT 1",
        (clean,),
    )
    row = c.fetchone()
    result = _row_to_dict(c, row) if row else None
    conn.close()
    return result


def signal_stats(pair: str = None) -> dict:
    """
    Estadísticas de señales: total, BUY/SELL/HOLD count,
    avg confidence, avg signal_strength.
    Si pair=None, estadísticas globales.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    base_where = "WHERE pair = ?" if pair else ""
    base_params = [pair.upper().replace("/","").replace("_","").replace("-","")
                   ] if pair else []

    c.execute(f"SELECT COUNT(*) FROM forex_signals {base_where}", base_params)
    total = c.fetchone()[0]

    stats = {"total": total, "by_action": {}, "avg_confidence": None, "avg_strength": None}

    for action in ["BUY", "SELL", "HOLD"]:
        extra = f" AND action = '{action}'" if pair else f" WHERE action = '{action}'"
        c.execute(
            f"SELECT COUNT(*) FROM forex_signals {base_where}{extra}",
            base_params,
        )
        stats["by_action"][action] = c.fetchone()[0]

    if total > 0:
        c.execute(
            f"SELECT AVG(confidence), AVG(signal_strength) FROM forex_signals {base_where}",
            base_params,
        )
        row = c.fetchone()
        stats["avg_confidence"] = round(row[0], 4) if row[0] else None
        stats["avg_strength"]   = round(row[1], 2) if row[1] else None

    conn.close()
    return stats


# ══════════════════════════════════════════════════════════
#  COMANDOS CLI
# ══════════════════════════════════════════════════════════

def cmd_signal_history(pair: str = None, limit: int = 10) -> str:
    """Comando: 'señales <par>' / 'signals <par>'"""
    signals = get_signals(pair=pair, limit=limit)

    if not signals:
        msg = f"No hay señales registradas"
        if pair:
            msg += f" para {pair.upper()}"
        return msg + ". Genera una con: predict forex <csv>"

    from colorama import Fore, Style

    ACTION_COLOR = {
        "BUY":  Fore.GREEN,
        "SELL": Fore.RED,
        "HOLD": Fore.YELLOW,
    }
    ACTION_ICON = {"BUY": "▲", "SELL": "▼", "HOLD": "─"}

    header = pair.upper() if pair else "TODOS LOS PARES"
    lines = [
        Fore.GREEN + f"{'─'*64}" + Style.RESET_ALL,
        Fore.GREEN + f"  HISTORIAL DE SEÑALES — {header} (últimas {len(signals)})" + Style.RESET_ALL,
        Fore.GREEN + f"{'─'*64}" + Style.RESET_ALL,
    ]

    for s in signals:
        action = s.get("action", "HOLD")
        pair_s = s.get("pair", "?")
        conf   = s.get("confidence") or 0
        adx    = s.get("adx")       or 0
        str_   = s.get("signal_strength") or 0
        regime = (s.get("regime") or "")[:14]
        date   = (s.get("generated_at") or "")[:16]
        color  = ACTION_COLOR.get(action, Fore.WHITE)
        icon   = ACTION_ICON.get(action, "─")

        bar_n = int(str_ / 10)
        bar   = "█" * bar_n + "░" * (10 - bar_n)

        line = (
            f"  {color}{icon}  {pair_s:<10}{Style.RESET_ALL} "
            f"{color}{action:<5}{Style.RESET_ALL}  "
            f"conf={conf:.2f}  [{bar}]{str_:5.1f}  "
            f"adx={adx:5.1f}  {regime:<14}  {date}"
        )

        if action == "HOLD" and s.get("hold_reason"):
            reason = (s["hold_reason"] or "")[:55]
            line += f"\n         {Fore.YELLOW}↳ {reason}{Style.RESET_ALL}"

        lines.append(line)

    return "\n".join(lines)


def cmd_signal_stats(pair: str = None) -> str:
    """Comando: 'stats señales' / 'stats señales <par>'"""
    stats = signal_stats(pair=pair)

    if stats["total"] == 0:
        return "No hay señales registradas aún."

    from colorama import Fore, Style

    header = pair.upper() if pair else "GLOBAL"
    lines = [
        Fore.GREEN + f"  ESTADÍSTICAS DE SEÑALES — {header}" + Style.RESET_ALL,
        f"  Total señales  : {stats['total']}",
    ]
    by = stats.get("by_action", {})
    lines.append(
        f"  BUY/SELL/HOLD  : "
        f"{Fore.GREEN}{by.get('BUY',0)}{Style.RESET_ALL} / "
        f"{Fore.RED}{by.get('SELL',0)}{Style.RESET_ALL} / "
        f"{Fore.YELLOW}{by.get('HOLD',0)}{Style.RESET_ALL}"
    )
    if stats["avg_confidence"]:
        lines.append(f"  Avg confidence : {stats['avg_confidence']:.2%}")
    if stats["avg_strength"]:
        lines.append(f"  Avg strength   : {stats['avg_strength']:.1f}/100")

    return "\n".join(lines)
