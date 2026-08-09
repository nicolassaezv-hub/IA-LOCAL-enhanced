"""
position_sizing.py — ASTRA Forex
=================================
Calcula el tamaño de posición óptimo usando Kelly Criterion fraccionado.

Reglas de uso:
  - Kelly puro es agresivo. Usamos Kelly * 0.25 (cuarto de Kelly) como estándar.
  - El resultado se clampea a [min_risk, max_risk] para evitar ruina.
  - Si no hay historial suficiente (< 20 trades), usa riesgo mínimo conservador.

API pública:
    sizer = PositionSizer(account_balance=10000)
    result = sizer.calculate(signal, trade_history)
    → {"units": float, "risk_pct": float, "risk_usd": float, "kelly_fraction": float, "method": str}

    cmd_position_size(pair, balance) → str  (para main.py)
"""

import math
from typing import Optional


# ─────────────────────────────────────────────────────────
# CONSTANTES DE RIESGO
# ─────────────────────────────────────────────────────────
MIN_RISK_PCT   = 0.005   # 0.5% mínimo absoluto por operación
MAX_RISK_PCT   = 0.02    # 2.0% máximo absoluto por operación
KELLY_FRACTION = 0.25    # Cuarto de Kelly (conservador)
MIN_TRADES     = 20      # Mínimo de trades para usar Kelly; si no, usa MIN_RISK_PCT


class PositionSizer:
    """
    Calcula el tamaño de posición usando Kelly Criterion fraccionado.

    Parameters
    ----------
    account_balance : float  — capital total disponible en cuenta (USD o unidad base)
    kelly_fraction  : float  — multiplicador de Kelly (0.25 = cuarto de Kelly)
    min_risk_pct    : float  — riesgo mínimo por operación como fracción del balance
    max_risk_pct    : float  — riesgo máximo por operación como fracción del balance
    """

    def __init__(
        self,
        account_balance: float = 10_000,
        kelly_fraction:  float = KELLY_FRACTION,
        min_risk_pct:    float = MIN_RISK_PCT,
        max_risk_pct:    float = MAX_RISK_PCT,
    ):
        self.account_balance = account_balance
        self.kelly_fraction  = kelly_fraction
        self.min_risk_pct    = min_risk_pct
        self.max_risk_pct    = max_risk_pct

    # ─────────────────────────────────────────────────────
    # MÉTODO PRINCIPAL
    # ─────────────────────────────────────────────────────
    def calculate(
        self,
        signal:        dict,
        trade_history: list,
        price:         float = 1.0,
        stop_loss_pips: float = 20.0,
    ) -> dict:
        """
        Calcula el tamaño de posición para la señal recibida.

        Parameters
        ----------
        signal        : dict devuelto por ForexPredictor.signal()
        trade_history : list de dicts con {"pnl": float}
        price         : precio actual del activo
        stop_loss_pips: distancia en pips al stop loss

        Returns
        -------
        dict con:
            risk_pct        — fracción del balance a arriesgar
            risk_usd        — monto en USD a arriesgar
            units           — unidades a comprar/vender
            kelly_fraction  — kelly calculado antes de clamp
            method          — "kelly" | "conservative" | "hold"
        """
        action = signal.get("action", "HOLD")

        if action == "HOLD":
            return {
                "action":        "HOLD",
                "risk_pct":      0.0,
                "risk_usd":      0.0,
                "units":         0.0,
                "kelly_raw":     0.0,
                "method":        "hold",
                "reason":        signal.get("hold_reason", "Señal HOLD — no operar"),
            }

        # ── Estadísticas del historial ────────────────────
        wins   = [t["pnl"] for t in trade_history if t.get("pnl", 0) > 0]
        losses = [t["pnl"] for t in trade_history if t.get("pnl", 0) <= 0]
        n      = len(trade_history)

        if n < MIN_TRADES or not wins or not losses:
            # Sin historial suficiente → riesgo mínimo conservador
            risk_pct = self.min_risk_pct
            kelly_raw = 0.0
            method   = "conservative"
        else:
            win_rate  = len(wins) / n
            avg_win   = sum(wins)   / len(wins)
            avg_loss  = abs(sum(losses) / len(losses))

            if avg_loss < 1e-9:
                risk_pct  = self.min_risk_pct
                kelly_raw = 0.0
                method    = "conservative"
            else:
                b = avg_win / avg_loss        # ratio beneficio/pérdida
                # Kelly = W - (1 - W) / B
                kelly_raw = win_rate - (1 - win_rate) / b
                # Aplicar fracción de Kelly y clampear
                kelly_adj = kelly_raw * self.kelly_fraction
                risk_pct  = max(self.min_risk_pct, min(self.max_risk_pct, kelly_adj))
                method    = "kelly"

        # Ajustar por confianza de la señal
        confidence = signal.get("confidence", 0.5)
        risk_pct   = risk_pct * min(1.0, confidence / 0.75)
        risk_pct   = max(self.min_risk_pct, min(self.max_risk_pct, risk_pct))

        risk_usd   = self.account_balance * risk_pct
        # Unidades = riesgo_usd / stop_loss_en_precio
        stop_price = stop_loss_pips * 0.0001 * price   # aprox. para pares FX
        units      = risk_usd / (stop_price + 1e-9)

        return {
            "action":       action,
            "risk_pct":     round(risk_pct * 100, 3),      # en %
            "risk_usd":     round(risk_usd, 2),
            "units":        round(units, 2),
            "kelly_raw":    round(kelly_raw, 4),
            "method":       method,
            "n_trades":     n,
            "confidence":   round(confidence, 4),
        }

    # ─────────────────────────────────────────────────────
    # ACTUALIZAR BALANCE
    # ─────────────────────────────────────────────────────
    def update_balance(self, new_balance: float):
        """Actualiza el balance tras cierre de operaciones."""
        self.account_balance = new_balance


# ─────────────────────────────────────────────────────────
# COMANDO CLI
# ─────────────────────────────────────────────────────────
def cmd_position_size(pair: str = "EURUSD", balance: float = 10_000,
                      signal: dict = None, trade_history: list = None) -> str:
    """
    Calcula y muestra el position sizing para un par.
    Diseñado para llamarse desde main.py.

    Ejemplo:
        result = cmd_position_size("EURUSD", 10000)
    """
    sizer = PositionSizer(account_balance=balance)

    # Señal demo si no se pasa
    if signal is None:
        signal = {"action": "BUY", "confidence": 0.75, "adx": 28.0}

    history = trade_history or []

    r = sizer.calculate(signal, history)

    method_label = {
        "kelly":        "Kelly Fraccionado (x0.25)",
        "conservative": f"Conservador (< {MIN_TRADES} trades en historial)",
        "hold":         "HOLD — no operar",
    }.get(r["method"], r["method"])

    lines = [
        f"\n{'═'*50}",
        f"  POSITION SIZING — {pair.upper()}",
        f"{'─'*50}",
        f"  Balance       : ${balance:,.2f}",
        f"  Señal         : {r['action']}  (conf={r['confidence']:.2%})",
        f"  Método        : {method_label}",
        f"  Kelly raw     : {r['kelly_raw']:.4f}",
        f"  Riesgo        : {r['risk_pct']:.3f}%  →  ${r['risk_usd']:,.2f}",
        f"  Unidades      : {r['units']:,.2f}",
        f"  Trades hist.  : {r['n_trades']}",
        f"{'═'*50}",
    ]
    if r["method"] == "hold":
        lines.append(f"  Motivo HOLD   : {r.get('reason','')}")
        lines.append(f"{'═'*50}")

    return "\n".join(lines)
