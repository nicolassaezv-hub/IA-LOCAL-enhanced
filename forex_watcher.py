# forex_watcher.py
"""
ASTRA Forex — Watcher de CSV + Monitor de Señales (Fase 2)

Monitorea uno o varios CSVs en un loop continuo.
Cuando detecta un cambio (mtime) o periódicamente, re-ejecuta el predictor
y guarda la señal en signal_tracker.

Diseñado para Windows:
  - Usa os.path.getmtime() puro — sin inotify ni watchdog.
  - Corre en un Thread daemon que vive mientras main.py esté activo.
  - Notificaciones por consola con colorama.
  - Soporte para múltiples pares simultáneos.

API pública:
  ForexWatcher(pairs_config)            — instancia con lista de pares
  watcher.start()                       — lanza el thread en background
  watcher.stop()                        — detiene el loop
  watcher.status()                      → str (estado actual)

pairs_config es una lista de dicts:
  [
    {"pair": "EURUSD", "csv": "CSVs/H1/EURUSD.csv", "interval": 60},
    {"pair": "XAUUSD", "csv": "CSVs/H1/XAUUSD.csv", "interval": 120},
  ]

Comandos CLI (para main.py):
  watch forex <par> <csv> [intervalo]   — arrancar monitoreo
  watch stop <par>                      — detener monitoreo de un par
  watch stop all                        — detener todos
  watch status                          — ver qué pares están activos
"""

import os
import time
import threading
from typing import List, Dict, Optional

from colorama import Fore, Style


# ══════════════════════════════════════════════════════════
#  WATCHER DE UN SOLO PAR
# ══════════════════════════════════════════════════════════

