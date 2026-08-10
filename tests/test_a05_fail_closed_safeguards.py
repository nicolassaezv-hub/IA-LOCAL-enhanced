"""Regression tests for audit finding A-05 (financial fail-closed guards)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "forex" / "prediction" / "integrated_pipeline.py"


class _FakeSeries:
    def __init__(self, values):
        self.iloc = self
        self._values = values

    def __getitem__(self, index):
        return self._values[index]


class _FakeDataFrame:
    columns = ("close",)

    def __init__(self, close: float = 1.085):
        self._close = close

    def __len__(self):
        return 1

    def __getitem__(self, column):
        if column != "close":
            raise KeyError(column)
        return _FakeSeries([self._close])

    def tail(self, _rows):
        return self


def _module(name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _valid_mtf():
    return types.SimpleNamespace(
        coherence_score=82.0,
        coherent=True,
        forced_hold=False,
    )


def _valid_risk(action: str):
    return types.SimpleNamespace(
        decision=action,
        entry_price=1.085,
        stop_loss=1.080 if action == "BUY" else 1.090,
        take_profit=1.090 if action == "BUY" else 1.080,
        position_size=1000.0,
        rr_ratio=1.0,
        to_dict=lambda: {"decision": action},
    )


class FailClosedSafeguardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        forex_package = _module("forex")
        forex_package.__path__ = []
        prediction_package = _module("forex.prediction")
        prediction_package.__path__ = []

        cls.context_module = _module("forex.prediction.prediction_context")
        cls.roadmap_module = _module("forex.prediction.roadmap_v_integration")
        cls.candlestick_module = _module("forex.prediction.candlestick_patterns")
        cls.outcome_module = _module("forex.prediction.outcome_tracker")

        stubs = {
            "numpy": _module("numpy"),
            "pandas": _module("pandas", DataFrame=_FakeDataFrame),
            "forex": forex_package,
            "forex.prediction": prediction_package,
            "forex.prediction.feature_engineering": _module(
                "forex.prediction.feature_engineering", build_features=lambda df: df
            ),
            "forex.prediction.dataset_builder": _module(
                "forex.prediction.dataset_builder",
                DatasetBuilder=object,
                get_pair_config=lambda _pair: {"horizon": 5, "rr_ratio": 2.0},
            ),
            "forex.prediction.predictor": _module(
                "forex.prediction.predictor", ForexPredictor=object
            ),
            "forex.prediction.backtester": _module(
                "forex.prediction.backtester", ForexBacktester=object
            ),
            "forex.prediction.xgb_trainer": _module(
                "forex.prediction.xgb_trainer",
                ForexEnsembleTrainer=object,
                train_with_wfv=lambda *args, **kwargs: None,
            ),
            "forex.prediction.hyperparameter_tuner": _module(
                "forex.prediction.hyperparameter_tuner",
                ForexHyperparameterTuner=object,
            ),
            "forex.prediction.csv_adapter": _module(
                "forex.prediction.csv_adapter", adapt_csv=lambda *args, **kwargs: None
            ),
            "forex.prediction.candlestick_patterns": cls.candlestick_module,
            "forex.prediction.prediction_context": cls.context_module,
            "forex.prediction.roadmap_v_integration": cls.roadmap_module,
            "forex.prediction.outcome_tracker": cls.outcome_module,
        }

        cls.modules_patch = patch.dict(sys.modules, stubs)
        cls.modules_patch.start()
        spec = importlib.util.spec_from_file_location(
            "forex.prediction.integrated_pipeline", PIPELINE_PATH
        )
        cls.pipeline_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.pipeline_module
        spec.loader.exec_module(cls.pipeline_module)

    @classmethod
    def tearDownClass(cls):
        cls.modules_patch.stop()

    def _predict(
        self,
        raw_action: str,
        *,
        context_mode: str = "valid",
        decision_mode: str = "normal",
        optional_failure: bool = False,
    ):
        frame = _FakeDataFrame()

        class FakeDatasetBuilder:
            def __init__(self, _df):
                pass

            def predict_features(self, n_rows, train_columns):
                return frame

        ctx = types.SimpleNamespace(
            circuit_breaker_active=context_mode == "circuit_breaker",
            circuit_breaker_state={
                "open": context_mode != "circuit_breaker",
                "reason": "daily loss limit" if context_mode == "circuit_breaker" else "",
            },
            regime=None,
            mtf=(
                None
                if context_mode == "mtf_missing"
                else types.SimpleNamespace(
                    coherence_score=float("nan"),
                    coherent=True,
                    forced_hold=False,
                )
                if context_mode == "mtf_invalid"
                else _valid_mtf()
            ),
            news_active=False,
            news_sentiment="",
            volatility_level="normal",
            atr_percentile=50.0,
            model_win_rate=None,
            model_recent_predictions=0,
            risk=(
                None
                if raw_action not in ("BUY", "SELL") or context_mode == "risk_failure"
                else _valid_risk(raw_action)
            ),
            protection_errors=[],
        )
        if context_mode == "risk_invalid":
            ctx.risk = _valid_risk(raw_action)
            ctx.risk.position_size = 0.0
        ctx.to_dict = lambda: {
            "protection_errors": ctx.protection_errors,
            "circuit_breaker_active": ctx.circuit_breaker_active,
        }

        if context_mode == "context_exception":
            def build_context(*_args, **_kwargs):
                raise RuntimeError("context exploded")
        else:
            build_context = lambda *_args, **_kwargs: ctx
        self.context_module.build_context = build_context

        if decision_mode == "exception":
            def run_decision_engine(**_kwargs):
                raise RuntimeError("decision exploded")
        else:
            final_action = "HOLD" if decision_mode == "veto" else raw_action
            self.roadmap_module.run_decision_engine = lambda **_kwargs: types.SimpleNamespace(
                decision=final_action,
                explanation="normal veto" if decision_mode == "veto" else "approved",
                risk_level="medium",
                factors_for=[],
                factors_against=[],
                reliability_score=80.0,
                quality_tier="valid",
            )
            run_decision_engine = self.roadmap_module.run_decision_engine
        self.roadmap_module.run_decision_engine = run_decision_engine

        if optional_failure:
            def detect_patterns(_df):
                raise RuntimeError("candlestick exploded")
        else:
            detect_patterns = lambda _df: {}
        self.candlestick_module.detect_patterns = detect_patterns

        tracker = Mock()
        self.outcome_module.OutcomeTracker = lambda: tracker

        pipeline = object.__new__(self.pipeline_module.ForexIntegratedPipeline)
        pipeline.storage = types.SimpleNamespace(
            load_model_with_features=lambda pair: (None, None)
        )
        pipeline.predictor = types.SimpleNamespace(
            signal=lambda _features, pair: {
                "pair": pair,
                "action": raw_action,
                "confidence": 0.8,
            }
        )
        pipeline._pair_params = lambda _pair: (5, 2.0)

        with patch.object(self.pipeline_module, "_load", return_value=frame), patch.object(
            self.pipeline_module, "build_features", side_effect=lambda df: df
        ), patch.object(self.pipeline_module, "DatasetBuilder", FakeDatasetBuilder):
            result = pipeline.predict("unused.csv", pair="EURUSD")

        return result, tracker

    def assert_blocked(self, result, tracker, component: str):
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["signal"], "HOLD")
        self.assertEqual(result["safeguard_status"], "blocked")
        self.assertIn(component, result["blocked_by"])
        self.assertTrue(result["safeguard_failures"])
        tracker.record_prediction.assert_not_called()

    def test_buy_and_sell_pass_with_all_critical_protections_valid(self):
        for action in ("BUY", "SELL"):
            with self.subTest(action=action):
                result, tracker = self._predict(action)
                self.assertEqual(result["raw_action"], action)
                self.assertEqual(result["action"], action)
                self.assertEqual(result["signal"], action)
                self.assertEqual(result["safeguard_status"], "passed")
                tracker.record_prediction.assert_called_once()

    def test_active_circuit_breaker_blocks_trade(self):
        for action in ("BUY", "SELL"):
            with self.subTest(action=action):
                result, tracker = self._predict(action, context_mode="circuit_breaker")
                self.assertEqual(result["raw_action"], action)
                self.assert_blocked(result, tracker, "circuit_breaker")
                self.assertEqual(
                    result["safeguard_failures"][-1]["code"],
                    "circuit_breaker_active",
                )

    def test_build_context_exception_blocks_trade_and_exposes_cause(self):
        result, tracker = self._predict("BUY", context_mode="context_exception")
        self.assert_blocked(result, tracker, "prediction_context")
        error = result["protection_errors"][0]
        self.assertEqual(error["error_type"], "RuntimeError")
        self.assertEqual(error["error"], "context exploded")

    def test_missing_or_invalid_critical_mtf_blocks_trade(self):
        for mode in ("mtf_missing", "mtf_invalid"):
            with self.subTest(mode=mode):
                result, tracker = self._predict("BUY", context_mode=mode)
                self.assert_blocked(result, tracker, "mtf")
                self.assertIn("MTF", result["safeguard_failures"][0]["reason"])

    def test_decision_engine_exception_blocks_trade(self):
        result, tracker = self._predict("SELL", decision_mode="exception")
        self.assertEqual(result["raw_action"], "SELL")
        self.assert_blocked(result, tracker, "decision_engine")
        self.assertEqual(result["protection_errors"][-1]["error"], "decision exploded")

    def test_missing_or_invalid_risk_protection_blocks_trade(self):
        for mode in ("risk_failure", "risk_invalid"):
            with self.subTest(mode=mode):
                result, tracker = self._predict("BUY", context_mode=mode)
                self.assert_blocked(result, tracker, "risk_engine")
                self.assertEqual(
                    result["safeguard_failures"][0]["code"],
                    "risk_context_invalid",
                )

    def test_optional_candlestick_failure_is_diagnostic_but_does_not_block(self):
        result, tracker = self._predict("BUY", optional_failure=True)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["safeguard_status"], "degraded")
        self.assertEqual(result["blocked_by"], [])
        self.assertEqual(
            result["protection_errors"][0]["component"], "candlestick_patterns"
        )
        tracker.record_prediction.assert_called_once()

    def test_normal_decision_engine_veto_is_distinct_from_exception(self):
        result, tracker = self._predict("BUY", decision_mode="veto")
        self.assert_blocked(result, tracker, "decision_engine")
        self.assertEqual(
            result["safeguard_failures"][0]["code"], "decision_engine_veto"
        )
        self.assertNotIn("error_type", result["safeguard_failures"][0])

    def test_original_hold_cannot_become_executable(self):
        result, tracker = self._predict("HOLD")
        self.assertEqual(result["raw_action"], "HOLD")
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["action"], result["signal"])
        tracker.record_prediction.assert_not_called()

    def test_quality_gate_exception_blocks_training_before_dataset_build(self):
        frame = _FakeDataFrame()

        def run_quality_gate(*_args, **_kwargs):
            raise RuntimeError("quality exploded")

        self.roadmap_module.run_quality_gate = run_quality_gate
        pipeline = object.__new__(self.pipeline_module.ForexIntegratedPipeline)

        with patch.object(self.pipeline_module, "_load", return_value=frame), patch.object(
            self.pipeline_module, "build_features", side_effect=lambda df: df
        ), patch.object(
            self.pipeline_module,
            "DatasetBuilder",
            side_effect=AssertionError("DatasetBuilder must not run"),
        ):
            result = pipeline.train("unused.csv", pair="EURUSD")

        self.assertIn("error", result)
        self.assertEqual(result["safeguard_status"], "blocked")
        self.assertEqual(result["blocked_by"], ["quality_gate"])
        self.assertEqual(
            result["safeguard_failures"][0]["error"], "quality exploded"
        )


if __name__ == "__main__":
    unittest.main()
