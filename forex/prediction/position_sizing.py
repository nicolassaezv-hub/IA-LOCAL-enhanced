"""Position sizing with explicit financial units.

The canonical calculation is expressed in lots for broker constraints and in
base-currency units for the backward-compatible ``units`` field.  No market
metadata or FX conversion is guessed.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Callable


MIN_RISK_PCT = 0.005
MAX_RISK_PCT = 0.02
KELLY_FRACTION = 0.25
MIN_TRADES = 20

CurrencyConverter = Callable[[str, str], float | None]


@dataclass(frozen=True)
class InstrumentMetadata:
    """Broker/instrument facts required for exact Forex sizing.

    ``contract_size`` is base-currency units per lot. ``pip_size`` and all
    prices are quote-currency units per one base-currency unit.
    """

    symbol: str
    asset_class: str
    base_currency: str | None
    quote_currency: str | None
    pip_size: float | None
    contract_size: float | None
    min_lot: float | None = None
    max_lot: float | None = None
    lot_step: float | None = None
    leverage: float | None = None

    @classmethod
    def from_mapping(cls, values: dict) -> "InstrumentMetadata":
        return cls(
            symbol=str(values.get("symbol", "")),
            asset_class=str(values.get("asset_class", "")),
            base_currency=values.get("base_currency"),
            quote_currency=values.get("quote_currency"),
            pip_size=values.get("pip_size"),
            contract_size=values.get("contract_size"),
            min_lot=values.get("min_lot"),
            max_lot=values.get("max_lot"),
            lot_step=values.get("lot_step"),
            leverage=values.get("leverage"),
        )


@dataclass
class PositionSizingResult:
    valid: bool = False
    risk_amount: float = 0.0
    risk_fraction: float = 0.0
    account_currency: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    side: str = ""
    entry: float = 0.0
    stop: float = 0.0
    stop_distance_price: float = 0.0
    pip_size: float = 0.0
    stop_pips: float = 0.0
    contract_size: float = 0.0
    pip_value_per_lot: float = 0.0
    loss_per_unit: float = 0.0
    loss_per_lot: float = 0.0
    conversion_rate: float = 0.0
    raw_position_size: float = 0.0
    raw_position_size_unit: str = "lots"
    risk_limited_size: float = 0.0
    margin_limited_size: float | None = None
    final_position_size: float = 0.0
    final_position_size_unit: str = "lots"
    lots: float = 0.0
    units: float = 0.0
    leverage: float | None = None
    available_margin: float | None = None
    margin_required: float | None = None
    stop_loss_amount: float = 0.0
    additional_cost_amount: float = 0.0
    worst_case_loss: float = 0.0
    costs_included: bool = False
    cost_assumptions: dict[str, object] = field(default_factory=dict)
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def _finite_nonnegative(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0.0


def _floor_to_step(value: float, step: float) -> float:
    """Round down to a broker step without increasing financial exposure."""
    try:
        quotient = value / step
        nearest_steps = round(quotient)
        if math.isclose(quotient, nearest_steps, rel_tol=1e-12, abs_tol=1e-12):
            return float(Decimal(nearest_steps) * Decimal(str(step)))
        decimal_value = Decimal(str(value))
        decimal_step = Decimal(str(step))
        steps = (decimal_value / decimal_step).to_integral_value(rounding=ROUND_FLOOR)
        return float(steps * decimal_step)
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return 0.0


def calculate_forex_position_size(
    *,
    instrument: InstrumentMetadata | dict | None,
    account_equity: float | None,
    risk_fraction: float,
    account_currency: str | None,
    side: str,
    entry: float,
    stop: float,
    conversion_rate: float | None = None,
    currency_converter: CurrencyConverter | None = None,
    max_risk_fraction: float = MAX_RISK_PCT,
    leverage: float | None = None,
    available_margin: float | None = None,
    require_margin_validation: bool = False,
    commission_per_lot: float | None = None,
    spread_price: float | None = None,
    slippage_price: float | None = None,
    costs_in_entry_stop: bool = False,
) -> PositionSizingResult:
    """Calculate a Forex position without implicit unit or currency defaults.

    ``conversion_rate`` means account-currency units per one quote-currency
    unit. ``commission_per_lot`` is the total account-currency commission for
    one lot over the declared stop-out path; spread and slippage are
    quote-currency price distances. Leverage is used only for margin.
    """
    result = PositionSizingResult(
        risk_fraction=risk_fraction,
        account_currency=str(account_currency or "").upper(),
        side=str(side or "").upper(),
        entry=entry,
        stop=stop,
        available_margin=available_margin,
    )
    if _finite_positive(account_equity) and _finite_positive(risk_fraction):
        result.risk_amount = float(account_equity) * float(risk_fraction)

    if isinstance(instrument, dict):
        instrument = InstrumentMetadata.from_mapping(instrument)
    if instrument is None:
        result.blocking_reasons.append("missing_instrument_metadata")
        return result
    if instrument.asset_class.lower() != "forex":
        result.blocking_reasons.append("unsupported_instrument_metadata")
        return result

    base = str(instrument.base_currency or "").upper()
    quote = str(instrument.quote_currency or "").upper()
    result.base_currency = base
    result.quote_currency = quote
    if not base or not quote or not result.account_currency:
        result.blocking_reasons.append("missing_currency_metadata")
    if not _finite_positive(instrument.pip_size):
        result.blocking_reasons.append("invalid_pip_size")
    if not _finite_positive(instrument.contract_size):
        result.blocking_reasons.append("invalid_contract_size")
    if result.side not in ("BUY", "SELL"):
        result.blocking_reasons.append("invalid_side")
    if account_equity is None:
        result.blocking_reasons.append("missing_account_equity")
    elif not _finite_positive(account_equity):
        result.blocking_reasons.append("invalid_account_equity")
    if not _finite_positive(risk_fraction):
        result.blocking_reasons.append("invalid_risk_fraction")
    elif not _finite_positive(max_risk_fraction) or risk_fraction > max_risk_fraction:
        result.blocking_reasons.append("risk_fraction_exceeds_limit")
    if not _finite_positive(entry) or not _finite_positive(stop):
        result.blocking_reasons.append("invalid_entry_or_stop")
    elif entry == stop:
        result.blocking_reasons.append("zero_stop_distance")
    elif result.side == "BUY" and stop >= entry:
        result.blocking_reasons.append("invalid_buy_stop_geometry")
    elif result.side == "SELL" and stop <= entry:
        result.blocking_reasons.append("invalid_sell_stop_geometry")

    for name, value in (
        ("min_lot", instrument.min_lot),
        ("max_lot", instrument.max_lot),
        ("lot_step", instrument.lot_step),
    ):
        if value is not None and not _finite_positive(value):
            result.blocking_reasons.append(f"invalid_{name}")
    if (
        instrument.min_lot is not None
        and instrument.max_lot is not None
        and _finite_positive(instrument.min_lot)
        and _finite_positive(instrument.max_lot)
        and instrument.min_lot > instrument.max_lot
    ):
        result.blocking_reasons.append("min_lot_exceeds_max_lot")
    if result.blocking_reasons:
        return result

    result.pip_size = float(instrument.pip_size)
    result.contract_size = float(instrument.contract_size)
    result.stop_distance_price = abs(float(entry) - float(stop))
    result.stop_pips = result.stop_distance_price / result.pip_size

    if quote == result.account_currency:
        if conversion_rate is not None and (
            not _finite_positive(conversion_rate)
            or not math.isclose(float(conversion_rate), 1.0, rel_tol=0.0, abs_tol=1e-12)
        ):
            result.blocking_reasons.append("invalid_identity_conversion_rate")
            return result
        result.conversion_rate = 1.0
    else:
        rate = conversion_rate
        if rate is None and currency_converter is not None:
            try:
                rate = currency_converter(quote, result.account_currency)
            except Exception:
                result.blocking_reasons.append("currency_conversion_failed")
                return result
        if not _finite_positive(rate):
            result.blocking_reasons.append("missing_or_invalid_conversion_rate")
            return result
        result.conversion_rate = float(rate)

    result.pip_value_per_lot = (
        result.pip_size * result.contract_size * result.conversion_rate
    )
    stop_loss_per_lot = (
        result.stop_distance_price * result.contract_size * result.conversion_rate
    )

    cost_per_lot = 0.0
    embedded_entry_stop_costs = bool(costs_in_entry_stop)
    result.cost_assumptions = {
        "commission_per_lot_account_currency": commission_per_lot,
        "spread_price_quote_currency_per_base_unit": spread_price,
        "slippage_price_quote_currency_per_base_unit": slippage_price,
        "spread_and_slippage_already_in_entry_stop": embedded_entry_stop_costs,
        "commission": "unknown/not_included",
        "spread": "embedded" if embedded_entry_stop_costs else "unknown/not_included",
        "slippage": "embedded" if embedded_entry_stop_costs else "unknown/not_included",
    }
    if commission_per_lot is None:
        result.warnings.append("commission_not_included")
    elif not _finite_nonnegative(commission_per_lot):
        result.blocking_reasons.append("invalid_commission")
    else:
        cost_per_lot += float(commission_per_lot)
        result.cost_assumptions["commission"] = "explicitly_declared"

    for name, value in (("spread", spread_price), ("slippage", slippage_price)):
        if embedded_entry_stop_costs:
            result.cost_assumptions[name] = "embedded"
            if value is not None and not _finite_nonnegative(value):
                result.blocking_reasons.append(f"invalid_{name}")
            elif value is not None:
                result.warnings.append(f"{name}_ignored_already_in_entry_stop")
        elif value is None:
            result.warnings.append(f"{name}_not_included")
        elif not _finite_nonnegative(value):
            result.blocking_reasons.append(f"invalid_{name}")
        else:
            cost_per_lot += float(value) * result.contract_size * result.conversion_rate
            result.cost_assumptions[name] = "explicitly_declared"
    result.costs_included = all(
        result.cost_assumptions[name] != "unknown/not_included"
        for name in ("commission", "spread", "slippage")
    )
    if result.blocking_reasons:
        return result

    result.loss_per_lot = stop_loss_per_lot + cost_per_lot
    result.loss_per_unit = result.loss_per_lot / result.contract_size
    if not _finite_positive(result.loss_per_lot):
        result.blocking_reasons.append("invalid_loss_per_lot")
        return result

    result.raw_position_size = result.risk_amount / result.loss_per_lot
    if instrument.lot_step is not None:
        step = float(instrument.lot_step)
        quotient = result.raw_position_size / step
        nearest_steps = round(quotient)
        if math.isclose(quotient, nearest_steps, rel_tol=1e-12, abs_tol=1e-12):
            result.raw_position_size = nearest_steps * step
    result.risk_limited_size = result.raw_position_size
    final_lots = result.risk_limited_size

    resolved_leverage = leverage if leverage is not None else instrument.leverage
    result.leverage = float(resolved_leverage) if _finite_positive(resolved_leverage) else None
    if resolved_leverage is not None and result.leverage is None:
        result.blocking_reasons.append("invalid_leverage")
    if available_margin is not None and not _finite_nonnegative(available_margin):
        result.blocking_reasons.append("invalid_available_margin")
    if require_margin_validation and resolved_leverage is None:
        result.blocking_reasons.append("missing_or_invalid_leverage")
    if require_margin_validation and available_margin is None:
        result.blocking_reasons.append("missing_or_invalid_available_margin")
    if (resolved_leverage is None) != (available_margin is None):
        result.warnings.append("margin_not_validated_incomplete_metadata")
    if result.blocking_reasons:
        return result

    if result.leverage is not None and available_margin is not None:
        margin_per_lot = (
            result.contract_size * float(entry) * result.conversion_rate / result.leverage
        )
        if not _finite_positive(margin_per_lot):
            result.blocking_reasons.append("invalid_margin_per_lot")
            return result
        result.margin_limited_size = float(available_margin) / margin_per_lot
        if instrument.lot_step is not None:
            margin_steps = result.margin_limited_size / float(instrument.lot_step)
            nearest_margin_steps = round(margin_steps)
            if math.isclose(
                margin_steps,
                nearest_margin_steps,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                result.margin_limited_size = (
                    nearest_margin_steps * float(instrument.lot_step)
                )
        if instrument.min_lot is not None and result.margin_limited_size < float(instrument.min_lot):
            result.blocking_reasons.append("insufficient_available_margin")
            return result
        final_lots = min(final_lots, result.margin_limited_size)
    elif not require_margin_validation:
        result.warnings.append("margin_viability_not_validated")

    if instrument.max_lot is not None:
        final_lots = min(final_lots, float(instrument.max_lot))
    if instrument.min_lot is not None and final_lots < float(instrument.min_lot):
        result.blocking_reasons.append("position_below_min_lot")
        return result
    if instrument.lot_step is not None:
        final_lots = _floor_to_step(final_lots, float(instrument.lot_step))
    if not _finite_positive(final_lots):
        result.blocking_reasons.append("position_size_not_positive")
        return result
    if instrument.min_lot is not None and final_lots < float(instrument.min_lot):
        result.blocking_reasons.append("position_below_min_lot")
        return result

    result.final_position_size = final_lots
    result.lots = final_lots
    result.units = final_lots * result.contract_size
    result.stop_loss_amount = final_lots * stop_loss_per_lot
    result.additional_cost_amount = final_lots * cost_per_lot
    result.worst_case_loss = final_lots * result.loss_per_lot
    if result.worst_case_loss > result.risk_amount * (1.0 + 1e-12):
        result.blocking_reasons.append("rounded_position_exceeds_risk_budget")
        result.final_position_size = result.lots = result.units = 0.0
        return result
    if result.leverage is not None:
        result.margin_required = (
            final_lots
            * result.contract_size
            * float(entry)
            * result.conversion_rate
            / result.leverage
        )
        if (
            available_margin is not None
            and result.margin_required > float(available_margin) * (1.0 + 1e-12)
        ):
            result.blocking_reasons.append("margin_required_exceeds_available")
            result.valid = False
            result.final_position_size = result.lots = result.units = 0.0
            return result
    result.valid = True
    return result


class PositionSizer:
    """Backward-compatible Kelly selector backed by canonical Forex sizing."""

    def __init__(
        self,
        account_balance: float | None = None,
        kelly_fraction: float = KELLY_FRACTION,
        min_risk_pct: float = MIN_RISK_PCT,
        max_risk_pct: float = MAX_RISK_PCT,
        *,
        account_currency: str | None = None,
        instrument_metadata: InstrumentMetadata | dict | None = None,
        conversion_rate: float | None = None,
    ):
        self.account_balance = account_balance
        self.kelly_fraction = kelly_fraction
        self.min_risk_pct = min_risk_pct
        self.max_risk_pct = max_risk_pct
        self.account_currency = account_currency
        self.instrument_metadata = instrument_metadata
        self.conversion_rate = conversion_rate

    def calculate(
        self,
        signal: dict,
        trade_history: list,
        price: float = 1.0,
        stop_loss_pips: float = 20.0,
        *,
        instrument_metadata: InstrumentMetadata | dict | None = None,
        account_currency: str | None = None,
        conversion_rate: float | None = None,
    ) -> dict:
        action = str(signal.get("action", "HOLD")).upper()
        if action == "HOLD":
            return {
                "valid": True, "action": "HOLD", "risk_pct": 0.0,
                "risk_fraction": 0.0, "risk_usd": 0.0, "risk_amount": 0.0,
                "units": 0.0, "lots": 0.0, "kelly_raw": 0.0,
                "method": "hold", "n_trades": len(trade_history),
                "confidence": float(signal.get("confidence", 0.0)),
                "reason": signal.get("hold_reason", "Signal HOLD - no trade"),
                "blocking_reasons": [],
            }

        wins = [t["pnl"] for t in trade_history if t.get("pnl", 0) > 0]
        losses = [t["pnl"] for t in trade_history if t.get("pnl", 0) <= 0]
        n = len(trade_history)
        if n < MIN_TRADES or not wins or not losses:
            risk_fraction = self.min_risk_pct
            kelly_raw = 0.0
            method = "conservative"
        else:
            win_rate = len(wins) / n
            avg_win = sum(wins) / len(wins)
            avg_loss = abs(sum(losses) / len(losses))
            if avg_loss < 1e-9:
                risk_fraction = self.min_risk_pct
                kelly_raw = 0.0
                method = "conservative"
            else:
                b = avg_win / avg_loss
                kelly_raw = win_rate - (1 - win_rate) / b
                risk_fraction = max(
                    self.min_risk_pct,
                    min(self.max_risk_pct, kelly_raw * self.kelly_fraction),
                )
                method = "kelly"

        confidence = float(signal.get("confidence", 0.5))
        risk_fraction *= min(1.0, confidence / 0.75)
        risk_fraction = max(self.min_risk_pct, min(self.max_risk_pct, risk_fraction))
        metadata = instrument_metadata or self.instrument_metadata
        if isinstance(metadata, dict):
            metadata = InstrumentMetadata.from_mapping(metadata)
        if metadata is None or not _finite_positive(getattr(metadata, "pip_size", None)):
            sizing = calculate_forex_position_size(
                instrument=metadata,
                account_equity=self.account_balance,
                risk_fraction=risk_fraction,
                account_currency=account_currency or self.account_currency,
                side=action,
                entry=price,
                stop=price,
                max_risk_fraction=self.max_risk_pct,
            )
        else:
            distance = float(stop_loss_pips) * float(metadata.pip_size)
            stop = price - distance if action == "BUY" else price + distance
            sizing = calculate_forex_position_size(
                instrument=metadata,
                account_equity=self.account_balance,
                risk_fraction=risk_fraction,
                account_currency=account_currency or self.account_currency,
                side=action,
                entry=price,
                stop=stop,
                conversion_rate=(
                    conversion_rate if conversion_rate is not None else self.conversion_rate
                ),
                max_risk_fraction=self.max_risk_pct,
            )
        payload = sizing.to_dict()
        payload.update({
            "action": action,
            "risk_pct": round(risk_fraction * 100.0, 3),
            "risk_usd": round(sizing.risk_amount, 2),
            "risk_account_currency": round(sizing.risk_amount, 2),
            "kelly_raw": round(kelly_raw, 4),
            "method": method,
            "n_trades": n,
            "confidence": round(confidence, 4),
        })
        return payload

    def update_balance(self, new_balance: float):
        self.account_balance = new_balance


def cmd_position_size(
    pair: str = "EURUSD",
    balance: float | None = None,
    signal: dict | None = None,
    trade_history: list | None = None,
) -> str:
    """CLI boundary; refuses to invent equity or instrument metadata."""
    signal = signal or {"action": "BUY", "confidence": 0.75}
    result = PositionSizer(account_balance=balance).calculate(signal, trade_history or [])
    if not result["valid"]:
        reasons = ", ".join(result["blocking_reasons"])
        return f"POSITION SIZING - {pair.upper()}\nInvalid (fail-closed): {reasons}"
    return (
        f"POSITION SIZING - {pair.upper()}\n"
        f"Risk: {result['risk_pct']:.3f}%\n"
        f"Lots: {result['lots']:.4f}\nUnits: {result['units']:.2f}"
    )


__all__ = [
    "InstrumentMetadata",
    "PositionSizer",
    "PositionSizingResult",
    "calculate_forex_position_size",
]
