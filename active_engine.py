# active_engine.py
"""
ASTRA — Active Engine (Fase 3)

Scheduler liviano basado en la librería `schedule`.
Corre en un thread daemon independiente dentro del mismo proceso de main.py.
100% compatible con Windows — sin cron, sin servicios externos.

Casos de uso:
  - Re-evaluar un par Forex cada N minutos/horas
  - Re-entrenar un modelo cuando llega nueva data
  - Tareas periódicas personalizadas (cualquier callable)

API pública:
  engine = get_engine()             — instancia global (singleton)
  engine.start()                    — lanza el thread del scheduler
  engine.stop()                     — detiene el thread
  engine.schedule_forex(pair, csv, interval_min)  — tarea Forex periódica
  engine.schedule_task(name, fn, interval_min)    — tarea genérica
  engine.cancel(name)               — cancela una tarea por nombre
  engine.list_jobs()                → list[dict]  — trabajos activos
  engine.status()                   → str  — para _print_result

Comandos CLI (para main.py):
  schedule forex <par> <csv> [min]  — evaluar señal cada N minutos
  schedule stop <nombre>            — cancelar trabajo
  schedule stop all                 — cancelar todos
  schedule status                   — ver trabajos activos
  schedule run <nombre>             — forzar ejecución inmediata
"""

import threading
import time
import os
from typing import Callable, Dict, List, Optional

from colorama import Fore, Style

# Circuit breaker y position sizing
try:
    from forex.prediction.circuit_breaker import get_circuit_breaker
    from forex.prediction.position_sizing import PositionSizer
    _HAS_RISK_MODULES = True
except ImportError:
    _HAS_RISK_MODULES = False

try:
    import schedule as _schedule
    HAS_SCHEDULE = True
except ImportError:
    _schedule = None
    HAS_SCHEDULE = False


# ══════════════════════════════════════════════════════════
#  ACTIVE ENGINE
# ══════════════════════════════════════════════════════════

