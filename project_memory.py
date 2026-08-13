# project_memory.py
"""
ASTRA — Memoria de Proyectos y Modelos (Fase 1)

Almacena en SQLite (misma memoria.db) el estado de:
  - Modelos entrenados (par, fecha, métricas, ruta)
  - Proyectos / workflows activos
  - Tareas pendientes por proyecto

Tablas nuevas:
  models   — registro de modelos entrenados por par Forex
  projects — proyectos/datasets en progreso
  tasks    — tareas pendientes asociadas a un proyecto

API pública:
  # Modelos
  register_model(pair, csv_path, metrics)     → int (id)
  get_model(pair)                              → dict | None
  list_models()                                → list[dict]
  update_model(pair, metrics)                  → bool

  # Proyectos
  save_project(name, description, status)      → int (id)
  get_project(name)                            → dict | None
  list_projects(status=None)                   → list[dict]
  update_project_status(name, status)          → bool

  # Tareas
  add_task(project_name, description)          → int (id)
  complete_task(task_id)                       → bool
  get_pending_tasks(project_name=None)         → list[dict]

  # Resumen de sesión
  session_summary()                            → str  (para mostrar al inicio)
"""

import sqlite3
import time
import os
from typing import Optional

from runtime_paths import configured_project_path

# Reutiliza la misma memoria.db del proyecto
DB_PATH = str(configured_project_path("ASTRA_MEMORY_DB_PATH", "memoria.db"))


# ══════════════════════════════════════════════════════════════════
#  INIT — Crea tablas si no existen (safe to call on every startup)
# ══════════════════════════════════════════════════════════════════

def init_project_db() -> None:
    """Crea las tablas models, projects y tasks si no existen."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Modelos entrenados ────────────────────────────────────────
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

    # ── Proyectos / datasets ──────────────────────────────────────
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

    # ── Tareas pendientes ─────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(cursor, row) -> dict:
    """Convierte un sqlite3.Row a dict usando los nombres de columna."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# ══════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════

def register_model(
    pair: str,
    csv_path: str = "",
    metrics: dict = None
) -> int:
    """
    Registra o actualiza un modelo entrenado.
    Si el par ya existe en la tabla, actualiza sus métricas.
    Devuelve el id del registro.

    Parámetros de metrics esperados (todos opcionales):
      accuracy, precision, rows_trained, wfv_score, params_saved
    """
    metrics = metrics or {}
    pair    = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    now     = _now()

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("SELECT id FROM models WHERE pair = ?", (pair,))
    existing = c.fetchone()

    if existing:
        c.execute("""
            UPDATE models SET
                csv_path     = ?,
                accuracy     = ?,
                precision    = ?,
                rows_trained = ?,
                wfv_score    = ?,
                params_saved = ?,
                updated_at   = ?
            WHERE pair = ?
        """, (
            csv_path,
            metrics.get("accuracy"),
            metrics.get("precision"),
            metrics.get("rows_trained"),
            metrics.get("wfv_score"),
            int(metrics.get("params_saved", False)),
            now,
            pair,
        ))
        row_id = existing[0]
    else:
        c.execute("""
            INSERT INTO models
                (pair, csv_path, accuracy, precision, rows_trained,
                 wfv_score, params_saved, trained_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pair,
            csv_path,
            metrics.get("accuracy"),
            metrics.get("precision"),
            metrics.get("rows_trained"),
            metrics.get("wfv_score"),
            int(metrics.get("params_saved", False)),
            now,
            now,
        ))
        row_id = c.lastrowid

    conn.commit()
    conn.close()
    return row_id


def get_model(pair: str) -> Optional[dict]:
    """Devuelve el registro de un modelo por par (ej. 'EURUSD')."""
    pair = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM models WHERE pair = ?", (pair,))
    row  = c.fetchone()
    result = _row_to_dict(c, row) if row else None
    conn.close()
    return result


def list_models() -> list:
    """Devuelve todos los modelos registrados, ordenados por updated_at desc."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM models ORDER BY updated_at DESC")
    rows   = c.fetchall()
    result = [_row_to_dict(c, r) for r in rows]
    conn.close()
    return result


def update_model(pair: str, metrics: dict) -> bool:
    """Actualiza métricas de un modelo existente. Devuelve True si encontró el par."""
    pair = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        UPDATE models SET
            accuracy     = ?,
            precision    = ?,
            rows_trained = ?,
            wfv_score    = ?,
            params_saved = ?,
            updated_at   = ?
        WHERE pair = ?
    """, (
        metrics.get("accuracy"),
        metrics.get("precision"),
        metrics.get("rows_trained"),
        metrics.get("wfv_score"),
        int(metrics.get("params_saved", False)),
        _now(),
        pair,
    ))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def delete_model(pair: str) -> bool:
    """Elimina el registro de un modelo. Devuelve True si existía."""
    pair = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("DELETE FROM models WHERE pair = ?", (pair,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ══════════════════════════════════════════════════════════════════
#  PROJECTS
# ══════════════════════════════════════════════════════════════════

def save_project(
    name: str,
    description: str = "",
    status: str = "active"
) -> int:
    """
    Guarda o actualiza un proyecto. Devuelve el id.
    Status: 'active' | 'paused' | 'done'
    """
    now  = _now()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("SELECT id FROM projects WHERE name = ?", (name,))
    existing = c.fetchone()

    if existing:
        c.execute("""
            UPDATE projects SET description = ?, status = ?, updated_at = ?
            WHERE name = ?
        """, (description, status, now, name))
        row_id = existing[0]
    else:
        c.execute("""
            INSERT INTO projects (name, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, status, now, now))
        row_id = c.lastrowid

    conn.commit()
    conn.close()
    return row_id


