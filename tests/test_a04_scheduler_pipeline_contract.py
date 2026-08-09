import ast
import inspect
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from infra.db.database import SQLiteDatabase
from scheduler import autonomous_scheduler


class FakeDatabase:
    def __init__(self, datasets=None):
        self.datasets = datasets or {}
        self.saved_predictions = []

    def get_dataset_registry(self, symbol, timeframe):
        path = self.datasets.get((symbol, timeframe))
        if path is None:
            return []
        return [{"status": "ready", "blob_path": str(path)}]

    def save_prediction(self, prediction):
        saved = {"id": len(self.saved_predictions) + 1, **prediction}
        self.saved_predictions.append(saved)
        return saved


class FakeCycleDatabase:
    def __init__(self):
        self.run = None
        self.run_updates = []

    def create_scheduler_run(self, run):
        self.run = {"id": 1, **run}
        return self.run

    def update_scheduler_run(self, run_id, updates):
        self.run_updates.append((run_id, updates))
        return {**self.run, **updates}

    def get_supported_symbols(self):
        return [{"symbol_code": "EURUSD"}]


@contextmanager
def pipeline_double(result):
    calls = []
    instances = []

    class ForexIntegratedPipeline:
        def __init__(self):
            instances.append(self)

        def predict(
            self,
            filepath: str,
            pair: str = None,
            path_h4: str = None,
            path_d1: str = None,
        ) -> dict:
            calls.append(
                {
                    "filepath": filepath,
                    "pair": pair,
                    "path_h4": path_h4,
                    "path_d1": path_d1,
                }
            )
            return dict(result)

    prediction_package = types.ModuleType("forex.prediction")
    prediction_package.__path__ = []
    pipeline_module = types.ModuleType("forex.prediction.integrated_pipeline")
    pipeline_module.ForexIntegratedPipeline = ForexIntegratedPipeline

    with patch.dict(
        sys.modules,
        {
            "forex.prediction": prediction_package,
            "forex.prediction.integrated_pipeline": pipeline_module,
        },
    ):
        yield ForexIntegratedPipeline, calls, instances


class SchedulerPipelineContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        root_patch = patch.object(autonomous_scheduler, "PROJECT_ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def make_dataset(self, symbol: str, timeframe: str) -> Path:
        path = self.root / f"{symbol}_{timeframe}.csv"
        path.write_text(
            "isolated test fixture; pipeline double does not read it\n",
            encoding="utf-8",
        )
        return path

    def test_real_predict_declaration_and_double_use_the_same_contract(self):
        pipeline_path = (
            Path(__file__).resolve().parents[1]
            / "forex"
            / "prediction"
            / "integrated_pipeline.py"
        )
        tree = ast.parse(pipeline_path.read_text(encoding="utf-8"))
        pipeline_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ForexIntegratedPipeline"
        )
        predict = next(
            node
            for node in pipeline_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "predict"
        )
        real_parameters = [argument.arg for argument in predict.args.args]

        with pipeline_double({"action": "HOLD"}) as (
            double,
            _calls,
            _instances,
        ):
            double_parameters = list(inspect.signature(double.predict).parameters)

        expected = ["self", "filepath", "pair", "path_h4", "path_d1"]
        self.assertEqual(real_parameters, expected)
        self.assertEqual(double_parameters, expected)

    def test_h1_resolves_main_and_available_mtf_paths(self):
        h1 = self.make_dataset("EURUSD", "H1")
        h4 = self.make_dataset("EURUSD", "H4")
        d1 = self.make_dataset("EURUSD", "D1")
        db = FakeDatabase(
            {
                ("EURUSD", "H1"): h1,
                ("EURUSD", "H4"): h4,
                ("EURUSD", "D1"): d1,
            }
        )

        with pipeline_double({"action": "BUY", "confidence": 0.72}) as (
            _double,
            calls,
            _instances,
        ):
            outcome = autonomous_scheduler.run_prediction(db, "EURUSD", "H1")

        self.assertEqual(outcome["action"], "predicted")
        self.assertEqual(
            calls,
            [
                {
                    "filepath": str(h1),
                    "pair": "EURUSD",
                    "path_h4": str(h4),
                    "path_d1": str(d1),
                }
            ],
        )

    def test_dict_buy_and_sell_actions_are_persisted(self):
        h1 = self.make_dataset("GBPUSD", "H1")

        for final_action in ("BUY", "SELL"):
            with self.subTest(final_action=final_action):
                db = FakeDatabase({("GBPUSD", "H1"): h1})
                result = {
                    "action": final_action,
                    "confidence": 0.77,
                    "reliability_score": 83.0,
                    "entry_price": 1.27,
                    "stop_loss": 1.26,
                    "take_profit": 1.29,
                }

                with pipeline_double(result):
                    outcome = autonomous_scheduler.run_prediction(
                        db,
                        "GBPUSD",
                        "H1",
                    )

                persisted = db.saved_predictions[0]
                self.assertEqual(outcome["action"], "predicted")
                self.assertEqual(persisted["symbol"], "GBPUSD")
                self.assertEqual(persisted["pair"], "GBPUSD")
                self.assertEqual(persisted["timeframe"], "H1")
                self.assertEqual(persisted["action"], final_action)
                self.assertEqual(persisted["direction"], final_action)
                self.assertAlmostEqual(persisted["confidence"], 0.77)
                self.assertAlmostEqual(persisted["reliability_score"], 83.0)

    def test_dict_hold_uses_canonical_action_and_never_raw_buy(self):
        h1 = self.make_dataset("AUDUSD", "H1")
        db = FakeDatabase({("AUDUSD", "H1"): h1})

        with pipeline_double(
            {"action": "HOLD", "raw_action": "BUY", "confidence": 0.81}
        ):
            autonomous_scheduler.run_prediction(db, "AUDUSD", "H1")

        persisted = db.saved_predictions[0]
        self.assertEqual(persisted["action"], "HOLD")
        self.assertEqual(persisted["direction"], "HOLD")
        self.assertNotIn("BUY", (persisted["action"], persisted["direction"]))

    def test_sqlite_persistence_maps_final_action_to_current_direction_schema(self):
        h1 = self.make_dataset("EURUSD", "H1")
        db = SQLiteDatabase(str(self.root / "scheduler-test.db"))
        self.addCleanup(db._conn().close)
        db.upsert_dataset_registry(
            {
                "symbol": "EURUSD",
                "timeframe": "H1",
                "blob_path": str(h1),
                "status": "ready",
            }
        )

        with pipeline_double(
            {
                "action": "HOLD",
                "raw_action": "BUY",
                "confidence": 0.74,
                "reliability_score": 79.0,
            }
        ):
            outcome = autonomous_scheduler.run_prediction(db, "EURUSD", "H1")

        persisted = outcome["prediction"]
        self.assertEqual(persisted["symbol"], "EURUSD")
        self.assertEqual(persisted["timeframe"], "H1")
        self.assertEqual(persisted["direction"], "HOLD")
        self.assertAlmostEqual(persisted["confidence"], 0.74)
        self.assertNotEqual(persisted["direction"], "BUY")

    def test_missing_main_filepath_is_explicit_and_pipeline_is_not_called(self):
        db = FakeDatabase()

        with pipeline_double({"action": "BUY"}) as (
            _double,
            calls,
            instances,
        ):
            outcome = autonomous_scheduler.run_prediction(db, "NZDUSD", "H1")

        self.assertEqual(outcome["action"], "error")
        self.assertIn("Dataset CSV not found for NZDUSD H1", outcome["error"])
        self.assertEqual(calls, [])
        self.assertEqual(instances, [])
        self.assertEqual(db.saved_predictions, [])

    def test_missing_optional_h4_and_d1_are_passed_as_none(self):
        h1 = self.make_dataset("USDJPY", "H1")
        db = FakeDatabase({("USDJPY", "H1"): h1})

        with pipeline_double({"action": "HOLD", "confidence": 0.65}) as (
            _double,
            calls,
            _instances,
        ):
            outcome = autonomous_scheduler.run_prediction(db, "USDJPY", "H1")

        self.assertEqual(outcome["action"], "predicted")
        self.assertEqual(calls[0]["filepath"], str(h1))
        self.assertIsNone(calls[0]["path_h4"])
        self.assertIsNone(calls[0]["path_d1"])

    def test_run_prediction_skips_h4_and_d1_without_pipeline_or_persistence(self):
        for timeframe in ("H4", "D1"):
            with self.subTest(timeframe=timeframe):
                main = self.make_dataset("EURUSD", timeframe)
                db = FakeDatabase({("EURUSD", timeframe): main})

                with pipeline_double({"action": "SELL"}) as (
                    _double,
                    calls,
                    instances,
                ):
                    outcome = autonomous_scheduler.run_prediction(
                        db,
                        "EURUSD",
                        timeframe,
                    )

                self.assertEqual(outcome["action"], "skip")
                self.assertEqual(
                    outcome["reason"],
                    "prediction_timeframe_not_supported",
                )
                self.assertEqual(outcome["timeframe"], timeframe)
                self.assertEqual(outcome["supported_timeframe"], "H1")
                self.assertEqual(calls, [])
                self.assertEqual(instances, [])
                self.assertEqual(db.saved_predictions, [])

    def test_h1_cycle_updates_dataset_and_generates_prediction(self):
        db = FakeCycleDatabase()
        model_check = Mock(return_value=True)
        integrity_module = types.ModuleType("robustness.model_integrity_checker")
        integrity_module.check_model_before_cycle = model_check

        with patch.dict(
            sys.modules,
            {"robustness.model_integrity_checker": integrity_module},
        ), patch.object(
            autonomous_scheduler,
            "detect_new_symbols",
            return_value=[],
        ), patch.object(
            autonomous_scheduler,
            "run_rolling_update",
            return_value={"action": "updated"},
        ) as update, patch.object(
            autonomous_scheduler,
            "run_prediction",
            return_value={"action": "predicted"},
        ) as predict:
            result = autonomous_scheduler.run_cycle(db, "H1")

        update.assert_called_once_with(db, "EURUSD", "H1")
        predict.assert_called_once_with(db, "EURUSD", "H1")
        model_check.assert_called_once_with("EURUSD", "H1")
        self.assertEqual(result["predictions_generated"], 1)

    def test_h4_and_d1_cycles_only_update_their_dataset(self):
        for timeframe in ("H4", "D1"):
            with self.subTest(timeframe=timeframe):
                db = FakeCycleDatabase()
                model_check = Mock()
                integrity_module = types.ModuleType(
                    "robustness.model_integrity_checker"
                )
                integrity_module.check_model_before_cycle = model_check

                with patch.dict(
                    sys.modules,
                    {"robustness.model_integrity_checker": integrity_module},
                ), patch.object(
                    autonomous_scheduler,
                    "detect_new_symbols",
                    return_value=[],
                ), patch.object(
                    autonomous_scheduler,
                    "run_rolling_update",
                    return_value={"action": "updated"},
                ) as update, patch.object(
                    autonomous_scheduler,
                    "run_prediction",
                ) as predict:
                    result = autonomous_scheduler.run_cycle(db, timeframe)

                update.assert_called_once_with(db, "EURUSD", timeframe)
                predict.assert_not_called()
                model_check.assert_not_called()
                self.assertEqual(result["predictions_generated"], 0)
                self.assertEqual(
                    result["results"],
                    [
                        {
                            "symbol": "EURUSD",
                            "update": {"action": "updated"},
                        }
                    ],
                )

    def test_scheduler_does_not_use_attribute_access_for_pipeline_dict(self):
        source = inspect.getsource(autonomous_scheduler.run_prediction)
        self.assertNotIn("getattr(result", source)


if __name__ == "__main__":
    unittest.main()
