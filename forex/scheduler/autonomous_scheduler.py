"""
VI.5.A — Autonomous Scheduler
Scheduler H1/H4/D1 para operación 24/7 (local o en Oracle Cloud).
Ejecuta ciclos de: actualizar CSV → Quality Gate → Predecir → Notificar.
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_TIMEFRAME_SECONDS = {
    "M1":  60,
    "M5":  300,
    "M15": 900,
    "M30": 1800,
    "H1":  3600,
    "H4":  14400,
    "D1":  86400,
}


class SchedulerJob:
    """Tarea programada con su propio intervalo."""

    def __init__(self, name: str, interval_s: int,
                 fn: Callable, args: tuple = (), kwargs: dict = None):
        self.name = name
        self.interval_s = interval_s
        self.fn = fn
        self.args = args
        self.kwargs = kwargs or {}
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None

    def should_run(self) -> bool:
        if self.last_run is None:
            return True
        return (datetime.now() - self.last_run).total_seconds() >= self.interval_s

    def execute(self):
        try:
            self.fn(*self.args, **self.kwargs)
            self.last_run = datetime.now()
            self.run_count += 1
            logger.info(f"[Scheduler] {self.name} completado (run #{self.run_count})")
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"[Scheduler] Error en {self.name}: {e}")


class AutonomousScheduler:
    """
    Scheduler de operación continua para ASTRA.
    Diseñado para correr 24/7 en background (local o en Oracle Cloud).
    """

    def __init__(self, tick_interval: float = 5.0):
        self.tick_interval = tick_interval
        self._jobs: list[SchedulerJob] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None

    def add_job(self, name: str, timeframe: str,
                fn: Callable, args: tuple = (), kwargs: dict = None) -> "AutonomousScheduler":
        """Añade una tarea con el intervalo del timeframe dado."""
        interval_s = _TIMEFRAME_SECONDS.get(timeframe.upper(), 3600)
        job = SchedulerJob(name, interval_s, fn, args, kwargs)
        self._jobs.append(job)
        return self

    def add_job_seconds(self, name: str, interval_s: int,
                        fn: Callable, args: tuple = (), kwargs: dict = None) -> "AutonomousScheduler":
        """Añade una tarea con intervalo en segundos."""
        job = SchedulerJob(name, interval_s, fn, args, kwargs)
        self._jobs.append(job)
        return self

    def start(self, daemon: bool = True):
        """Inicia el scheduler en un hilo background."""
        if self._running:
            return
        self._running = True
        self._start_time = datetime.now()
        self._thread = threading.Thread(target=self._loop, daemon=daemon)
        self._thread.start()
        logger.info(f"[Scheduler] Iniciado con {len(self._jobs)} tareas.")

    def stop(self):
        """Detiene el scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("[Scheduler] Detenido.")

    def _loop(self):
        while self._running:
            for job in self._jobs:
                if job.should_run():
                    job.execute()
            time.sleep(self.tick_interval)

    def run_once(self, job_name: str = None):
        """Ejecuta manualmente un job por nombre (o todos si no se especifica)."""
        for job in self._jobs:
            if job_name is None or job.name == job_name:
                job.execute()

    def status(self) -> str:
        lines = ["\n  ⏰ ASTRA Scheduler"]
        if self._start_time:
            uptime = datetime.now() - self._start_time
            lines.append(f"  Estado: {'🟢 Activo' if self._running else '🔴 Detenido'}  "
                         f"| Uptime: {str(uptime).split('.')[0]}")
        else:
            lines.append(f"  Estado: {'🟢 Activo' if self._running else '🔴 No iniciado'}")
        lines.append(f"  Tareas ({len(self._jobs)}):")
        for job in self._jobs:
            last = job.last_run.strftime("%H:%M:%S") if job.last_run else "Nunca"
            next_run_s = max(0, job.interval_s - (
                (datetime.now() - job.last_run).total_seconds() if job.last_run else 0))
            errors = f"  ⚠️ {job.error_count} errores" if job.error_count else ""
            lines.append(
                f"    • {job.name} — intervalo={job.interval_s}s  "
                f"última={last}  próxima en {int(next_run_s)}s{errors}"
            )
        return "\n".join(lines)

    @property
    def is_running(self) -> bool:
        return self._running


_scheduler: Optional[AutonomousScheduler] = None


def get_scheduler() -> AutonomousScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutonomousScheduler()
    return _scheduler
