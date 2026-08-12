"""Canonical boundary for account state and broker risk metadata.

The resolver deliberately has no financial defaults.  A normal pipeline can
load an updateable JSON document through ``ASTRA_RISK_CONFIG_PATH``; advanced
callers can inject a mapping, an account-state provider, or a currency
converter.  Incomplete data is returned with explicit blocking reasons so the
Risk Engine can fail closed.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


AccountStateProvider = Callable[[str], Mapping[str, Any] | None]
CurrencyConverter = Callable[[str, str], float | None]


def normalize_instrument_symbol(symbol: object) -> str:
    """Normalize common Forex pair spellings without guessing currencies."""
    return "".join(
        character
        for character in str(symbol or "").upper()
        if character.isalnum()
    )


@dataclass
class RiskConfigResolution:
    pair: str
    valid: bool
    config: dict[str, Any] = field(default_factory=dict)
    blocking_reasons: list[str] = field(default_factory=list)

    def to_engine_config(self) -> dict[str, Any]:
        config = dict(self.config)
        config["configuration_blocking_reasons"] = list(self.blocking_reasons)
        return config


class RiskConfigResolver:
    """Resolve one pair's stable metadata and current account state."""

    ENV_PATH = "ASTRA_RISK_CONFIG_PATH"
    REQUIRED_INSTRUMENT_FIELDS = (
        "symbol",
        "asset_class",
        "base_currency",
        "quote_currency",
        "pip_size",
        "contract_size",
    )

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        config_path: str | Path | None = None,
        account_state_provider: AccountStateProvider | None = None,
        currency_converter: CurrencyConverter | None = None,
    ):
        self._config = dict(config) if config is not None else None
        self._config_path = Path(config_path) if config_path else None
        self._account_state_provider = account_state_provider
        self._currency_converter = currency_converter

    @classmethod
    def from_environment(cls) -> "RiskConfigResolver":
        path = os.environ.get(cls.ENV_PATH)
        return cls(config_path=path) if path else cls()

    def resolve(self, pair: str) -> RiskConfigResolution:
        normalized_pair = normalize_instrument_symbol(pair)
        source, source_errors = self._load_source()
        reasons = list(source_errors)

        account = self._mapping(source.get("account"))
        if self._account_state_provider is not None:
            try:
                current = self._account_state_provider(normalized_pair)
                if current is not None:
                    account.update(self._mapping(current))
            except Exception:
                reasons.append("account_state_provider_failed")

        instruments = self._mapping(source.get("instruments"))
        instrument = self._find_instrument(instruments, normalized_pair)
        if instrument is None:
            reasons.append("missing_instrument_metadata")
            instrument = {}

        account_equity = account.get("account_equity")
        account_currency = account.get("account_currency")
        if account_equity is None:
            reasons.append("missing_account_equity")
        elif not self._finite_positive(account_equity):
            reasons.append("invalid_account_equity")
        if not str(account_currency or "").strip():
            reasons.append("missing_account_currency")

        for field_name in self.REQUIRED_INSTRUMENT_FIELDS:
            value = instrument.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                reasons.append(f"missing_instrument_{field_name}")

        metadata_symbol = normalize_instrument_symbol(instrument.get("symbol"))
        if metadata_symbol and normalized_pair != metadata_symbol:
            reasons.append("instrument_symbol_mismatch")
        if instrument.get("asset_class") is not None and (
            str(instrument.get("asset_class")).lower() != "forex"
        ):
            reasons.append("unsupported_instrument_metadata")
        for field_name in ("pip_size", "contract_size"):
            value = instrument.get(field_name)
            if value is not None and not self._finite_positive(value):
                reasons.append(f"invalid_{field_name}")

        costs = self._mapping(source.get("costs"))
        instrument_costs = self._mapping(instrument.get("costs"))
        costs.update(instrument_costs)

        account_leverage_declared = "leverage" in account
        instrument_leverage_declared = "leverage" in instrument
        account_leverage = account.get("leverage")
        instrument_leverage = instrument.get("leverage")
        account_leverage_valid = (
            not account_leverage_declared
            or self._finite_positive(account_leverage)
        )
        instrument_leverage_valid = (
            not instrument_leverage_declared
            or self._finite_positive(instrument_leverage)
        )
        if not account_leverage_valid:
            reasons.append("invalid_account_leverage")
        if not instrument_leverage_valid:
            reasons.append("invalid_instrument_leverage")

        effective_leverage = None
        if account_leverage_valid and instrument_leverage_valid:
            leverage_limits = [
                float(value)
                for declared, value in (
                    (account_leverage_declared, account_leverage),
                    (instrument_leverage_declared, instrument_leverage),
                )
                if declared
            ]
            if leverage_limits:
                effective_leverage = min(leverage_limits)

        engine_instrument = dict(instrument)
        engine_instrument.pop("leverage", None)

        engine_config: dict[str, Any] = {
            "account_equity": account_equity,
            "account_currency": account_currency,
            "available_margin": account.get("available_margin"),
            "account_leverage": account_leverage,
            "instrument_leverage": instrument_leverage,
            "leverage": effective_leverage,
            "instrument_metadata": (
                {normalized_pair: engine_instrument} if instrument else None
            ),
        }
        for name in (
            "commission_per_lot",
            "spread_price",
            "slippage_price",
            "costs_in_entry_stop",
        ):
            if name in costs:
                engine_config[name] = costs[name]

        converter = self._currency_converter
        if converter is not None:
            engine_config["currency_converter"] = converter
        else:
            conversion_rate = self._find_conversion_rate(
                source.get("conversion_rates"),
                instrument.get("quote_currency"),
                account_currency,
            )
            if conversion_rate is not None:
                if self._finite_positive(conversion_rate):
                    engine_config["conversion_rate"] = conversion_rate
                else:
                    reasons.append("missing_or_invalid_conversion_rate")
            elif (
                str(instrument.get("quote_currency") or "").upper()
                and str(account_currency or "").upper()
                and str(instrument.get("quote_currency")).upper()
                != str(account_currency).upper()
            ):
                reasons.append("missing_or_invalid_conversion_rate")

        reasons = list(dict.fromkeys(reasons))
        return RiskConfigResolution(
            pair=normalized_pair,
            valid=not reasons,
            config=engine_config,
            blocking_reasons=reasons,
        )

    def _load_source(self) -> tuple[dict[str, Any], list[str]]:
        if self._config is not None:
            return dict(self._config), []
        if self._config_path is None:
            return {}, ["risk_config_source_not_configured"]
        try:
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}, ["risk_config_source_unreadable"]
        if not isinstance(payload, dict):
            return {}, ["risk_config_source_invalid"]
        return payload, []

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _finite_positive(value: object) -> bool:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(number) and number > 0.0

    @classmethod
    def _find_instrument(
        cls,
        instruments: Mapping[str, Any],
        normalized_pair: str,
    ) -> dict[str, Any] | None:
        for key, value in instruments.items():
            if normalize_instrument_symbol(key) == normalized_pair and isinstance(value, Mapping):
                return dict(value)
        return None

    @staticmethod
    def _find_conversion_rate(
        rates: object,
        source_currency: object,
        target_currency: object,
    ) -> object:
        if not isinstance(rates, Mapping):
            return None
        source = str(source_currency or "").upper()
        target = str(target_currency or "").upper()
        if not source or not target or source == target:
            return None
        normalized_candidates = {source + target, f"{source}:{target}"}
        for key, value in rates.items():
            normalized_key = str(key).upper().replace("/", "").replace("_", "")
            if normalized_key in normalized_candidates:
                return value
        nested = rates.get(source)
        if isinstance(nested, Mapping):
            return nested.get(target)
        return None


__all__ = [
    "AccountStateProvider",
    "CurrencyConverter",
    "RiskConfigResolution",
    "RiskConfigResolver",
    "normalize_instrument_symbol",
]
