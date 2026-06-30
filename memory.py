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