class _PairWatcher:
    """
    Worker interno: monitorea un CSV cada `interval` segundos.
    Si el mtime cambia (CSV actualizado) o si el intervalo se cumple,
    ejecuta el predictor y guarda la señal.
    """

    def __init__(
        self,
        pair:        str,
        csv_path:    str,
        interval:    int  = 60,
        retrain_on_change: bool = True,
    ):
        self.pair       = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        self.csv_path   = csv_path
        self.interval   = max(interval, 10)     # mínimo 10 segundos
        self.retrain    = retrain_on_change
        self._stop_evt  = threading.Event()
        self._last_mtime: float = 0.0
        self._last_signal: Optional[dict] = None

    # ──────────────────────────────────────────────────────
    #  Thread loop
    # ──────────────────────────────────────────────────────
    def run(self) -> None:
        print(
            Fore.CYAN +
            f"[WATCHER] Monitoreando {self.pair} — {self.csv_path} "
            f"(cada {self.interval}s)" +
            Style.RESET_ALL
        )
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception as e:
                print(Fore.RED + f"[WATCHER:{self.pair}] Error: {e}" + Style.RESET_ALL)
            self._stop_evt.wait(self.interval)

        print(Fore.YELLOW + f"[WATCHER] {self.pair} detenido." + Style.RESET_ALL)

    # ──────────────────────────────────────────────────────
    #  Un ciclo de evaluación
    # ──────────────────────────────────────────────────────
    def _tick(self) -> None:
        if not os.path.isfile(self.csv_path):
            print(Fore.YELLOW + f"[WATCHER:{self.pair}] CSV no encontrado: {self.csv_path}" + Style.RESET_ALL)
            return

        current_mtime = os.path.getmtime(self.csv_path)
        csv_changed   = (current_mtime != self._last_mtime)

        # Re-entrenar automáticamente si el CSV cambió
        if csv_changed and self.retrain and self._last_mtime != 0.0:
            print(
                Fore.CYAN +
                f"[WATCHER:{self.pair}] CSV actualizado — re-entrenando modelo..." +
                Style.RESET_ALL
            )
            self._retrain()

        self._last_mtime = current_mtime

        # Generar señal
        signal = self._predict()
        if signal and "error" not in signal:
            self._on_signal(signal, csv_changed)

    # ──────────────────────────────────────────────────────
    #  Predicción
    # ──────────────────────────────────────────────────────
    def _predict(self) -> Optional[dict]:
        try:
            from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
            pipeline = ForexIntegratedPipeline()
            return pipeline.predict(self.csv_path, pair=self.pair)
        except Exception as e:
            print(Fore.RED + f"[WATCHER:{self.pair}] Predicción falló: {e}" + Style.RESET_ALL)
            return None

    # ──────────────────────────────────────────────────────
    #  Re-entrenamiento
    # ──────────────────────────────────────────────────────
    def _retrain(self) -> None:
        try:
            from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
            pipeline = ForexIntegratedPipeline()
            result   = pipeline.train(self.csv_path, pair=self.pair)
            # Registrar en project_memory si disponible
            try:
                from project_memory import auto_register_forex_model
                auto_register_forex_model(result, self.csv_path)
            except Exception:
                pass
            print(
                Fore.GREEN +
                f"[WATCHER:{self.pair}] Re-entrenamiento OK — "
                f"precision={result.get('precision', 0):.2%}" +
                Style.RESET_ALL
            )
        except Exception as e:
            print(Fore.RED + f"[WATCHER:{self.pair}] Re-entrenamiento falló: {e}" + Style.RESET_ALL)

    # ──────────────────────────────────────────────────────
    #  Notificación de señal
    # ──────────────────────────────────────────────────────
    def _on_signal(self, signal: dict, csv_changed: bool) -> None:
        action     = signal.get("action", "HOLD")
        confidence = signal.get("confidence", 0)
        strength   = signal.get("signal_strength", 0)
        adx        = signal.get("adx", 0)
        regime     = signal.get("regime", "")

        # Guardar en historial
        try:
            from signal_tracker import save_signal
            save_signal(signal, self.csv_path)
        except Exception:
            pass

        # Imprimir solo si cambió respecto a la señal anterior
        prev_action = (self._last_signal or {}).get("action")
        signal_changed = (action != prev_action)

        COLOR = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}
        ICON  = {"BUY": "▲", "SELL": "▼", "HOLD": "─"}
        color = COLOR.get(action, Fore.WHITE)
        icon  = ICON.get(action, "─")

        ts = time.strftime("%H:%M:%S")

        if action in ("BUY", "SELL"):
            # Señal activa: siempre mostrar
            bar_n = int(strength / 10)
            bar   = "█" * bar_n + "░" * (10 - bar_n)
            print(
                f"\n{color}{'═'*60}{Style.RESET_ALL}\n"
                f"  {color}{icon}  SEÑAL {action} — {self.pair}  [{ts}]{Style.RESET_ALL}\n"
                f"  Confidence  : {confidence:.2%}  |  Strength: [{bar}]{strength:.1f}\n"
                f"  ADX         : {adx:.1f}  ({regime})\n"
                f"{color}{'═'*60}{Style.RESET_ALL}\n"
            )
        elif signal_changed:
            # HOLD y cambió desde BUY/SELL: notificar
            reason = (signal.get("hold_reason") or "")[:60]
            print(
                Fore.YELLOW +
                f"  ─  {self.pair}  HOLD  [{ts}]  {reason}" +
                Style.RESET_ALL
            )

        self._last_signal = signal

    # ──────────────────────────────────────────────────────
    #  Control
    # ──────────────────────────────────────────────────────
    def stop(self) -> None:
        self._stop_evt.set()

    @property
    def is_running(self) -> bool:
        return not self._stop_evt.is_set()


# ══════════════════════════════════════════════════════════
#  GESTOR DE MÚLTIPLES WATCHERS
# ══════════════════════════════════════════════════════════

