"""
circuit_breaker.py — ASTRA Forex
==================================
Protección automática de capital. Detiene el trading cuando se alcanzan
límites de pérdida diaria, semanal o de drawdown máximo.

Reglas por defecto (ajustables):
  - Max pérdida diaria  : 3% del balance inicial del día
  - Max pérdida semanal : 6% del balance inicial de la semana
  - Max drawdown        : 10% desde el pico histórico
  - Cooldown tras trip  : 24h (no opera aunque se recupere el balance)

API pública:
    cb = CircuitBreaker(initial_balance=10000)
    cb.record_trade(pnl=-150)
    status = cb.check()
    → {"open": True/False, "reason": str, "daily_loss_pct": float, ...}

    cb.reset_daily()     — llamar cada día a las 00:00
    cb.reset_weekly()    — llamar cada lunes a las 00:00

    cmd_circuit_status() → str   (para main.py)
    cmd_circuit_reset()  → str
"""

import time
import json
import os
from typing import Optional


# ─────────────────────────────────────────────────────────
# LÍMITES POR DEFECTO
# ─────────────────────────────────────────────────────────
MAX_DAILY_LOSS_PCT    = 0.03   # 3%  del balance inicial del día
MAX_WEEKLY_LOSS_PCT   = 0.06   # 6%  del balance inicial de la semana
MAX_DRAWDOWN_PCT      = 0.10   # 10% desde el pico histórico
COOLDOWN_HOURS        = 24     # horas de pausa tras activar el circuit breaker

_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "../../circuit_breaker_state.json")
_STATE_FILE = os.path.normpath(_STATE_FILE)