class ActiveEngine:
    """
    Wrapper sobre `schedule` que corre en un thread daemon.
    Mantiene un registro de trabajos con nombre para poder
    cancelarlos individualmente y mostrarlos al usuario.
    """

    def __init__(self):
        self._scheduler = _schedule.Scheduler() if HAS_SCHEDULE else None
        self._jobs:    Dict[str, dict] = {}     # name → {job, fn, interval, desc}
        self._thread:  Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock     = threading.Lock()

    # ──────────────────────────────────────────────────────
    #  Thread loop
    # ──────────────────────────────────────────────────────
    def start(self) -> str:
        """Lanza el thread del scheduler. No-op si ya está corriendo."""
        if not HAS_SCHEDULE:
            return (
                Fore.RED +
                "[ENGINE] 'schedule' no instalado. Ejecuta: pip install schedule" +
                Style.RESET_ALL
            )

        if self._thread and self._thread.is_alive():
            return Fore.YELLOW + "[ENGINE] Ya está corriendo." + Style.RESET_ALL

        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="active_engine",
        )
        self._thread.start()
        return Fore.GREEN + "[ENGINE] Active Engine iniciado." + Style.RESET_ALL

    def _run_loop(self) -> None:
        print(Fore.CYAN + "[ENGINE] Scheduler loop activo." + Style.RESET_ALL)
        while not self._stop_evt.is_set():
            if self._scheduler:
                self._scheduler.run_pending()
            self._stop_evt.wait(1)   # chequeo cada segundo, sin busy-wait
        print(Fore.YELLOW + "[ENGINE] Scheduler loop detenido." + Style.RESET_ALL)

    def stop(self) -> str:
        """Detiene el thread. Los trabajos registrados se conservan en memoria."""
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=3)
        with self._lock:
            if self._scheduler:
                self._scheduler.clear()
            self._jobs.clear()
        return "[ENGINE] Active Engine detenido."

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ──────────────────────────────────────────────────────
    #  Tarea Forex periódica
    # ──────────────────────────────────────────────────────
    def schedule_forex(
        self,
        pair:         str,
        csv_path:     str,
        interval_min: int  = 60,
    ) -> str:
        """
        Evalúa señal Forex cada `interval_min` minutos.
        Guarda la señal en signal_tracker automáticamente.
        Si el par ya tiene trabajo activo, lo reemplaza.
        """
        if not HAS_SCHEDULE:
            return Fore.RED + "[ENGINE] 'schedule' no disponible." + Style.RESET_ALL

        csv_path = os.path.normpath(csv_path)
        if not os.path.isfile(csv_path):
            return (
                f"[ENGINE] CSV no encontrado: {csv_path}\n"
                f"  Genera datos con: python creando.py --modo yfinance --pares {pair.upper()}"
            )

        clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        name  = f"forex_{clean}"

        def _forex_job():
            ts = time.strftime("%H:%M:%S")
            print(Fore.CYAN + f"[ENGINE:{ts}] Evaluando {clean}..." + Style.RESET_ALL)
            try:
                # ── CIRCUIT BREAKER — verificar antes de operar ────────
                if _HAS_RISK_MODULES:
                    cb     = get_circuit_breaker()
                    status = cb.check()
                    if not status["open"]:
                        print(Fore.RED + f"[ENGINE:{ts}] CIRCUIT BREAKER ACTIVO — {status['reason']}" + Style.RESET_ALL)
                        print(Fore.RED + f"  Cooldown restante: {status['cooldown_remaining_h']:.1f}h" + Style.RESET_ALL)
                        return

                from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
                pipeline = ForexIntegratedPipeline()
                result   = pipeline.predict(csv_path, pair=clean)

                if isinstance(result, dict) and "error" not in result:
                    action = result.get("action", "HOLD")
                    conf   = result.get("confidence", 0)
                    adx    = result.get("adx", 0)
                    # ── POSITION SIZING ───────────────────────────────
                    sizing_info = ""
                    if _HAS_RISK_MODULES and action in ("BUY", "SELL"):
                        try:
                            from signal_tracker import get_signals as _gs
                            hist = _gs(pair=clean, limit=200)
                            trade_hist = [{"pnl": h.get("pnl", 0)} for h in hist if "pnl" in h]
                            sizing = PositionSizer(account_balance=10_000).calculate(result, trade_hist)
                            sizing_info = f"  Risk={sizing['risk_pct']:.2f}%  ${sizing['risk_usd']:.0f}  [{sizing['method']}]"
                        except Exception as _e:
                            import logging as _l
                            _l.getLogger("astra.engine").debug("PositionSizer error: %s", _e)

                    # Guardar en historial
                    try:
                        from signal_tracker import save_signal
                        save_signal(result, csv_path)
                    except Exception as _e:
                        import logging as _l
                        _l.getLogger("astra.engine").debug("Signal save error: %s", _e)
                    # Notificar solo si BUY o SELL
                    COLOR = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}
                    ICON  = {"BUY": "▲", "SELL": "▼", "HOLD": "─"}
                    color = COLOR.get(action, Fore.WHITE)
                    icon  = ICON.get(action, "─")
                    if action in ("BUY", "SELL"):
                        print(
                            f"\n{color}{'═'*54}{Style.RESET_ALL}\n"
                            f"  {color}{icon}  SEÑAL {action} — {clean}  [{ts}]{Style.RESET_ALL}\n"
                            f"  confidence={conf:.2%}  adx={adx:.1f}\n"
                            f"{sizing_info}\n"
                            f"{color}{'═'*54}{Style.RESET_ALL}\n"
                        )
                    else:
                        reason = (result.get("hold_reason") or "")[:55]
                        print(Fore.YELLOW + f"  ─  {clean}  HOLD  [{ts}]  {reason}" + Style.RESET_ALL)
                else:
                    err = result.get("error", "desconocido") if isinstance(result, dict) else str(result)
                    print(Fore.RED + f"[ENGINE:{ts}] {clean} error: {err}" + Style.RESET_ALL)

            except Exception as e:
                print(Fore.RED + f"[ENGINE:{ts}] {clean} excepción: {e}" + Style.RESET_ALL)

        return self._register_job(
            name         = name,
            fn           = _forex_job,
            interval_min = interval_min,
            description  = f"Forex signal {clean} — {os.path.basename(csv_path)}",
        )

    # ──────────────────────────────────────────────────────
    #  Tarea genérica
    # ──────────────────────────────────────────────────────
    def schedule_task(
        self,
        name:         str,
        fn:           Callable,
        interval_min: int,
        description:  str = "",
    ) -> str:
        """Registra cualquier callable para ejecutarse cada `interval_min` minutos."""
        return self._register_job(name, fn, interval_min, description)

    # ──────────────────────────────────────────────────────
    #  Registro interno
    # ──────────────────────────────────────────────────────
    def _register_job(
        self,
        name:         str,
        fn:           Callable,
        interval_min: int,
        description:  str = "",
    ) -> str:
        if not HAS_SCHEDULE or not self._scheduler:
            return Fore.RED + "[ENGINE] schedule no disponible." + Style.RESET_ALL

        with self._lock:
            # Cancelar trabajo previo con el mismo nombre
            if name in self._jobs:
                old_job = self._jobs[name]["job"]
                self._scheduler.cancel_job(old_job)

            # Registrar nuevo job
            job = self._scheduler.every(interval_min).minutes.do(fn)

            self._jobs[name] = {
                "job":         job,
                "fn":          fn,
                "interval":    interval_min,
                "description": description,
                "created_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
                "next_run":    str(job.next_run) if job.next_run else "—",
            }

        # Auto-start si no está corriendo
        if not self.is_running:
            self.start()

        return (
            Fore.GREEN +
            f"[ENGINE] '{name}' programado — cada {interval_min} min. "
            f"Siguiente ejecución: {self._jobs[name]['next_run']}" +
            Style.RESET_ALL
        )

    # ──────────────────────────────────────────────────────
    #  Cancelar
    # ──────────────────────────────────────────────────────
    def cancel(self, name: str) -> str:
        """Cancela un trabajo por nombre."""
        if name.lower() == "all":
            return self._cancel_all()

        with self._lock:
            if name not in self._jobs:
                return f"[ENGINE] Trabajo '{name}' no encontrado."
            job = self._jobs[name]["job"]
            self._scheduler.cancel_job(job)
            del self._jobs[name]

        return f"[ENGINE] Trabajo '{name}' cancelado."

    def _cancel_all(self) -> str:
        with self._lock:
            count = len(self._jobs)
            if self._scheduler:
                self._scheduler.clear()
            self._jobs.clear()
        return f"[ENGINE] {count} trabajo(s) cancelado(s)."

    # ──────────────────────────────────────────────────────
    #  Forzar ejecución inmediata
    # ──────────────────────────────────────────────────────
    def run_now(self, name: str) -> str:
        """Ejecuta un trabajo inmediatamente sin esperar su próximo turno."""
        with self._lock:
            if name not in self._jobs:
                return f"[ENGINE] Trabajo '{name}' no encontrado."
            fn = self._jobs[name]["fn"]

        try:
            print(Fore.CYAN + f"[ENGINE] Ejecutando '{name}' manualmente..." + Style.RESET_ALL)
            fn()
            return f"[ENGINE] '{name}' ejecutado."
        except Exception as e:
            return f"[ENGINE] Error ejecutando '{name}': {e}"

    # ──────────────────────────────────────────────────────
    #  Estado
    # ──────────────────────────────────────────────────────
    def list_jobs(self) -> List[dict]:
        with self._lock:
            # Actualizar next_run desde schedule
            for name, info in self._jobs.items():
                job = info["job"]
                info["next_run"] = str(job.next_run) if job.next_run else "—"
            return list(self._jobs.values())

    def status(self) -> str:
        """Devuelve string con el estado del engine y los trabajos activos."""
        running_str = (
            Fore.GREEN + "corriendo" + Style.RESET_ALL if self.is_running
            else Fore.YELLOW + "detenido" + Style.RESET_ALL
        )

        jobs = self.list_jobs()

        if not jobs:
            return (
                f"[ENGINE] Estado: {running_str}\n"
                f"  Sin trabajos programados. Usa: schedule forex <par> <csv> [min]"
            )

        lines = [
            Fore.GREEN + f"  {'─'*58}" + Style.RESET_ALL,
            f"  ACTIVE ENGINE — {running_str}  ({len(jobs)} trabajo(s))",
            Fore.GREEN + f"  {'─'*58}" + Style.RESET_ALL,
        ]

        for info in jobs:
            # extraer nombre desde descripción o job tag
            desc  = info.get("description", "")
            intv  = info.get("interval", "?")
            nxt   = (info.get("next_run") or "—")[:19]
            lines.append(
                f"  {Fore.CYAN}{desc:<40}{Style.RESET_ALL}  "
                f"cada {intv:>3}min  próximo: {nxt}"
            )

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  SINGLETON GLOBAL
# ══════════════════════════════════════════════════════════

_engine_instance: Optional[ActiveEngine] = None


def get_engine() -> ActiveEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ActiveEngine()
    return _engine_instance


# ══════════════════════════════════════════════════════════
#  FUNCIONES CLI PARA main.py
# ══════════════════════════════════════════════════════════

def cmd_schedule_forex(pair: str, csv_path: str, interval_min: int = 60) -> str:
    """Comando: 'schedule forex <par> <csv> [min]'"""
    engine = get_engine()
    return engine.schedule_forex(pair, csv_path, interval_min)


def cmd_schedule_stop(name: str) -> str:
    """Comando: 'schedule stop <nombre>' / 'schedule stop all'"""
    return get_engine().cancel(name)


def cmd_schedule_status() -> str:
    """Comando: 'schedule status'"""
    return get_engine().status()


def cmd_schedule_run(name: str) -> str:
    """Comando: 'schedule run <nombre>' — forzar ejecución inmediata"""
    return get_engine().run_now(name)