class ForexWatcher:
    """
    Gestiona múltiples _PairWatcher, cada uno en su propio thread daemon.
    Thread-safe: usa un lock para acceder al registro de watchers.
    """

    def __init__(self):
        self._watchers: Dict[str, _PairWatcher]  = {}
        self._threads:  Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ──────────────────────────────────────────────────────
    #  Añadir / arrancar un par
    # ──────────────────────────────────────────────────────
    def watch(
        self,
        pair:     str,
        csv_path: str,
        interval: int  = 60,
        retrain:  bool = True,
    ) -> str:
        """
        Arranca el monitoreo de un par.
        Si ya está corriendo, lo reinicia con la nueva config.
        Devuelve mensaje de estado.
        """
        clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")

        # Normalizar ruta Windows/Linux
        csv_path = os.path.normpath(csv_path)

        if not os.path.isfile(csv_path):
            return (
                f"[WATCHER] CSV no encontrado: {csv_path}\n"
                f"  Genera el CSV con: python creando.py --modo yfinance --pares {clean}"
            )

        with self._lock:
            # Detener si ya existía
            if clean in self._watchers:
                self._watchers[clean].stop()

            w = _PairWatcher(clean, csv_path, interval, retrain)
            t = threading.Thread(target=w.run, daemon=True, name=f"watcher_{clean}")
            self._watchers[clean] = w
            self._threads[clean]  = t
            t.start()

        return (
            Fore.GREEN +
            f"[WATCHER] {clean} iniciado — {csv_path} (cada {interval}s)" +
            Style.RESET_ALL
        )

    # ──────────────────────────────────────────────────────
    #  Detener
    # ──────────────────────────────────────────────────────
    def stop(self, pair: str) -> str:
        clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        with self._lock:
            if clean not in self._watchers:
                return f"[WATCHER] {clean} no está siendo monitoreado."
            self._watchers[clean].stop()
            del self._watchers[clean]
            del self._threads[clean]
        return f"[WATCHER] {clean} detenido."

    def stop_all(self) -> str:
        with self._lock:
            pairs = list(self._watchers.keys())
            for p in pairs:
                self._watchers[p].stop()
            self._watchers.clear()
            self._threads.clear()
        return f"[WATCHER] {len(pairs)} watcher(s) detenidos."

    # ──────────────────────────────────────────────────────
    #  Estado
    # ──────────────────────────────────────────────────────
    def status(self) -> str:
        with self._lock:
            active = {p: w for p, w in self._watchers.items() if w.is_running}

        if not active:
            return "No hay pares siendo monitoreados. Usa: watch forex <par> <csv>"

        from colorama import Fore, Style
        lines = [
            Fore.GREEN + f"  PARES EN MONITOREO ({len(active)})" + Style.RESET_ALL
        ]
        for pair, w in active.items():
            lines.append(
                f"  {Fore.CYAN}{pair:<12}{Style.RESET_ALL}  "
                f"{os.path.basename(w.csv_path):<25}  "
                f"cada {w.interval}s"
            )
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────
    #  Conveniencia: forzar un tick inmediato sin esperar el intervalo
    # ──────────────────────────────────────────────────────
    def force_check(self, pair: str) -> str:
        clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        with self._lock:
            w = self._watchers.get(clean)
        if not w:
            return f"[WATCHER] {clean} no está activo."
        try:
            w._tick()
            return f"[WATCHER] {clean} — check forzado completado."
        except Exception as e:
            return f"[WATCHER] {clean} — error en check: {e}"


# ══════════════════════════════════════════════════════════
#  INSTANCIA GLOBAL (importada por main.py)
# ══════════════════════════════════════════════════════════

_watcher_instance: Optional[ForexWatcher] = None


def get_watcher() -> ForexWatcher:
    """Devuelve la instancia global del ForexWatcher (singleton)."""
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = ForexWatcher()
    return _watcher_instance


# ══════════════════════════════════════════════════════════
#  FUNCIONES DE CONVENIENCIA PARA main.py
# ══════════════════════════════════════════════════════════

def cmd_watch_start(pair: str, csv_path: str, interval: int = 60) -> str:
    """Comando: 'watch forex <par> <csv> [intervalo]'"""
    return get_watcher().watch(pair, csv_path, interval)


def cmd_watch_stop(pair: str) -> str:
    """Comando: 'watch stop <par>'"""
    if pair.lower() == "all":
        return get_watcher().stop_all()
    return get_watcher().stop(pair)


def cmd_watch_status() -> str:
    """Comando: 'watch status'"""
    return get_watcher().status()


def cmd_watch_check(pair: str) -> str:
    """Comando: 'watch check <par>' — fuerza una evaluación inmediata"""
    return get_watcher().force_check(pair)
