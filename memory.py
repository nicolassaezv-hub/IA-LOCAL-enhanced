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
    c.execute("INSERT INTO memoria (user_input, ai_response, timestamp) VALUES (?, ?, ?)",
              (user_input, ai_response, time.ctime()))
    conn.commit()
    conn.close()

def cargar_memoria(limit=10):
    """Carga las últimas interacciones guardadas en memoria."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_input, ai_response FROM memoria ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    memoria = ""
    for u, a in rows[::-1]:
        memoria += f"Tú: {u}\nCopilot: {a}\n"
    return memoria
