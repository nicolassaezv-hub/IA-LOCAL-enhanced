"""A-09 deterministic tests for risk units, conversion, and position sizing."""

from __future__ import annotations

import math
import json
import importlib.util
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "forex" / "prediction"
PACKAGE_NAME = "_a09_risk_modules"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(MODULE_ROOT)]
sys.modules.setdefault(PACKAGE_NAME, package)
position_sizing = _load_module(
    f"{PACKAGE_NAME}.position_sizing", MODULE_ROOT / "position_sizing.py"
)
risk_config_resolver = _load_module(
    f"{PACKAGE_NAME}.risk_config_resolver", MODULE_ROOT / "risk_config_resolver.py"
)
risk_engine = _load_module(
    f"{PACKAGE_NAME}.risk_engine", MODULE_ROOT / "risk_engine.py"
)

InstrumentMetadata = position_sizing.InstrumentMetadata
PositionSizer = position_sizing.PositionSizer
calculate_forex_position_size = position_sizing.calculate_forex_position_size
RiskEngine = risk_engine.RiskEngine
RiskConfigResolver = risk_config_resolver.RiskConfigResolver
cmd_risk_report = risk_engine.cmd_risk_report


EURUSD = InstrumentMetadata(
    symbol="EURUSD",
    asset_class="forex",
    base_currency="EUR",
    quote_currency="USD",
    pip_size=0.0001,
    contract_size=100_000,
    min_lot=0.01,
    max_lot=100.0,
    lot_step=0.01,
)

USDJPY = InstrumentMetadata(
    symbol="USDJPY",
    asset_class="forex",
    base_currency="USD",
    quote_currency="JPY",
    pip_size=0.01,
    contract_size=100_000,
    min_lot=0.01,
    max_lot=100.0,
    lot_step=0.01,
)

EURJPY = replace(USDJPY, symbol="EURJPY", base_currency="EUR")


def size_eurusd(**overrides):
    values = {
        "instrument": EURUSD,
        "account_equity": 10_000.0,
        "risk_fraction": 0.01,
        "account_currency": "USD",
        "side": "BUY",
        "entry": 1.1000,
        "stop": 1.0950,
        "commission_per_lot": 0.0,
        "spread_price": 0.0,
        "slippage_price": 0.0,
    }
    values.update(overrides)
    return calculate_forex_position_size(**values)


def complete_risk_source(**account_overrides):
    account = {
        "account_equity": 10_000.0,
        "account_currency": "USD",
    }
    account.update(account_overrides)
    return {
        "account": account,
        "instruments": {
            "EURUSD": {
                "symbol": "EUR/USD",
                "asset_class": "forex",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "pip_size": 0.0001,
                "contract_size": 100_000,
                "min_lot": 0.01,
                "max_lot": 100.0,
                "lot_step": 0.01,
            }
        },
        "costs": {
            "commission_per_lot": 0.0,
            "spread_price": 0.0,
            "slippage_price": 0.0,
        },
    }


