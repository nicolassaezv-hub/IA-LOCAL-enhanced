"""ASTRA Forex Risk Engine.

ATR/Kelly select the stop and risk fraction.  Exact monetary sizing is
delegated to :mod:`position_sizing`, which requires explicit instrument and
account-currency metadata and fails closed when it cannot prove the result.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .position_sizing import (
    InstrumentMetadata,
    calculate_forex_position_size,
)
from .risk_config_resolver import normalize_instrument_symbol


@dataclass
class RiskAssessment:
    valid: bool = False
    decision: str = "HOLD"
    pair: str = ""
    timeframe: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    stop_distance_price: float = 0.0
    sl_pips: float = 0.0
    tp_pips: float = 0.0
    pip_size: float = 0.0
    rr_ratio: float = 1.0
    position_size: float = 0.0
    position_size_unit: str = "base_currency_units"
    raw_position_size: float = 0.0
    raw_position_size_unit: str = "lots"
    risk_limited_size: float = 0.0
    final_position_size: float = 0.0
    final_position_size_unit: str = "lots"
    units: float = 0.0
    lots: float = 0.0
    contract_size: float = 0.0
    pip_value_per_lot: float = 0.0
    loss_per_unit: float = 0.0
    loss_per_lot: float = 0.0
    risk_pct: float = 0.0
    risk_fraction: float = 0.0
    risk_amount: float = 0.0
    reward_amount: float = 0.0
    gross_reward_per_lot: float = 0.0
    effective_rr: float = 0.0
    account_currency: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    conversion_rate: float = 0.0
    leverage: float | None = None
    margin_limited_size: float | None = None
    margin_required: float | None = None
    available_margin: float | None = None
    stop_loss_amount: float = 0.0
    additional_cost_amount: float = 0.0
    worst_case_loss: float = 0.0
    costs_included: bool = False
    cost_assumptions: dict[str, object] = field(default_factory=dict)
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expected_drawdown: float = 0.0
    kelly_fraction: float = 0.0
    regime: str = ""
    atr_value: float = 0.0
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 1.5
    capital: float | None = None
    risk_level: str = "medium"
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class RiskEngine:
    """Compute stop geometry, risk budget and an auditable position size."""

    DEFAULTS = {
        "risk_per_trade_pct": 1.0,
        "max_risk_pct": 2.0,
        "min_risk_pct": 0.5,
        "kelly_fraction": 0.25,
        "rr_ratio_default": 1.0,
        "atr_mult_sl_trending": 1.5,
        "atr_mult_sl_ranging": 2.0,
        "atr_mult_sl_high_vol": 2.5,
        "atr_mult_tp_trending": 1.5,
        "atr_mult_tp_ranging": 1.0,
        # No default account currency, contract size, or conversion rate: those
        # are deployment/broker facts and must be supplied explicitly.
        "account_currency": None,
        "instrument_metadata": None,
        "require_margin_validation": False,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def assess(
        self,
        decision: str = "BUY",
        entry_price: float = 0.0,
        atr: float = 0.0,
        reliability_score: float = 0.0,
        model_win_rate: float = 0.5,
        regime: str = "",
        pair: str = "",
        timeframe: str = "",
        capital: float | None = None,
        rr_ratio: float | None = None,
        *,
        stop_loss: float | None = None,
        instrument_metadata: InstrumentMetadata | dict | None = None,
        account_currency: str | None = None,
        conversion_rate: float | None = None,
        currency_converter=None,
        leverage: float | None = None,
        available_margin: float | None = None,
        require_margin_validation: bool | None = None,
        commission_per_lot: float | None = None,
        spread_price: float | None = None,
        slippage_price: float | None = None,
        costs_in_entry_stop: bool | None = None,
    ) -> RiskAssessment:
        configured_equity = self.config.get("account_equity")
        if configured_equity is None and "capital" in self.config:
            configured_equity = self.config.get("capital")
        cap = capital if capital is not None else configured_equity
        rr = rr_ratio if rr_ratio is not None else self.config["rr_ratio_default"]
        action = str(decision or "").upper()
        result = RiskAssessment(
            decision=action,
            pair=pair,
            timeframe=timeframe,
            entry_price=entry_price,
            atr_value=atr,
            rr_ratio=rr,
            regime=regime,
            capital=cap,
            account_currency=str(
                account_currency or self.config.get("account_currency") or ""
            ).upper(),
        )

        if action not in ("BUY", "SELL"):
            result.risk_level = "none"
            result.recommendation = "No directional signal; no position sizing required."
            return result

        numeric_inputs = (entry_price, atr, reliability_score, model_win_rate, rr)
        if cap is not None:
            numeric_inputs += (cap,)
        try:
            inputs_finite = all(math.isfinite(float(value)) for value in numeric_inputs)
        except (TypeError, ValueError):
            inputs_finite = False
        if not inputs_finite:
            result.blocking_reasons.append("non_finite_risk_input")
            result.recommendation = self._build_recommendation(result)
            return result
        if float(rr) <= 0.0:
            result.blocking_reasons.append("invalid_rr_ratio")
            result.recommendation = self._build_recommendation(result)
            return result
        if float(atr) <= 0.0:
            result.blocking_reasons.append("invalid_atr")
            result.recommendation = self._build_recommendation(result)
            return result

        sl_mult, tp_mult = self._get_atr_multipliers(regime)
        result.atr_multiplier_sl = sl_mult
        result.atr_multiplier_tp = tp_mult
        generated_sl_distance = float(atr) * sl_mult
        tp_distance = float(atr) * tp_mult * float(rr)
        if stop_loss is None:
            result.stop_loss = (
                float(entry_price) - generated_sl_distance
                if action == "BUY"
                else float(entry_price) + generated_sl_distance
            )
        else:
            result.stop_loss = stop_loss
        result.take_profit = (
            float(entry_price) + tp_distance
            if action == "BUY"
            else float(entry_price) - tp_distance
        )

        kelly = self._kelly_criterion(float(model_win_rate), float(rr))
        result.kelly_fraction = kelly * self.config["kelly_fraction"]
        result.risk_pct = self._compute_risk_pct(
            float(reliability_score), result.kelly_fraction
        )
        result.risk_fraction = result.risk_pct / 100.0

        metadata = self._resolve_instrument_metadata(pair, instrument_metadata)
        metadata_symbol = (
            metadata.symbol
            if isinstance(metadata, InstrumentMetadata)
            else metadata.get("symbol")
            if isinstance(metadata, dict)
            else None
        )
        if metadata is not None and (
            normalize_instrument_symbol(pair)
            != normalize_instrument_symbol(metadata_symbol)
        ):
            result.blocking_reasons = self._configuration_blocking_reasons()
            result.blocking_reasons.append("instrument_symbol_mismatch")
            result.blocking_reasons = list(dict.fromkeys(result.blocking_reasons))
            result.recommendation = self._build_recommendation(result)
            return result
        sizing = calculate_forex_position_size(
            instrument=metadata,
            account_equity=cap,
            risk_fraction=result.risk_fraction,
            account_currency=result.account_currency,
            side=action,
            entry=float(entry_price),
            stop=result.stop_loss,
            conversion_rate=(
                conversion_rate
                if conversion_rate is not None
                else self.config.get("conversion_rate")
            ),
            currency_converter=(
                currency_converter
                if currency_converter is not None
                else self.config.get("currency_converter")
            ),
            max_risk_fraction=float(self.config["max_risk_pct"]) / 100.0,
            leverage=leverage if leverage is not None else self.config.get("leverage"),
            available_margin=(
                available_margin
                if available_margin is not None
                else self.config.get("available_margin")
            ),
            require_margin_validation=(
                bool(self.config.get("require_margin_validation"))
                if require_margin_validation is None
                else require_margin_validation
            ),
            commission_per_lot=(
                commission_per_lot
                if commission_per_lot is not None
                else self.config.get("commission_per_lot")
            ),
            spread_price=(
                spread_price if spread_price is not None else self.config.get("spread_price")
            ),
            slippage_price=(
                slippage_price
                if slippage_price is not None
                else self.config.get("slippage_price")
            ),
            costs_in_entry_stop=(
                bool(self.config.get("costs_in_entry_stop"))
                if costs_in_entry_stop is None
                else costs_in_entry_stop
            ),
        )
        self._apply_sizing(result, sizing)
        result.blocking_reasons = list(
            dict.fromkeys(self._configuration_blocking_reasons() + result.blocking_reasons)
        )
        if result.blocking_reasons:
            result.valid = False
            result.position_size = 0.0
            result.final_position_size = 0.0
            result.lots = 0.0
            result.units = 0.0
        result.tp_pips = (
            abs(tp_distance / result.pip_size) if result.pip_size > 0.0 else 0.0
        )
        take_profit_distance_price = abs(result.take_profit - result.entry_price)
        if result.contract_size > 0.0 and result.conversion_rate > 0.0:
            result.gross_reward_per_lot = (
                take_profit_distance_price
                * result.contract_size
                * result.conversion_rate
            )
            result.reward_amount = result.lots * result.gross_reward_per_lot
        if result.worst_case_loss > 0.0:
            result.effective_rr = result.reward_amount / result.worst_case_loss
        result.expected_drawdown = result.stop_distance_price
        result.risk_level = self._classify_risk(
            float(reliability_score), result.risk_pct, regime
        )
        result.recommendation = self._build_recommendation(result)
        return result

    def _configuration_blocking_reasons(self) -> list[str]:
        reasons = self.config.get("configuration_blocking_reasons") or []
        if isinstance(reasons, str):
            return [reasons]
        return [str(reason) for reason in reasons]

    def _resolve_instrument_metadata(
        self,
        pair: str,
        supplied: InstrumentMetadata | dict | None,
    ) -> InstrumentMetadata | dict | None:
        if supplied is not None:
            return supplied
        configured = self.config.get("instrument_metadata")
        if isinstance(configured, InstrumentMetadata):
            return configured
        if isinstance(configured, dict):
            if "asset_class" in configured:
                return configured
            clean_pair = str(pair or "").upper().replace("/", "").replace("_", "").replace("-", "")
            return configured.get(clean_pair)
        return None

    @staticmethod
    def _apply_sizing(result: RiskAssessment, sizing) -> None:
        result.valid = sizing.valid
        result.risk_amount = sizing.risk_amount
        result.base_currency = sizing.base_currency
        result.quote_currency = sizing.quote_currency
        result.stop_distance_price = sizing.stop_distance_price
        result.sl_pips = sizing.stop_pips
        result.pip_size = sizing.pip_size
        result.contract_size = sizing.contract_size
        result.pip_value_per_lot = sizing.pip_value_per_lot
        result.loss_per_unit = sizing.loss_per_unit
        result.loss_per_lot = sizing.loss_per_lot
        result.conversion_rate = sizing.conversion_rate
        result.raw_position_size = sizing.raw_position_size
        result.risk_limited_size = sizing.risk_limited_size
        result.final_position_size = sizing.final_position_size
        result.lots = sizing.lots
        result.units = sizing.units
        result.position_size = sizing.units
        result.leverage = sizing.leverage
        result.margin_limited_size = sizing.margin_limited_size
        result.margin_required = sizing.margin_required
        result.available_margin = sizing.available_margin
        result.stop_loss_amount = sizing.stop_loss_amount
        result.additional_cost_amount = sizing.additional_cost_amount
        result.worst_case_loss = sizing.worst_case_loss
        result.costs_included = sizing.costs_included
        result.cost_assumptions = sizing.cost_assumptions
        result.blocking_reasons = sizing.blocking_reasons
        result.warnings = sizing.warnings

    def _get_atr_multipliers(self, regime: str) -> tuple[float, float]:
        if regime in ("trending_bullish", "trending_bearish"):
            return self.config["atr_mult_sl_trending"], self.config["atr_mult_tp_trending"]
        if regime == "ranging":
            return self.config["atr_mult_sl_ranging"], self.config["atr_mult_tp_ranging"]
        if regime in ("high_volatility", "news_impact"):
            return self.config["atr_mult_sl_high_vol"], self.config["atr_mult_tp_trending"]
        return self.config["atr_mult_sl_trending"], self.config["atr_mult_tp_trending"]

    @staticmethod
    def _kelly_criterion(win_rate: float, rr: float) -> float:
        p = max(0.01, min(0.99, win_rate))
        q = 1.0 - p
        b = max(0.1, rr)
        return max(0.0, (p * b - q) / b)

    def _compute_risk_pct(self, reliability: float, kelly: float) -> float:
        base_risk = kelly * 100.0
        reliability_factor = max(0.3, min(1.0, reliability / 100.0))
        adjusted_risk = base_risk * reliability_factor
        return max(
            self.config["min_risk_pct"],
            min(self.config["max_risk_pct"], adjusted_risk),
        )

    @staticmethod
    def _classify_risk(reliability: float, risk_pct: float, regime: str) -> str:
        if regime in ("high_volatility", "news_impact"):
            return "high"
        if reliability >= 85 and risk_pct <= 1.0:
            return "low"
        if reliability >= 70 and risk_pct <= 1.5:
            return "medium"
        return "high"

    @staticmethod
    def _build_recommendation(result: RiskAssessment) -> str:
        if not result.valid:
            reasons = ", ".join(result.blocking_reasons) or "sizing_not_requested"
            return f"Position sizing invalid (fail-closed): {reasons}."
        return (
            f"Risk sizing {result.pair} {result.decision}: "
            f"{result.lots:.4f} lots ({result.units:.2f} base units), "
            f"max loss {result.worst_case_loss:.2f} {result.account_currency}."
        )


def cmd_risk_report(risk: RiskAssessment) -> str:
    """Format a RiskAssessment without hiding invalid sizing."""
    if risk.decision not in ("BUY", "SELL"):
        return risk.recommendation
    if not risk.valid:
        return (
            f"RISK ENGINE - {risk.pair} {risk.decision}\n"
            f"INVALID (fail-closed): {', '.join(risk.blocking_reasons)}"
        )
    costs = "included as declared" if risk.costs_included else "not all-in"
    return "\n".join(
        (
            f"RISK ENGINE - {risk.pair} {risk.decision}",
            f"Entry/stop: {risk.entry_price:.5f} / {risk.stop_loss:.5f}",
            f"Stop: {risk.stop_distance_price:.5f} price, {risk.sl_pips:.1f} pips",
            f"Size: {risk.lots:.4f} lots / {risk.units:.2f} base units",
            f"Risk budget: {risk.risk_amount:.2f} {risk.account_currency}",
            f"Worst-case declared loss: {risk.worst_case_loss:.2f} ({costs})",
        )
    )


__all__ = ["InstrumentMetadata", "RiskAssessment", "RiskEngine", "cmd_risk_report"]
