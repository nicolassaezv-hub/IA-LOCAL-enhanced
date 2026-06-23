# memory.py
import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria.db")


def init_db():
    """Inicializa la base de datos SQLite para guardar memoria de la IA."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS memoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_input TEXT,
                    ai_response TEXT,
                    timestamp TEXT
                )""")
    conn.commit()
    conn.close()


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