class CircuitBreaker:
    """
    Monitorea pérdidas y corta el trading automáticamente si se superan los límites.

    Parameters
    ----------
    initial_balance      : float — capital inicial de la sesión
    max_daily_loss_pct   : float — % del balance del día que activa el corte diario
    max_weekly_loss_pct  : float — % del balance semanal que activa el corte semanal
    max_drawdown_pct     : float — % desde el pico histórico que activa el corte global
    cooldown_hours       : float — horas de pausa obligatoria después de activación
    persist              : bool  — si True guarda estado en JSON entre sesiones
    """

    def __init__(
        self,
        initial_balance:    float = 10_000,
        max_daily_loss_pct:  float = MAX_DAILY_LOSS_PCT,
        max_weekly_loss_pct: float = MAX_WEEKLY_LOSS_PCT,
        max_drawdown_pct:   float = MAX_DRAWDOWN_PCT,
        cooldown_hours:     float = COOLDOWN_HOURS,
        persist:            bool  = True,
    ):
        self.initial_balance      = initial_balance
        self.max_daily_loss_pct   = max_daily_loss_pct
        self.max_weekly_loss_pct  = max_weekly_loss_pct
        self.max_drawdown_pct     = max_drawdown_pct
        self.cooldown_hours       = cooldown_hours
        self.persist              = persist

        # Estado en memoria
        self.current_balance   = initial_balance
        self.peak_balance      = initial_balance
        self.daily_start       = initial_balance
        self.weekly_start      = initial_balance
        self.daily_pnl         = 0.0
        self.weekly_pnl        = 0.0
        self.tripped           = False         # True = circuit breaker activado
        self.trip_reason       = ""
        self.trip_time: Optional[float] = None  # timestamp UNIX del trip
        self.trade_log: list   = []

        # Cargar estado persistido
        if persist:
            self._load_state()

    # ─────────────────────────────────────────────────────
    # REGISTRAR TRADE
    # ─────────────────────────────────────────────────────
    def record_trade(self, pnl: float, pair: str = "", action: str = ""):
        """
        Registra el resultado de una operación cerrada.
        Actualiza todos los contadores y comprueba los límites.

        Parameters
        ----------
        pnl    : float — ganancia/pérdida en unidades monetarias (negativo = pérdida)
        pair   : str   — nombre del par (para el log)
        action : str   — "BUY" | "SELL"
        """
        self.current_balance += pnl
        self.daily_pnl       += pnl
        self.weekly_pnl      += pnl

        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        self.trade_log.append({
            "ts":      time.strftime("%Y-%m-%d %H:%M:%S"),
            "pair":    pair,
            "action":  action,
            "pnl":     round(pnl, 4),
            "balance": round(self.current_balance, 4),
        })

        # Comprobar límites automáticamente
        self._check_limits()

        if self.persist:
            self._save_state()

    # ─────────────────────────────────────────────────────
    # CHECK — ¿puede operar ahora?
    # ─────────────────────────────────────────────────────
    def check(self) -> dict:
        """
        Retorna el estado actual del circuit breaker.

        Returns
        -------
        dict:
            open            : bool  — True = puede operar, False = BLOQUEADO
            reason          : str   — motivo del bloqueo (vacío si open=True)
            daily_loss_pct  : float — % perdido hoy
            weekly_loss_pct : float — % perdido esta semana
            drawdown_pct    : float — % caída desde el pico
            balance         : float — balance actual
            cooldown_remaining_h : float — horas restantes de cooldown
        """
        daily_loss_pct  = -self.daily_pnl  / (self.daily_start  + 1e-9)
        weekly_loss_pct = -self.weekly_pnl / (self.weekly_start + 1e-9)
        drawdown_pct    = (self.peak_balance - self.current_balance) / (self.peak_balance + 1e-9)

        cooldown_remaining = 0.0
        if self.tripped and self.trip_time is not None:
            elapsed  = (time.time() - self.trip_time) / 3600
            cooldown_remaining = max(0.0, self.cooldown_hours - elapsed)
            if cooldown_remaining == 0.0:
                # Cooldown expirado — resetear automáticamente
                self._reset_trip()

        return {
            "open":                 not self.tripped,
            "reason":               self.trip_reason if self.tripped else "",
            "daily_loss_pct":       round(daily_loss_pct  * 100, 3),
            "weekly_loss_pct":      round(weekly_loss_pct * 100, 3),
            "drawdown_pct":         round(drawdown_pct    * 100, 3),
            "balance":              round(self.current_balance, 2),
            "peak_balance":         round(self.peak_balance, 2),
            "cooldown_remaining_h": round(cooldown_remaining, 2),
        }

    # ─────────────────────────────────────────────────────
    # RESETS PROGRAMADOS
    # ─────────────────────────────────────────────────────
    def reset_daily(self):
        """Llamar al inicio de cada día de trading (ej. 00:00 NY)."""
        self.daily_start = self.current_balance
        self.daily_pnl   = 0.0
        if self.persist:
            self._save_state()

    def reset_weekly(self):
        """Llamar al inicio de cada semana (ej. lunes 00:00 NY)."""
        self.weekly_start = self.current_balance
        self.weekly_pnl   = 0.0
        if self.persist:
            self._save_state()

    # ─────────────────────────────────────────────────────
    # INTERNOS
    # ─────────────────────────────────────────────────────
    def _check_limits(self):
        if self.tripped:
            return

        daily_loss_pct  = -self.daily_pnl  / (self.daily_start  + 1e-9)
        weekly_loss_pct = -self.weekly_pnl / (self.weekly_start + 1e-9)
        drawdown_pct    = (self.peak_balance - self.current_balance) / (self.peak_balance + 1e-9)

        if daily_loss_pct >= self.max_daily_loss_pct:
            self._trip(f"Pérdida diaria {daily_loss_pct:.2%} ≥ límite {self.max_daily_loss_pct:.2%}")
        elif weekly_loss_pct >= self.max_weekly_loss_pct:
            self._trip(f"Pérdida semanal {weekly_loss_pct:.2%} ≥ límite {self.max_weekly_loss_pct:.2%}")
        elif drawdown_pct >= self.max_drawdown_pct:
            self._trip(f"Drawdown {drawdown_pct:.2%} ≥ límite {self.max_drawdown_pct:.2%}")

    def _trip(self, reason: str):
        self.tripped     = True
        self.trip_reason = reason
        self.trip_time   = time.time()
        print(f"\n🚨 [CIRCUIT BREAKER ACTIVADO] {reason}")
        print(f"   Trading BLOQUEADO por {self.cooldown_hours:.0f}h. Balance: ${self.current_balance:,.2f}")
        if self.persist:
            self._save_state()

    def _reset_trip(self):
        self.tripped     = False
        self.trip_reason = ""
        self.trip_time   = None
        if self.persist:
            self._save_state()

    def _save_state(self):
        try:
            state = {
                "current_balance": self.current_balance,
                "peak_balance":    self.peak_balance,
                "daily_start":     self.daily_start,
                "weekly_start":    self.weekly_start,
                "daily_pnl":       self.daily_pnl,
                "weekly_pnl":      self.weekly_pnl,
                "tripped":         self.tripped,
                "trip_reason":     self.trip_reason,
                "trip_time":       self.trip_time,
            }
            os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
            with open(_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _load_state(self):
        try:
            if os.path.exists(_STATE_FILE):
                with open(_STATE_FILE) as f:
                    s = json.load(f)
                self.current_balance = s.get("current_balance", self.initial_balance)
                self.peak_balance    = s.get("peak_balance",    self.initial_balance)
                self.daily_start     = s.get("daily_start",     self.initial_balance)
                self.weekly_start    = s.get("weekly_start",    self.initial_balance)
                self.daily_pnl       = s.get("daily_pnl",       0.0)
                self.weekly_pnl      = s.get("weekly_pnl",      0.0)
                self.tripped         = s.get("tripped",         False)
                self.trip_reason     = s.get("trip_reason",     "")
                self.trip_time       = s.get("trip_time",        None)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────
# SINGLETON GLOBAL (compartido por active_engine)
# ─────────────────────────────────────────────────────────
_global_cb: Optional[CircuitBreaker] = None


def get_circuit_breaker(initial_balance: float = 10_000) -> CircuitBreaker:
    """Retorna la instancia global del circuit breaker (singleton)."""
    global _global_cb
    if _global_cb is None:
        _global_cb = CircuitBreaker(initial_balance=initial_balance)
    return _global_cb


# ─────────────────────────────────────────────────────────
# COMANDOS CLI
# ─────────────────────────────────────────────────────────
def cmd_circuit_status() -> str:
    cb     = get_circuit_breaker()
    status = cb.check()
    icon   = "🟢 ABIERTO" if status["open"] else "🔴 BLOQUEADO"

    lines = [
        f"\n{'═'*52}",
        f"  CIRCUIT BREAKER — {icon}",
        f"{'─'*52}",
        f"  Balance actual   : ${status['balance']:>10,.2f}",
        f"  Peak histórico   : ${status['peak_balance']:>10,.2f}",
        f"  Pérdida diaria   : {status['daily_loss_pct']:>6.2f}%  (límite: {cb.max_daily_loss_pct*100:.0f}%)",
        f"  Pérdida semanal  : {status['weekly_loss_pct']:>6.2f}%  (límite: {cb.max_weekly_loss_pct*100:.0f}%)",
        f"  Drawdown         : {status['drawdown_pct']:>6.2f}%  (límite: {cb.max_drawdown_pct*100:.0f}%)",
    ]
    if not status["open"]:
        lines += [
            f"{'─'*52}",
            f"  🚨 Motivo bloqueo : {status['reason']}",
            f"  ⏱  Cooldown resto : {status['cooldown_remaining_h']:.1f}h",
        ]
    lines.append(f"{'═'*52}")
    return "\n".join(lines)


def cmd_circuit_reset(force: bool = False) -> str:
    """Resetea el circuit breaker manualmente (solo si el usuario lo pide)."""
    cb = get_circuit_breaker()
    cb._reset_trip()
    cb.reset_daily()
    return "✓ Circuit breaker reseteado manualmente. El trading está habilitado."