class ForexSizingTests(unittest.TestCase):
    def test_eurusd_quote_equals_account_currency(self):
        result = size_eurusd()

        self.assertTrue(result.valid)
        self.assertEqual(result.conversion_rate, 1.0)
        self.assertAlmostEqual(result.stop_distance_price, 0.005)
        self.assertAlmostEqual(result.stop_pips, 50.0)
        self.assertAlmostEqual(result.pip_value_per_lot, 10.0)
        self.assertAlmostEqual(result.loss_per_lot, 500.0)
        self.assertAlmostEqual(result.raw_position_size, 0.2)
        self.assertAlmostEqual(result.lots, 0.2)
        self.assertAlmostEqual(result.units, 20_000.0)
        self.assertAlmostEqual(result.worst_case_loss, result.risk_amount)

    def test_usdjpy_uses_jpy_pip_and_explicit_jpy_to_usd_conversion(self):
        result = calculate_forex_position_size(
            instrument=USDJPY,
            account_equity=10_000.0,
            risk_fraction=0.01,
            account_currency="USD",
            side="BUY",
            entry=150.0,
            stop=149.0,
            conversion_rate=1.0 / 150.0,
            commission_per_lot=0.0,
            spread_price=0.0,
            slippage_price=0.0,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.pip_size, 0.01)
        self.assertAlmostEqual(result.stop_pips, 100.0)
        self.assertAlmostEqual(result.pip_value_per_lot, 1000.0 / 150.0)
        self.assertLessEqual(result.worst_case_loss, result.risk_amount + 1e-9)

    def test_eurjpy_cross_uses_injected_conversion_boundary(self):
        calls = []

        def convert(source, target):
            calls.append((source, target))
            return 0.00625

        result = calculate_forex_position_size(
            instrument=EURJPY,
            account_equity=10_000.0,
            risk_fraction=0.01,
            account_currency="USD",
            side="SELL",
            entry=160.0,
            stop=160.8,
            currency_converter=convert,
            commission_per_lot=0.0,
            spread_price=0.0,
            slippage_price=0.0,
        )

        self.assertTrue(result.valid)
        self.assertEqual(calls, [("JPY", "USD")])
        self.assertAlmostEqual(result.loss_per_lot, 500.0)
        self.assertAlmostEqual(result.lots, 0.2)

    def test_risk_fraction_monotonicity(self):
        low = size_eurusd(risk_fraction=0.005)
        high = size_eurusd(risk_fraction=0.01)

        self.assertTrue(low.valid and high.valid)
        self.assertGreaterEqual(high.final_position_size, low.final_position_size)

    def test_stop_distance_inverse_monotonicity(self):
        near = size_eurusd(stop=1.0975)
        far = size_eurusd(stop=1.0900)

        self.assertTrue(near.valid and far.valid)
        self.assertLessEqual(far.final_position_size, near.final_position_size)

    def test_leverage_does_not_increase_risk_budget_or_risk_limited_size(self):
        low = size_eurusd(
            leverage=10.0,
            available_margin=1_000_000.0,
            require_margin_validation=True,
        )
        high = size_eurusd(
            leverage=100.0,
            available_margin=1_000_000.0,
            require_margin_validation=True,
        )

        self.assertTrue(low.valid and high.valid)
        self.assertEqual(low.risk_amount, high.risk_amount)
        self.assertEqual(low.risk_limited_size, high.risk_limited_size)
        self.assertEqual(low.final_position_size, high.final_position_size)
        self.assertGreater(low.margin_required, high.margin_required)

    def test_final_size_respects_risk_and_margin_limits(self):
        result = size_eurusd(
            leverage=20.0,
            available_margin=550.0,
            require_margin_validation=True,
        )

        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.risk_limited_size, 0.2)
        self.assertAlmostEqual(result.margin_limited_size, 0.1)
        self.assertAlmostEqual(result.final_position_size, 0.1)
        self.assertLessEqual(result.margin_required, result.available_margin + 1e-9)

    def test_reward_follows_final_margin_limited_lots(self):
        config = {
            **RiskConfigResolver(
                complete_risk_source(available_margin=550.0, leverage=20.0)
            ).resolve("EURUSD").to_engine_config(),
            "min_risk_pct": 1.0,
            "max_risk_pct": 1.0,
        }
        result = RiskEngine(config).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.005 / 1.5,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EURUSD",
            rr_ratio=2.0,
        )

        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.risk_limited_size, 0.2)
        self.assertAlmostEqual(result.margin_limited_size, 0.1)
        self.assertAlmostEqual(result.lots, 0.1)
        self.assertAlmostEqual(result.gross_reward_per_lot, 1_000.0)
        self.assertAlmostEqual(result.reward_amount, 100.0)
        self.assertNotAlmostEqual(result.reward_amount, result.risk_amount * result.rr_ratio)
        self.assertAlmostEqual(result.effective_rr, 2.0)

    def test_final_loss_never_exceeds_budget_and_rounding_is_down(self):
        result = size_eurusd(
            account_equity=23_700.0,
            entry=1.1000,
            stop=1.0900,
        )

        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.raw_position_size, 0.237)
        self.assertAlmostEqual(result.final_position_size, 0.23)
        self.assertLessEqual(result.final_position_size, result.raw_position_size)
        self.assertLessEqual(result.worst_case_loss, result.risk_amount + 1e-9)

    def test_pip_math_equals_generic_contract_math(self):
        result = size_eurusd()
        generic_loss = (
            result.stop_distance_price
            * result.contract_size
            * result.conversion_rate
        )
        pip_loss = result.stop_pips * result.pip_value_per_lot

        self.assertAlmostEqual(generic_loss, pip_loss)
        self.assertAlmostEqual(result.risk_amount / generic_loss, result.raw_position_size)

    def test_explicit_costs_reduce_size_and_unknown_costs_are_disclosed(self):
        unknown = size_eurusd(
            commission_per_lot=None,
            spread_price=None,
            slippage_price=None,
        )
        costed = size_eurusd(
            commission_per_lot=7.0,
            spread_price=0.0002,
            slippage_price=0.0001,
        )

        self.assertTrue(unknown.valid and costed.valid)
        self.assertFalse(unknown.costs_included)
        self.assertIn("commission_not_included", unknown.warnings)
        self.assertTrue(costed.costs_included)
        self.assertAlmostEqual(costed.loss_per_lot, 537.0)
        self.assertLess(costed.final_position_size, unknown.final_position_size)
        self.assertLessEqual(costed.worst_case_loss, costed.risk_amount)

    def test_spread_is_not_counted_twice_when_declared_in_entry_stop(self):
        result = size_eurusd(
            commission_per_lot=0.0,
            spread_price=0.0002,
            slippage_price=0.0,
            costs_in_entry_stop=True,
        )

        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.loss_per_lot, 500.0)
        self.assertIn("spread_ignored_already_in_entry_stop", result.warnings)

    def test_embedded_costs_do_not_emit_missing_spread_or_slippage_warnings(self):
        result = size_eurusd(
            commission_per_lot=None,
            spread_price=None,
            slippage_price=None,
            costs_in_entry_stop=True,
        )

        self.assertTrue(result.valid)
        self.assertNotIn("spread_not_included", result.warnings)
        self.assertNotIn("slippage_not_included", result.warnings)
        self.assertEqual(result.cost_assumptions["spread"], "embedded")
        self.assertEqual(result.cost_assumptions["slippage"], "embedded")
        self.assertEqual(
            result.cost_assumptions["commission"], "unknown/not_included"
        )
        self.assertFalse(result.costs_included)

    def test_max_lot_and_step_are_conservative(self):
        metadata = replace(EURUSD, max_lot=0.157, lot_step=0.01)
        result = size_eurusd(instrument=metadata, stop=1.0995)

        self.assertTrue(result.valid)
        self.assertAlmostEqual(result.final_position_size, 0.15)
        self.assertLessEqual(result.final_position_size, metadata.max_lot)

    def test_legacy_position_sizer_uses_pip_size_not_price_scaled_pips(self):
        sizer = PositionSizer(
            account_balance=10_000.0,
            account_currency="USD",
            instrument_metadata=replace(EURUSD, lot_step=None),
        )
        result = sizer.calculate(
            {"action": "BUY", "confidence": 0.75},
            [],
            price=1.2,
            stop_loss_pips=20.0,
        )

        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["stop_distance_price"], 0.002)
        self.assertAlmostEqual(result["units"], 25_000.0)

    def test_position_sizer_without_explicit_equity_fails_closed(self):
        result = PositionSizer(
            account_currency="USD",
            instrument_metadata=EURUSD,
        ).calculate(
            {"action": "BUY", "confidence": 0.75},
            [],
            price=1.1,
            stop_loss_pips=20.0,
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["lots"], 0.0)
        self.assertIn("missing_account_equity", result["blocking_reasons"])