def get_project(name: str) -> Optional[dict]:
    """Devuelve un proyecto por nombre."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM projects WHERE name = ?", (name,))
    row  = c.fetchone()
    result = _row_to_dict(c, row) if row else None
    conn.close()
    return result


def list_projects(status: str = None) -> list:
    """
    Lista proyectos. Si status='active', filtra solo activos.
    Sin status devuelve todos.
    """
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    if status:
        c.execute(
            "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC",
            (status,)
        )
    else:
        c.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    rows   = c.fetchall()
    result = [_row_to_dict(c, r) for r in rows]
    conn.close()
    return result


def update_project_status(name: str, status: str) -> bool:
    """Actualiza el status de un proyecto. Devuelve True si lo encontró."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute(
        "UPDATE projects SET status = ?, updated_at = ? WHERE name = ?",
        (status, _now(), name)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ══════════════════════════════════════════════════════════════════
#  TASKS
# ══════════════════════════════════════════════════════════════════

def add_task(project_name: str, description: str) -> int:
    """Agrega una tarea pendiente a un proyecto. Devuelve el id."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        INSERT INTO tasks (project_name, description, done, created_at)
        VALUES (?, ?, 0, ?)
    """, (project_name, description, _now()))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def complete_task(task_id: int) -> bool:
    """Marca una tarea como completada. Devuelve True si la encontró."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute(
        "UPDATE tasks SET done = 1, completed_at = ? WHERE id = ?",
        (_now(), task_id)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_pending_tasks(project_name: str = None) -> list:
    """
    Devuelve tareas pendientes (done=0).
    Si project_name se especifica, filtra por proyecto.
    """
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    if project_name:
        c.execute(
            "SELECT * FROM tasks WHERE done = 0 AND project_name = ? ORDER BY created_at",
            (project_name,)
        )
    else:
        c.execute("SELECT * FROM tasks WHERE done = 0 ORDER BY project_name, created_at")
    rows   = c.fetchall()
    result = [_row_to_dict(c, r) for r in rows]
    conn.close()
    return result


def get_all_tasks(project_name: str = None) -> list:
    """Devuelve todas las tareas (pendientes + completadas)."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    if project_name:
        c.execute(
            "SELECT * FROM tasks WHERE project_name = ? ORDER BY created_at",
            (project_name,)
        )
    else:
        c.execute("SELECT * FROM tasks ORDER BY project_name, created_at")
    rows   = c.fetchall()
    result = [_row_to_dict(c, r) for r in rows]
    conn.close()
    return result


# ══════════════════════════════════════════════════════════════════
#  SESSION SUMMARY — se muestra al arrancar ASTRA
# ══════════════════════════════════════════════════════════════════

def session_summary() -> str:
    """
    Genera un resumen compacto del estado actual para mostrar al iniciar.
    Muestra: modelos entrenados, proyectos activos, tareas pendientes.
    """
    from colorama import Fore, Style

    lines = []
    sep   = Fore.GREEN + "─" * 46 + Style.RESET_ALL

    lines.append(sep)
    lines.append(Fore.GREEN + "  📋  ASTRA — Resumen de sesión" + Style.RESET_ALL)
    lines.append(sep)

    # ── Modelos ───────────────────────────────────────────────────
    models = list_models()
    if models:
        lines.append(Fore.CYAN + f"  🤖  Modelos entrenados ({len(models)}):" + Style.RESET_ALL)
        for m in models[:6]:       # máx 6 para no saturar pantalla
            pair  = m.get("pair", "?")
            prec  = m.get("precision")
            acc   = m.get("accuracy")
            date  = (m.get("updated_at") or "")[:10]
            prec_str = f"precision={prec:.2%}" if prec else ""
            acc_str  = f"acc={acc:.2%}"        if acc  else ""
            metric   = "  ".join(filter(None, [prec_str, acc_str]))
            lines.append(f"     {pair:<12}  {metric:<32}  {date}")
        if len(models) > 6:
            lines.append(f"     ... y {len(models)-6} más")
    else:
        lines.append(Fore.YELLOW + "  🤖  Sin modelos entrenados aún." + Style.RESET_ALL)

    # ── Proyectos activos ─────────────────────────────────────────
    projects = list_projects(status="active")
    if projects:
        lines.append("")
        lines.append(Fore.CYAN + f"  📁  Proyectos activos ({len(projects)}):" + Style.RESET_ALL)
        for p in projects[:4]:
            name = p.get("name", "?")
            desc = (p.get("description") or "")[:45]
            lines.append(f"     {name:<20}  {desc}")

    # ── Tareas pendientes ─────────────────────────────────────────
    tasks = get_pending_tasks()
    if tasks:
        lines.append("")
        lines.append(Fore.CYAN + f"  ✅  Tareas pendientes ({len(tasks)}):" + Style.RESET_ALL)
        for t in tasks[:5]:
            proj = t.get("project_name", "?")
            desc = (t.get("description") or "")[:50]
            lines.append(f"     [{t['id']}] {proj:<14}  {desc}")
        if len(tasks) > 5:
            lines.append(f"     ... y {len(tasks)-5} más (usa 'tareas' para ver todas)")

    lines.append(sep)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  COMANDOS CLI (devuelven strings para _print_result)
