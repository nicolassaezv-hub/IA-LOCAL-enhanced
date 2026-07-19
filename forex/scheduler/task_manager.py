"""
V.12 — Scheduler Inteligente
============================
Planificador interno que orquesta todos los procesos automaticos de ASTRA.
Coordina tareas periodicas y responde a eventos (nueva vela, regimen cambiado,
modelo degradado).

Integracion:
    from forex.scheduler.task_manager import TaskManager
    mgr = TaskManager()
    mgr.register("dataset_update", interval=3600, func=update_func)
    mgr.start()
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

try:
    from colorama import Fore, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

if HAS_COLOR:
    _C = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _B = lambda s: f"{Fore.BLUE}{s}{Style.RESET_ALL}"
    _D = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
else:
    _C = _G = _Y = _R = _B = _D = lambda s: s


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Task:
    name: str
    func: Callable
    interval_sec: int = 3600
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    last_status: TaskStatus = TaskStatus.PENDING
    last_error: str = ""
    run_count: int = 0
    error_count: int = 0
    max_retries: int = 3
    retry_delay: int = 60
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "interval_sec": self.interval_sec,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_status": self.last_status.value,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }


@dataclass
class TaskResult:
    task_name: str
    success: bool
    duration_sec: float
    error: str = ""
    output: Any = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "success": self.success,
            "duration_sec": round(self.duration_sec, 2),
            "error": self.error,
            "timestamp": self.timestamp,
        }


class TaskManager:
    """Gestor de tareas periodicas con retry y backoff."""

    def __init__(self, db_path: str = "memoria.db"):
        self.db_path = db_path
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT,
                    success INTEGER,
                    duration_sec REAL,
                    error TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    task_name TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 1,
                    interval_sec INTEGER,
                    last_run TEXT,
                    next_run TEXT,
                    run_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Register a task ──
    def register(
        self,
        name: str,
        func: Callable,
        interval_sec: int = 3600,
        enabled: bool = True,
        args: tuple = (),
        kwargs: dict | None = None,
        max_retries: int = 3,
        retry_delay: int = 60,
    ) -> Task:
        task = Task(
            name=name,
            func=func,
            interval_sec=interval_sec,
            enabled=enabled,
            args=args,
            kwargs=kwargs or {},
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        task.next_run = datetime.utcnow()
        with self._lock:
            self._tasks[name] = task
        self._persist_state(task)
        return task

    # ── Unregister ──
    def unregister(self, name: str):
        with self._lock:
            self._tasks.pop(name, None)

    # ── Enable/Disable ──
    def enable(self, name: str):
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = True

    def disable(self, name: str):
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = False

    # ── Run a single task ──
    def run_task(self, name: str) -> TaskResult:
        with self._lock:
            task = self._tasks.get(name)
        if task is None:
            return TaskResult(task_name=name, success=False, duration_sec=0.0, error="Task not found", timestamp=datetime.utcnow().isoformat())

        return self._execute_task(task)

    def _execute_task(self, task: Task) -> TaskResult:
        start = time.time()
        task.last_status = TaskStatus.RUNNING
        task.last_error = ""

        for attempt in range(task.max_retries):
            try:
                output = task.func(*task.args, **task.kwargs)
                duration = time.time() - start
                task.last_status = TaskStatus.SUCCESS
                task.last_run = datetime.utcnow()
                task.next_run = task.last_run + timedelta(seconds=task.interval_sec)
                task.run_count += 1
                result = TaskResult(
                    task_name=task.name,
                    success=True,
                    duration_sec=duration,
                    output=output,
                    timestamp=datetime.utcnow().isoformat(),
                )
                self._log_result(result)
                self._persist_state(task)
                return result
            except Exception as e:
                task.last_error = str(e)
                if attempt < task.max_retries - 1:
                    time.sleep(min(task.retry_delay * (2 ** attempt), 300))
                else:
                    task.last_status = TaskStatus.FAILED
                    task.error_count += 1
                    task.last_run = datetime.utcnow()
                    task.next_run = task.last_run + timedelta(seconds=task.interval_sec)
                    duration = time.time() - start
                    result = TaskResult(
                        task_name=task.name,
                        success=False,
                        duration_sec=duration,
                        error=str(e),
                        timestamp=datetime.utcnow().isoformat(),
                    )
                    self._log_result(result)
                    self._persist_state(task)
                    return result

        return TaskResult(task_name=task.name, success=False, duration_sec=0.0, error="Max retries exceeded", timestamp=datetime.utcnow().isoformat())

    # ── Main loop ──
    def _loop(self):
        while self._running:
            now = datetime.utcnow()
            with self._lock:
                tasks_to_run = [
                    t for t in self._tasks.values()
                    if t.enabled and t.next_run and now >= t.next_run
                ]
            for task in tasks_to_run:
                self._execute_task(task)
            time.sleep(5)

    # ── Start/Stop ──
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    # ── Get status ──
    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "task_count": len(self._tasks),
                "tasks": {name: t.to_dict() for name, t in self._tasks.items()},
            }

    def get_task(self, name: str) -> Task | None:
        with self._lock:
            return self._tasks.get(name)

    # ── Persistence ──
    def _persist_state(self, task: Task):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO scheduler_state
                (task_name, enabled, interval_sec, last_run, next_run, run_count, error_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.name,
                int(task.enabled),
                task.interval_sec,
                task.last_run.isoformat() if task.last_run else None,
                task.next_run.isoformat() if task.next_run else None,
                task.run_count,
                task.error_count,
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _log_result(self, result: TaskResult):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO scheduler_log (task_name, success, duration_sec, error, timestamp) VALUES (?, ?, ?, ?, ?)",
                (result.task_name, int(result.success), result.duration_sec, result.error, result.timestamp),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Get log history ──
    def get_log(self, limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT task_name, success, duration_sec, error, timestamp FROM scheduler_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [
                {"task_name": r[0], "success": bool(r[1]), "duration_sec": r[2], "error": r[3], "timestamp": r[4]}
                for r in rows
            ]
        except Exception:
            return []


# ── CLI ──
def cmd_scheduler_status(args: str = "") -> str:
    """Comando CLI: scheduler_status"""
    mgr = TaskManager()
    status = mgr.get_status()
    lines = [f"{_C('Scheduler Status')} — running={status['running']}, tasks={status['task_count']}"]
    for name, t in status["tasks"].items():
        icon = _G("OK") if t["last_status"] == "success" else _R("FAIL") if t["last_status"] == "failed" else _Y("WAIT")
        lines.append(f"  {icon} {name}: interval={t['interval_sec']}s, runs={t['run_count']}, errors={t['error_count']}, next={t['next_run']}")
    return "\n".join(lines)


if __name__ == "__main__":
    def dummy():
        print("Task executed")
        return "ok"

    mgr = TaskManager()
    mgr.register("test", dummy, interval_sec=5)
    mgr.start()
    time.sleep(8)
    mgr.stop()
    print(cmd_scheduler_status())