class FailClosedSizingTests(unittest.TestCase):
    def assert_blocked(self, result, reason):
        self.assertFalse(result.valid)
        self.assertEqual(result.final_position_size, 0.0)
        self.assertEqual(result.units, 0.0)
        self.assertIn(reason, result.blocking_reasons)

    def test_missing_conversion(self):
        result = calculate_forex_position_size(
            instrument=EURJPY,
            account_equity=10_000.0,
            risk_fraction=0.01,
            account_currency="USD",
            side="BUY",
            entry=160.0,
            stop=159.0,
        )
        self.assert_blocked(result, "missing_or_invalid_conversion_rate")

    def test_zero_stop_distance(self):
        self.assert_blocked(size_eurusd(stop=1.1), "zero_stop_distance")

    def test_invalid_buy_and_sell_geometry(self):
        self.assert_blocked(size_eurusd(stop=1.101), "invalid_buy_stop_geometry")
        self.assert_blocked(
            size_eurusd(side="SELL", stop=1.099),
            "invalid_sell_stop_geometry",
        )

    def test_nan_is_rejected(self):
        self.assert_blocked(size_eurusd(entry=math.nan), "invalid_entry_or_stop")

    def test_non_positive_equity(self):
        for equity in (0.0, -1.0):
            with self.subTest(equity=equity):
                self.assert_blocked(
                    size_eurusd(account_equity=equity),
                    "invalid_account_equity",
                )

    def test_missing_account_equity_blocks_directional_sizing(self):
        result = RiskEngine(
            {
                "account_currency": "USD",
                "instrument_metadata": {"EURUSD": EURUSD},
            }
        ).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.001,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EURUSD",
        )

        self.assert_blocked(result, "missing_account_equity")
        self.assertEqual("HOLD" if not result.valid else result.decision, "HOLD")

    def test_pair_and_metadata_symbol_must_match(self):
        result = RiskEngine(
            {
                "account_equity": 10_000.0,
                "account_currency": "USD",
                "instrument_metadata": {"EURUSD": USDJPY},
            }
        ).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.001,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EUR_USD",
        )

        self.assert_blocked(result, "instrument_symbol_mismatch")

    def test_zero_and_negative_contract_size(self):
        for contract_size in (0.0, -100_000.0):
            with self.subTest(contract_size=contract_size):
                self.assert_blocked(
                    size_eurusd(instrument=replace(EURUSD, contract_size=contract_size)),
                    "invalid_contract_size",
                )

    def test_invalid_pip_size_and_risk_fraction(self):
        self.assert_blocked(
            size_eurusd(instrument=replace(EURUSD, pip_size=0.0)),
            "invalid_pip_size",
        )
        self.assert_blocked(size_eurusd(risk_fraction=0.0), "invalid_risk_fraction")
        self.assert_blocked(size_eurusd(risk_fraction=-0.01), "invalid_risk_fraction")
        self.assert_blocked(
            size_eurusd(risk_fraction=0.03),
            "risk_fraction_exceeds_limit",
        )

    def test_unsupported_instrument_metadata(self):
        crypto = replace(
            EURUSD,
            symbol="BTCUSD",
            asset_class="crypto",
            base_currency="BTC",
        )
        self.assert_blocked(
            size_eurusd(instrument=crypto),
            "unsupported_instrument_metadata",
        )

    def test_lot_below_min_is_not_forced_up(self):
        result = size_eurusd(
            instrument=replace(EURUSD, min_lot=0.1),
            account_equity=1_000.0,
            entry=1.1,
            stop=1.09,
        )
        self.assert_blocked(result, "position_below_min_lot")

    def test_margin_below_minimum_position_is_invalid(self):
        result = size_eurusd(
            leverage=20.0,
            available_margin=10.0,
            require_margin_validation=True,
        )
        self.assert_blocked(result, "insufficient_available_margin")
        self.assertLess(result.margin_limited_size, EURUSD.min_lot)

    def test_required_margin_metadata_cannot_be_omitted(self):
        result = size_eurusd(require_margin_validation=True)
        self.assert_blocked(result, "missing_or_invalid_leverage")
        self.assertIn("missing_or_invalid_available_margin", result.blocking_reasons)

    def test_risk_engine_requires_metadata_and_exposes_structured_invalidity(self):
        risk = RiskEngine(
            {"account_equity": 10_000.0, "account_currency": "USD"}
        ).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.001,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EURUSD",
        )

        self.assertFalse(risk.valid)
        self.assertEqual(risk.position_size, 0.0)
        self.assertIn("missing_instrument_metadata", risk.blocking_reasons)
        self.assertGreater(risk.risk_amount, 0.0)

    def test_risk_engine_accepts_explicit_metadata_without_changing_strategy(self):
        risk = RiskEngine(
            {
                "account_currency": "USD",
                "account_equity": 10_000.0,
                "instrument_metadata": {"EURUSD": EURUSD},
            }
        ).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.001,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EURUSD",
            commission_per_lot=0.0,
            spread_price=0.0,
            slippage_price=0.0,
        )

        self.assertTrue(risk.valid)
        self.assertEqual(risk.position_size, risk.units)
        self.assertEqual(risk.final_position_size, risk.lots)
        self.assertLess(risk.stop_loss, risk.entry_price)
        self.assertLessEqual(risk.worst_case_loss, risk.risk_amount + 1e-9)


