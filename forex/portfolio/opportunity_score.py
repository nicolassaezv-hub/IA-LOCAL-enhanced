"""
VI.8.A — Opportunity Score Engine
Calcula el OpScore compuesto (0–100) para cada señal activa.
Fórmula: (Reliability × 0.35) + (WinRate × 0.30) + (RegimenBonus × 0.20) + (MTF × 0.15)
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


_SCORE_THRESHOLD     = 60.0   # mínimo OpScore para entrar al ranking
_RELIABILITY_MIN     = 70.0   # mínimo Reliability para entrar al ranking

# Pesos de la fórmula
_W_RELIABILITY = 0.35
_W_WINRATE     = 0.30
_W_REGIME      = 0.20
_W_MTF         = 0.15

# Bonificaciones / penalizaciones
_BONUS_CANDLE_CONFIRM  = +10.0
_BONUS_REGIME_FAVOR    = +15.0
_PENALTY_REGIME_ADV    = -15.0
_PENALTY_NO_MTF        = -10.0
_PENALTY_STALE_DATA    = -20.0

_FAVORABLE_REGIMES  = {"trending_bullish", "trending_bearish", "breakout"}
_ADVERSE_REGIMES    = {"high_volatility", "news_risk", "ranging_choppy"}


@dataclass
class SignalInput:
    """Datos de entrada para calcular el OpScore de una señal."""
    pair: str
    direction: str                        # "BUY" | "SELL" | "HOLD"
    reliability_score: float = 0.0       # 0–100 del ReliabilityScorer (V.8)
    win_rate_pct: float = 0.0            # histórico del modelo, 0–100
    regime: str = "unknown"              # del RegimeDetector (V.4)
    mtf_coherent: bool = False           # del MTFIntelligence (V.3)
    candlestick_confirm: bool = False    # del CandlestickPatternDetector (VI.5.D)
    data_fresh: bool = True              # False si los datos tienen >2h de antigüedad
    current_price: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    model_name: str = "ensemble"
    confidence: float = 0.0             # 0–100
    ts: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class OpportunityResult:
    """Resultado del cálculo de OpScore para una señal."""
    pair: str
    direction: str
    op_score: float
    reliability: float
    win_rate: float
    regime: str
    mtf_coherent: bool
    current_price: float
    take_profit: float
    stop_loss: float
    model_name: str
    confidence: float
    ts: str
    eligible: bool     # True si supera los umbrales mínimos
    breakdown: dict    # desglose del score por componente


def calculate_op_score(signal: SignalInput) -> OpportunityResult:
    """Calcula el Opportunity Score para una señal."""
    breakdown = {}

    # Componente 1: Reliability
    rel_component = signal.reliability_score * _W_RELIABILITY
    breakdown["reliability"] = rel_component

    # Componente 2: Win Rate
    wr_component = signal.win_rate_pct * _W_WINRATE
    breakdown["win_rate"] = wr_component

    # Componente 3: Régimen (bonus proporcional)
    if signal.regime in _FAVORABLE_REGIMES:
        regime_base = 80.0
    elif signal.regime in _ADVERSE_REGIMES:
        regime_base = 30.0
    else:
        regime_base = 55.0
    regime_component = regime_base * _W_REGIME
    breakdown["regime"] = regime_component

    # Componente 4: MTF Coherencia
    mtf_base = 90.0 if signal.mtf_coherent else 40.0
    mtf_component = mtf_base * _W_MTF
    breakdown["mtf"] = mtf_component

    raw_score = rel_component + wr_component + regime_component + mtf_component

    # Bonificaciones y penalizaciones
    adjustments = 0.0
    if signal.candlestick_confirm:
        adjustments += _BONUS_CANDLE_CONFIRM
        breakdown["bonus_candle"] = _BONUS_CANDLE_CONFIRM
    if signal.regime in _FAVORABLE_REGIMES:
        adjustments += _BONUS_REGIME_FAVOR
        breakdown["bonus_regime"] = _BONUS_REGIME_FAVOR
    if signal.regime in _ADVERSE_REGIMES:
        adjustments += _PENALTY_REGIME_ADV
        breakdown["penalty_regime"] = _PENALTY_REGIME_ADV
    if not signal.mtf_coherent:
        adjustments += _PENALTY_NO_MTF
        breakdown["penalty_no_mtf"] = _PENALTY_NO_MTF
    if not signal.data_fresh:
        adjustments += _PENALTY_STALE_DATA
        breakdown["penalty_stale"] = _PENALTY_STALE_DATA

    breakdown["adjustments"] = adjustments
    final_score = max(0.0, min(100.0, raw_score + adjustments))
    breakdown["final"] = final_score

    eligible = (
        final_score >= _SCORE_THRESHOLD
        and signal.reliability_score >= _RELIABILITY_MIN
        and signal.direction in ("BUY", "SELL")
    )

    return OpportunityResult(
        pair=signal.pair,
        direction=signal.direction,
        op_score=round(final_score, 1),
        reliability=signal.reliability_score,
        win_rate=signal.win_rate_pct,
        regime=signal.regime,
        mtf_coherent=signal.mtf_coherent,
        current_price=signal.current_price,
        take_profit=signal.take_profit,
        stop_loss=signal.stop_loss,
        model_name=signal.model_name,
        confidence=signal.confidence,
        ts=signal.ts,
        eligible=eligible,
        breakdown=breakdown,
    )


class OpportunityRanker:
    """
    Genera el ranking Top-N de oportunidades BUY y SELL
    a partir de una lista de señales activas.
    """

    def __init__(self, top_n: int = 10):
        self.top_n = top_n

    def rank(self, signals: list[SignalInput]) -> dict:
        """
        Calcula OpScore para cada señal y devuelve Top-N BUY y Top-N SELL.
        Solo incluye señales elegibles (OpScore ≥ 60, Reliability ≥ 70).
        """
        results = [calculate_op_score(s) for s in signals]
        eligible = [r for r in results if r.eligible]

        buys  = sorted([r for r in eligible if r.direction == "BUY"],
                       key=lambda x: x.op_score, reverse=True)[:self.top_n]
        sells = sorted([r for r in eligible if r.direction == "SELL"],
                       key=lambda x: x.op_score, reverse=True)[:self.top_n]

        return {
            "top_buy":   buys,
            "top_sell":  sells,
            "total_evaluated": len(signals),
            "total_eligible":  len(eligible),
            "ts": datetime.now().isoformat(),
        }

    def format_ranking(self, ranking: dict) -> str:
        """Formatea el ranking para mostrar en consola."""
        lines = []
        ts = ranking.get("ts", "")[:19]
        lines.append(f"\n{'═'*62}")
        lines.append(f"  🎯 OPPORTUNITY RANKING — {ts}")
        lines.append(f"  Evaluadas: {ranking['total_evaluated']}  |  Elegibles: {ranking['total_eligible']}")
        lines.append(f"{'═'*62}")

        for label, key in [("TOP BUY  ▲", "top_buy"), ("TOP SELL ▼", "top_sell")]:
            items = ranking.get(key, [])
            lines.append(f"\n  {label}")
            if not items:
                lines.append("    (Sin señales elegibles)")
            else:
                lines.append(f"  {'#':<3} {'Par':<10} {'Precio':>10} {'TP':>10} {'SL':>10} {'Score':>6} {'Conf':>6} {'Rel':>5}")
                lines.append(f"  {'─'*62}")
                for i, r in enumerate(items, 1):
                    lines.append(
                        f"  {i:<3} {r.pair:<10} {r.current_price:>10.5f} "
                        f"{r.take_profit:>10.5f} {r.stop_loss:>10.5f} "
                        f"{r.op_score:>5.1f}  {r.confidence:>5.1f}% {r.reliability:>5.1f}"
                    )
        lines.append(f"\n{'═'*62}")
        return "\n".join(lines)


_ranker = OpportunityRanker()


def get_ranker(top_n: int = 10) -> OpportunityRanker:
    return OpportunityRanker(top_n)
