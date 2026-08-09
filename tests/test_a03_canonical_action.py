"""Regression tests for audit finding A-03.

The production environment has optional ML dependencies.  These tests load the
pipeline with small module doubles so no model, dataset, database, or external
service is used.
"""

from __future__ import annotations

import ast
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


class CanonicalActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        forex_package = _module("forex")
        forex_package.__path__ = []
        prediction_package = _module("forex.prediction")
        prediction_package.__path__ = []

        cls.context = types.SimpleNamespace(
            circuit_breaker_active=False,
            regime=None,
            mtf=None,
            news_active=False,
            news_sentiment="",
            volatility_level="normal",
            atr_percentile=50.0,
            model_win_rate=None,
            model_recent_predictions=0,
            risk=None,
            to_dict=lambda: {},
        )
        cls.roadmap_module = _module("forex.prediction.roadmap_v_integration")
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
            "forex.prediction.candlestick_patterns": _module(
                "forex.prediction.candlestick_patterns",
                detect_patterns=lambda _df: {},
            ),
            "forex.prediction.prediction_context": _module(
                "forex.prediction.prediction_context",
                build_context=lambda *args, **kwargs: cls.context,
            ),
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

    def _predict(self, raw_action: str, final_action: str):
        frame = _FakeDataFrame()

        class FakeDatasetBuilder:
            def __init__(self, _df):
                pass

            def predict_features(self, n_rows, train_columns):
                return frame

        tracker = Mock()
        self.outcome_module.OutcomeTracker = lambda: tracker
        self.roadmap_module.run_decision_engine = lambda **_kwargs: types.SimpleNamespace(
            decision=final_action,
            explanation="test decision",
            risk_level="medium",
            factors_for=[],
            factors_against=[],
            reliability_score=80.0,
            quality_tier="valid",
        )

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

    def test_buy_without_veto_remains_buy(self):
        result, _tracker = self._predict("BUY", "BUY")

        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["raw_action"], "BUY")

    def test_sell_without_veto_remains_sell(self):
        result, _tracker = self._predict("SELL", "SELL")

        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["raw_action"], "SELL")

    def test_vetoed_buy_cannot_remain_buy(self):
        result, tracker = self._predict("BUY", "HOLD")

        self.assertEqual(result["raw_action"], "BUY")
        self.assertEqual(result["action"], "HOLD")
        tracker.record_prediction.assert_not_called()

    def test_vetoed_sell_cannot_remain_sell(self):
        result, tracker = self._predict("SELL", "NO_OPERAR")

        self.assertEqual(result["raw_action"], "SELL")
        self.assertEqual(result["action"], "NO_OPERAR")
        tracker.record_prediction.assert_not_called()

    def test_action_and_signal_are_consistent_after_pipeline(self):
        for raw_action, final_action in (
            ("BUY", "BUY"),
            ("SELL", "SELL"),
            ("BUY", "HOLD"),
            ("SELL", "NO_OPERAR"),
        ):
            with self.subTest(raw_action=raw_action, final_action=final_action):
                result, _tracker = self._predict(raw_action, final_action)
                self.assertEqual(result["action"], result["signal"])
                self.assertEqual(result["action"], final_action)

    def test_outcome_tracker_receives_only_effective_trade_action(self):
        result, tracker = self._predict("SELL", "SELL")

        self.assertEqual(result["action"], "SELL")
        tracker.record_prediction.assert_called_once()
        self.assertEqual(tracker.record_prediction.call_args.kwargs["signal"], "SELL")

    def test_cli_formatter_uses_final_action(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        formatter = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_format_signal"
        )
        formatter_module = ast.fix_missing_locations(
            ast.Module(body=[formatter], type_ignores=[])
        )
        colors = types.SimpleNamespace(GREEN="", RED="", YELLOW="", WHITE="")
        style = types.SimpleNamespace(RESET_ALL="")
        namespace = {"Fore": colors, "Style": style}
        exec(compile(formatter_module, str(ROOT / "main.py"), "exec"), namespace)

        rendered = namespace["_format_signal"](
            {"action": "HOLD", "signal": "HOLD", "raw_action": "BUY"}
        )

        self.assertIn("HOLD", rendered)
        self.assertNotIn("BUY", rendered)


if __name__ == "__main__":
    unittest.main()
