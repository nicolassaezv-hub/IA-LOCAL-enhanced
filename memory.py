# memory.py
"""
ASTRA — Memoria SQLite principal.

Tabla original:
  memoria  — historial de conversaciones (user_input / ai_response)

Fase 1: init_db() ahora también inicializa las tablas de project_memory
(models, projects, tasks) para que existan desde el primer arranque.
"""

import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria.db")


def init_db():
    """
    Inicializa la base de datos SQLite.
    Crea la tabla de conversaciones Y las tablas de project_memory
    (models, projects, tasks) si no existen.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Conversaciones (tabla original) ──────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS memoria (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_input  TEXT,
            ai_response TEXT,
            timestamp   TEXT
        )
    """)

    # ── Modelos Forex entrenados (Fase 1) ─────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pair          TEXT    NOT NULL,
            csv_path      TEXT,
            accuracy      REAL,
            precision     REAL,
            rows_trained  INTEGER,
            wfv_score     REAL,
            params_saved  INTEGER DEFAULT 0,
            trained_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        )
    """)

    # ── Proyectos / datasets (Fase 1) ─────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT,
            status      TEXT    DEFAULT 'active',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        )
    """)

    # ── Tareas pendientes (Fase 1) ────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            done         INTEGER DEFAULT 0,
            created_at   TEXT    NOT NULL,
            completed_at TEXT
        )
    """)

    # ── Registro de comandos ejecutados ──────────────────────────
    # Almacena cada comando con su resultado resumido para que el LLM
    # sepa qué acciones ejecutó el usuario sin necesidad de re-ejecutar.
    c.execute("""
        CREATE TABLE IF NOT EXISTS command_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            command     TEXT    NOT NULL,
            summary     TEXT    NOT NULL,
            pair        TEXT,
            category    TEXT,
            executed_at TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    # Asegurar que project_memory también inicializa sus índices
    try:
        from project_memory import init_project_db
        init_project_db()
    except Exception:
        pass


def guardar_memoria(user_input, ai_response):
    """Guarda una interacción en la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO memoria (user_input, ai_response, timestamp) VALUES (?, ?, ?)",
        (user_input, ai_response, time.ctime()),
    )
    conn.commit()
    conn.close()


def cargar_memoria(limit=10):
    """Carga las últimas interacciones como texto plano (para display)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_input, ai_response FROM memoria ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    memoria = ""
    for u, a in rows[::-1]:
        memoria += f"Tú: {u}\nASTRA: {a}\n"
    return memoria


def cargar_turnos(limit=8):
    """
    Devuelve las últimas `limit` interacciones como lista de dicts
    con formato role/content — listo para inyectar en la API de chat.

    Ejemplo de salida:
      [
        {"role": "user",      "content": "analiza negocio ventas.csv"},
        {"role": "assistant", "content": "Health score: 72/100 ..."},
        ...
      ]
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_input, ai_response FROM memoria ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()

    turns = []
    for u, a in rows[::-1]:
        turns.append({"role": "user",      "content": u})
        turns.append({"role": "assistant", "content": a})
    return turns


def contar_entradas() -> int:
    """Devuelve el número total de entradas en la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM memoria")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════
#  COMMAND LOG — registro de comandos con resultado
# ══════════════════════════════════════════════════════════

def log_command(command: str, summary: str, pair: str = None, category: str = "general") -> int:
    """
    Registra un comando ejecutado con su resultado resumido.
    Esto permite que el LLM sepa qué acciones se realizaron
    sin necesidad de repetirlas.

    Parameters
    ----------
    command  : str — comando tal como lo escribió el usuario
    summary  : str — resultado resumido (máx 500 chars)
    pair     : str — par Forex si aplica
    category : str — "forex", "risk", "model", "system", "general"

    Returns
    -------
    int — id del registro
    """
    # Recortar summary a 500 chars para no saturar el contexto
    summary_short = str(summary)[:500].replace("\033[", "").replace("[0m", "")
    # Limpiar códigos ANSI
    import re
    summary_short = re.sub(r'\x1b\[[0-9;]*m', '', summary_short)
    summary_short = re.sub(r'\[\d+[mA-Z]', '', summary_short)

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute(
        """INSERT INTO command_log (command, summary, pair, category, executed_at)
           VALUES (?, ?, ?, ?, ?)""",
        (command, summary_short.strip(), pair, category, time.ctime())
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_command_log(limit: int = 10, category: str = None, pair: str = None) -> list:
    """
    Devuelve los últimos N comandos registrados, opcionalmente filtrados.
    """
    conn  = sqlite3.connect(DB_PATH)
    c     = conn.cursor()
    where = []
    params = []
    if category:
        where.append("category = ?")
        params.append(category)
    if pair:
        where.append("pair = ?")
        params.append(pair.upper())
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    c.execute(
        f"""SELECT command, summary, pair, category, executed_at
            FROM command_log {where_clause}
            ORDER BY id DESC LIMIT ?""",
        params
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"command": r[0], "summary": r[1], "pair": r[2],
         "category": r[3], "executed_at": r[4]}
        for r in reversed(rows)
    ]


def get_command_context_for_llm(limit: int = 6) -> str:
    """
    Devuelve los últimos comandos como bloque de texto para inyectar
    en el prompt del LLM. Así ASTRA sabe qué ejecutaste recientemente.
    """
    entries = get_command_log(limit=limit)
    if not entries:
        return ""
    lines = ["=== ACCIONES RECIENTES DEL USUARIO ==="]
    for e in entries:
        pair_tag = f" [{e['pair']}]" if e["pair"] else ""
        lines.append(f"[{e['executed_at']}]{pair_tag} {e['command']}")
        lines.append(f"  → {e['summary']}")
    lines.append("=== FIN ACCIONES ===")
    return "\n".join(lines)