# ══════════════════════════════════════════════════════════════════

def cmd_list_models() -> str:
    """Comando: 'mis modelos' / 'list models'"""
    models = list_models()
    if not models:
        return "No hay modelos registrados aún. Entrena uno con: train forex <archivo.csv>"

    from colorama import Fore, Style
    lines = [Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL,
             Fore.GREEN + "  MODELOS ENTRENADOS" + Style.RESET_ALL,
             Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL]

    for m in models:
        pair  = m.get("pair", "?")
        prec  = m.get("precision")
        acc   = m.get("accuracy")
        rows  = m.get("rows_trained")
        wfv   = m.get("wfv_score")
        date  = (m.get("updated_at") or "")[:16]
        saved = "✅ params" if m.get("params_saved") else ""

        lines.append(f"\n  {Fore.CYAN}{pair}{Style.RESET_ALL}")
        if prec  is not None: lines.append(f"    Precision    : {prec:.2%}")
        if acc   is not None: lines.append(f"    Accuracy     : {acc:.2%}")
        if rows  is not None: lines.append(f"    Filas usadas : {rows:,}")
        if wfv   is not None: lines.append(f"    WFV score    : {wfv:.4f}")
        if saved:              lines.append(f"    Optuna       : {saved}")
        lines.append(f"    Actualizado  : {date}")

    return "\n".join(lines)


def cmd_list_projects() -> str:
    """Comando: 'mis proyectos' / 'list projects'"""
    projects = list_projects()
    if not projects:
        return "No hay proyectos registrados. Crea uno con: nuevo proyecto <nombre> <descripción>"

    from colorama import Fore, Style
    STATUS_COLOR = {
        "active": Fore.GREEN,
        "paused": Fore.YELLOW,
        "done":   Fore.CYAN,
    }

    lines = [Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL,
             Fore.GREEN + "  PROYECTOS" + Style.RESET_ALL,
             Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL]

    for p in projects:
        name  = p.get("name", "?")
        desc  = (p.get("description") or "sin descripción")[:60]
        stat  = p.get("status", "active")
        color = STATUS_COLOR.get(stat, Fore.WHITE)
        date  = (p.get("updated_at") or "")[:10]
        lines.append(f"\n  {Fore.CYAN}{name}{Style.RESET_ALL}  {color}[{stat}]{Style.RESET_ALL}  {date}")
        lines.append(f"    {desc}")

    return "\n".join(lines)


def cmd_list_tasks(project_name: str = None) -> str:
    """Comando: 'tareas' / 'tareas <proyecto>'"""
    tasks = get_pending_tasks(project_name)
    if not tasks:
        msg = f"No hay tareas pendientes"
        if project_name:
            msg += f" en '{project_name}'"
        return msg + "."

    from colorama import Fore, Style
    lines = [Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL,
             Fore.GREEN + "  TAREAS PENDIENTES" + Style.RESET_ALL,
             Fore.GREEN + f"{'─'*60}" + Style.RESET_ALL]

    current_proj = None
    for t in tasks:
        proj = t.get("project_name", "?")
        if proj != current_proj:
            lines.append(f"\n  {Fore.CYAN}{proj}{Style.RESET_ALL}")
            current_proj = proj
        lines.append(f"    [{t['id']}] {t['description']}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  AUTO-REGISTRO desde el pipeline Forex
#  (llamar desde integrated_pipeline.py después de train())
# ══════════════════════════════════════════════════════════════════

def auto_register_forex_model(train_result: dict, csv_path: str = "") -> None:
    """
    Registra automáticamente un modelo después de un entrenamiento exitoso.
    Llamar desde _forex_train() en main.py o desde integrated_pipeline.train().

    train_result es el dict que devuelve pipeline.train():
      pair, accuracy, precision, rows_trained, wfv_score (opcional)
    """
    if not isinstance(train_result, dict):
        return
    if "error" in train_result:
        return

    pair = train_result.get("pair", "")
    if not pair:
        return

    register_model(
        pair     = pair,
        csv_path = csv_path,
        metrics  = {
            "accuracy":     train_result.get("accuracy"),
            "precision":    train_result.get("precision"),
            "rows_trained": train_result.get("rows_trained"),
            "wfv_score":    train_result.get("wfv_score"),
            "params_saved": train_result.get("params_saved", False),
        }
    )