class CanonicalRiskConfigTests(unittest.TestCase):
    def _assess(self, config):
        return RiskEngine(config).assess(
            decision="BUY",
            entry_price=1.1,
            atr=0.001,
            reliability_score=80.0,
            model_win_rate=0.6,
            pair="EURUSD",
        )

    def _predict_with_resolved_risk(self, pipeline):
        import pandas as pd
        from forex.prediction import integrated_pipeline

        frame = pd.DataFrame({"close": [1.1]})
        captured = {}

        class FakeDatasetBuilder:
            def __init__(self, _frame):
                pass

            def predict_features(self, n_rows, train_columns):
                return frame

        def build_context(*_args, **kwargs):
            risk = self._assess(kwargs["risk_config"])
            captured["risk"] = risk
            failures = []
            if not risk.valid:
                failures.append(
                    {
                        "component": "risk_engine",
                        "code": "risk_result_invalid",
                        "critical": True,
                        "reason": ", ".join(risk.blocking_reasons),
                    }
                )
            context = types.SimpleNamespace(
                circuit_breaker_active=False,
                circuit_breaker_state={"open": True},
                regime=None,
                mtf=types.SimpleNamespace(
                    coherence_score=80.0,
                    coherent=True,
                    forced_hold=False,
                ),
                news_active=False,
                news_sentiment="",
                volatility_level="normal",
                atr_percentile=50.0,
                model_win_rate=None,
                model_recent_predictions=0,
                risk=risk,
                protection_errors=failures,
            )
            context.to_dict = lambda: {
                "risk_engine": risk.to_dict(),
                "protection_errors": failures,
            }
            return context

        decision = Mock(
            return_value=types.SimpleNamespace(
                decision="BUY",
                explanation="approved",
                risk_level="medium",
                factors_for=[],
                factors_against=[],
                reliability_score=80.0,
                quality_tier="valid",
            )
        )
        tracker = Mock()
        pipeline.storage = types.SimpleNamespace(
            load_model_with_features=lambda pair: (None, None)
        )
        pipeline.predictor = types.SimpleNamespace(
            signal=lambda _features, pair: {
                "pair": pair,
                "action": "BUY",
                "confidence": 0.8,
            }
        )
        pipeline._pair_params = lambda _pair: (5, 2.0)
        pipeline.closed_loop_database = types.SimpleNamespace(
            get_symbol=lambda symbol: {"symbol_code": symbol, "status": "active"}
        )

        with patch.object(integrated_pipeline, "_load", return_value=frame), patch.object(
            integrated_pipeline,
            "build_features",
            side_effect=lambda value: value,
        ), patch.object(
            integrated_pipeline,
            "DatasetBuilder",
            FakeDatasetBuilder,
        ), patch(
            "forex.prediction.candlestick_patterns.detect_patterns",
            return_value={},
        ), patch(
            "forex.prediction.prediction_context.build_context",
            side_effect=build_context,
        ), patch(
            "forex.prediction.roadmap_v_integration.run_decision_engine",
            decision,
        ), patch(
            "forex.prediction.outcome_tracker.OutcomeTracker",
            return_value=tracker,
        ):
            result = pipeline.predict("unused.csv", pair="EURUSD")
        return result, captured["risk"], decision

    def test_canonical_complete_config_allows_valid_sizing(self):
        resolution = RiskConfigResolver(complete_risk_source()).resolve("EUR_USD")
        risk = self._assess(resolution.to_engine_config())

        self.assertTrue(resolution.valid)
        self.assertTrue(risk.valid)
        self.assertEqual(risk.decision, "BUY")
        self.assertGreater(risk.lots, 0.0)

    def test_canonical_incomplete_config_fails_closed(self):
        source = complete_risk_source()
        source["account"].pop("account_equity")
        resolution = RiskConfigResolver(source).resolve("EURUSD")
        risk = self._assess(resolution.to_engine_config())

        self.assertFalse(resolution.valid)
        self.assertFalse(risk.valid)
        self.assertEqual(risk.lots, 0.0)
        self.assertIn("missing_account_equity", risk.blocking_reasons)

    def test_effective_leverage_uses_lower_account_limit(self):
        source = complete_risk_source(leverage=20.0)
        source["instruments"]["EURUSD"]["leverage"] = 100.0

        resolution = RiskConfigResolver(source).resolve("EURUSD")

        self.assertTrue(resolution.valid)
        self.assertEqual(resolution.config["account_leverage"], 20.0)
        self.assertEqual(resolution.config["instrument_leverage"], 100.0)
        self.assertEqual(resolution.config["leverage"], 20.0)

    def test_effective_leverage_uses_lower_instrument_limit(self):
        source = complete_risk_source(leverage=100.0)
        source["instruments"]["EURUSD"]["leverage"] = 20.0

        resolution = RiskConfigResolver(source).resolve("EURUSD")

        self.assertTrue(resolution.valid)
        self.assertEqual(resolution.config["leverage"], 20.0)

    def test_invalid_account_leverage_fails_closed(self):
        source = complete_risk_source(leverage=math.nan)
        source["instruments"]["EURUSD"]["leverage"] = 20.0
        resolution = RiskConfigResolver(source).resolve("EURUSD")
        risk = self._assess(resolution.to_engine_config())

        self.assertFalse(resolution.valid)
        self.assertIsNone(resolution.config["leverage"])
        self.assertIn("invalid_account_leverage", resolution.blocking_reasons)
        self.assertFalse(risk.valid)
        self.assertEqual(risk.lots, 0.0)

    def test_invalid_instrument_leverage_fails_closed(self):
        source = complete_risk_source(leverage=20.0)
        source["instruments"]["EURUSD"]["leverage"] = 0.0
        resolution = RiskConfigResolver(source).resolve("EURUSD")
        risk = self._assess(resolution.to_engine_config())

        self.assertFalse(resolution.valid)
        self.assertIsNone(resolution.config["leverage"])
        self.assertIn("invalid_instrument_leverage", resolution.blocking_reasons)
        self.assertFalse(risk.valid)
        self.assertEqual(risk.lots, 0.0)

    def test_margin_uses_effective_account_leverage_limit(self):
        source = complete_risk_source(available_margin=550.0, leverage=20.0)
        source["instruments"]["EURUSD"]["leverage"] = 100.0
        resolution = RiskConfigResolver(source).resolve("EURUSD")

        risk = self._assess(resolution.to_engine_config())

        self.assertTrue(risk.valid)
        self.assertEqual(risk.leverage, 20.0)
        self.assertGreater(risk.risk_limited_size, risk.margin_limited_size)
        self.assertAlmostEqual(risk.margin_limited_size, 0.1)
        self.assertAlmostEqual(risk.lots, 0.1)
        self.assertAlmostEqual(risk.margin_required, 550.0)

    def test_invalid_cmd_risk_report_prints_fail_closed_once(self):
        resolution = RiskConfigResolver({}).resolve("EURUSD")
        risk = self._assess(resolution.to_engine_config())

        report = cmd_risk_report(risk)

        self.assertEqual(report.count("INVALID (fail-closed):"), 1)

    def test_pipeline_without_productive_config_resolves_to_downstream_hold(self):
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

        with patch.dict("os.environ", {}, clear=False):
            with patch.dict("os.environ", {"ASTRA_RISK_CONFIG_PATH": ""}):
                pipeline = ForexIntegratedPipeline()
        result, risk, decision = self._predict_with_resolved_risk(pipeline)

        self.assertFalse(risk.valid)
        self.assertEqual(result["raw_action"], "BUY")
        self.assertEqual(result["action"], "HOLD")
        self.assertIn("risk_engine", result["blocked_by"])
        self.assertIn("risk_config_source_not_configured", risk.blocking_reasons)
        self.assertFalse(result["roadmap_v_context"]["risk_engine"]["valid"])
        self.assertIn(
            "missing_account_equity",
            result["roadmap_v_context"]["risk_engine"]["blocking_reasons"],
        )
        decision.assert_not_called()

    def test_pipeline_complete_resolver_can_produce_valid_risk(self):
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

        resolver = RiskConfigResolver(complete_risk_source())
        pipeline = ForexIntegratedPipeline(risk_config_resolver=resolver)
        result, risk, decision = self._predict_with_resolved_risk(pipeline)

        self.assertTrue(risk.valid)
        self.assertEqual(risk.decision, "BUY")
        self.assertEqual(result["action"], "BUY")
        decision.assert_called_once()

    def test_normal_pipeline_loads_complete_config_from_environment_file(self):
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "risk.json"
            config_path.write_text(
                json.dumps(complete_risk_source()),
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"ASTRA_RISK_CONFIG_PATH": str(config_path)},
            ):
                pipeline = ForexIntegratedPipeline()
            risk = self._assess(pipeline._resolve_risk_config("EURUSD"))

        self.assertTrue(risk.valid)
        self.assertGreater(risk.lots, 0.0)

    def test_account_state_provider_supplies_updateable_account_values(self):
        source = complete_risk_source()
        source.pop("account")
        provider = Mock(
            return_value={
                "account_equity": 10_000.0,
                "account_currency": "USD",
            }
        )
        resolution = RiskConfigResolver(
            source,
            account_state_provider=provider,
        ).resolve("EURUSD")

        self.assertTrue(resolution.valid)
        provider.assert_called_once_with("EURUSD")

    def test_explicit_pipeline_risk_config_override_takes_precedence(self):
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

        override = {"account_equity": 12_345.0}
        resolver = Mock()
        pipeline = object.__new__(ForexIntegratedPipeline)
        pipeline.risk_config = override
        pipeline._risk_config_override_supplied = True
        pipeline.risk_config_resolver = resolver

        self.assertIs(pipeline._resolve_risk_config("EURUSD"), override)
        resolver.resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
