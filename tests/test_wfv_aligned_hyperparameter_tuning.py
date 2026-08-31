import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from forex.prediction import hyperparameter_cache
from forex.prediction import hyperparameter_tuner as tuner_module
from forex.prediction import integrated_pipeline as pipeline_module
from forex.prediction import roadmap_v_integration
from forex.prediction import xgb_trainer


def _frame(n=1756):
    return pd.DataFrame({"feature": np.arange(n, dtype=float)})


def _labels(n=1756):
    return pd.Series(np.arange(n) % 2, dtype=int)


def _valid_wfv():
    folds = [
        {
            "fold": 1,
            "tp": 21,
            "fp": 9,
            "signals": 30,
            "validation_size": 300,
            "precision": 0.7,
            "accuracy": 0.6,
        },
        {
            "fold": 2,
            "tp": 21,
            "fp": 9,
            "signals": 30,
            "validation_size": 300,
            "precision": 0.7,
            "accuracy": 0.6,
        },
    ]
    return {
        "folds": folds,
        "avg_precision": 0.7,
        "median_precision": 0.7,
        "avg_accuracy": 0.6,
        "total_tp": 42,
        "total_fp": 18,
        "total_signals": 60,
        "pooled_precision": 0.7,
        "evidence_sufficient": True,
        "wfv_passed": True,
        "model_deployed": False,
    }


def _strong_inner_summary():
    folds = [
        {
            "fold": 1,
            "validation_size": 200,
            "min_signals": 20,
            "tp": 14,
            "fp": 6,
            "signals": 20,
            "precision": 0.7,
            "accuracy": 0.6,
        },
        {
            "fold": 2,
            "validation_size": 200,
            "min_signals": 20,
            "tp": 14,
            "fp": 6,
            "signals": 20,
            "precision": 0.7,
            "accuracy": 0.6,
        },
    ]
    return tuner_module.summarize_inner_evidence(folds)


class _FakeTrial:
    def __init__(self, number):
        self.number = number
        self.user_attrs = {}
        self.value = None

    def suggest_int(self, _name, low, _high):
        return low

    def suggest_float(self, _name, low, _high, **_kwargs):
        return low

    def set_user_attr(self, name, value):
        self.user_attrs[name] = value


class _FakeStudy:
    def __init__(self):
        self.trials = []

    def optimize(self, objective, n_trials, timeout=None, show_progress_bar=False):
        assert timeout is None
        assert show_progress_bar is False
        for number in range(n_trials):
            trial = _FakeTrial(number)
            trial.value = objective(trial)
            self.trials.append(trial)


class _FakeOptuna:
    sampler_seed = None

    class samplers:
        class TPESampler:
            def __init__(self, seed):
                _FakeOptuna.sampler_seed = seed

    @staticmethod
    def create_study(*, direction, sampler):
        assert direction == "maximize"
        assert sampler is not None
        return _FakeStudy()


def test_production_split_positions_preserve_existing_geometry_and_slices():
    X = _frame()
    y = _labels()
    validator = xgb_trainer.WalkForwardValidator(purge=20, n_folds=5)

    positions = validator.split_positions(len(X))
    folds = validator.split(X, y)

    assert positions == [
        {
            "train_start": 0,
            "train_end": 980,
            "validation_start": 1020,
            "validation_end": 1320,
        },
        {
            "train_start": 300,
            "train_end": 1280,
            "validation_start": 1320,
            "validation_end": 1620,
        },
    ]
    assert len(folds) == 2
    for position, (X_train, y_train, X_validation, y_validation) in zip(
        positions, folds
    ):
        assert X_train.equals(X.iloc[position["train_start"] : position["train_end"]])
        assert y_train.equals(y.iloc[position["train_start"] : position["train_end"]])
        assert X_validation.equals(
            X.iloc[position["validation_start"] : position["validation_end"]]
        )
        assert y_validation.equals(
            y.iloc[position["validation_start"] : position["validation_end"]]
        )


def test_nested_geometry_reserves_outer_validation_and_uses_only_first_outer_train(tmp_path):
    tuner = tuner_module.ForexHyperparameterTuner("EURUSD", params_dir=tmp_path)
    geometry = tuner._nested_geometry(1756)

    assert geometry["tuning_pool"] == {
        "start": 0,
        "end": 980,
        "row_count": 980,
    }
    tuning_positions = set(range(0, 980))
    reserved = set()
    for fold in geometry["outer_validation_reserved"]:
        reserved.update(range(fold["start"], fold["end"]))
    assert reserved
    assert tuning_positions.isdisjoint(reserved)
    assert min(reserved) == 1020


def test_inner_folds_are_temporal_non_overlapping_and_respect_purge(tmp_path):
    tuner = tuner_module.ForexHyperparameterTuner("EURUSD", params_dir=tmp_path)
    geometry = tuner._nested_geometry(1756)
    positions = geometry["inner_positions"]

    assert len(positions) == 2
    assert positions == [
        {
            "train_start": 0,
            "train_end": 480,
            "validation_start": 520,
            "validation_end": 720,
        },
        {
            "train_start": 200,
            "train_end": 680,
            "validation_start": 720,
            "validation_end": 920,
        },
    ]
    for fold in positions:
        assert fold["train_start"] < fold["train_end"]
        assert fold["train_end"] < fold["validation_start"]
        assert fold["validation_start"] < fold["validation_end"]
        assert fold["validation_start"] - fold["train_end"] == 40
        assert set(range(fold["train_start"], fold["train_end"])).isdisjoint(
            range(fold["validation_start"], fold["validation_end"])
        )


@pytest.mark.parametrize(
    "folds",
    [
        [
            {
                "validation_size": 200,
                "tp": 0,
                "fp": 0,
                "signals": 0,
                "precision": 0.0,
                "accuracy": 0.5,
            },
            {
                "validation_size": 200,
                "tp": 0,
                "fp": 0,
                "signals": 0,
                "precision": 0.0,
                "accuracy": 0.5,
            },
        ],
        [
            {
                "validation_size": 200,
                "tp": 1,
                "fp": 0,
                "signals": 1,
                "precision": 1.0,
                "accuracy": 0.5,
            },
            {
                "validation_size": 200,
                "tp": 1,
                "fp": 0,
                "signals": 1,
                "precision": 1.0,
                "accuracy": 0.5,
            },
        ],
    ],
)
def test_inner_evidence_rejects_zero_or_tiny_signal_trials(folds):
    summary = tuner_module.summarize_inner_evidence(folds)

    assert summary["inner_evidence_sufficient"] is False
    assert summary["inner_wfv_passed"] is False
    assert summary["objective_score"] == tuner_module.INSUFFICIENT_EVIDENCE_SCORE


def test_sufficient_signal_candidate_strictly_outranks_insufficient_candidate():
    sufficient = _strong_inner_summary()
    insufficient = tuner_module.summarize_inner_evidence(
        [
            {
                "validation_size": 200,
                "tp": 1,
                "fp": 0,
                "signals": 1,
                "precision": 1.0,
                "accuracy": 0.5,
            }
        ]
        * 2
    )

    assert sufficient["inner_evidence_sufficient"] is True
    assert sufficient["inner_wfv_passed"] is True
    assert sufficient["objective_score"] > insufficient["objective_score"]


def test_objective_is_minimum_of_average_and_pooled_precision():
    summary = tuner_module.summarize_inner_evidence(
        [
            {
                "validation_size": 200,
                "tp": 18,
                "fp": 2,
                "signals": 20,
                "precision": 0.9,
                "accuracy": 0.6,
            },
            {
                "validation_size": 200,
                "tp": 12,
                "fp": 28,
                "signals": 40,
                "precision": 0.3,
                "accuracy": 0.5,
            },
        ]
    )

    assert summary["inner_avg_precision"] == pytest.approx(0.6)
    assert summary["inner_pooled_precision"] == pytest.approx(0.5)
    assert summary["objective_score"] == pytest.approx(0.5)


def test_explicit_override_wins_and_empty_override_forces_defaults(monkeypatch):
    disk_params = {"xgb": {"max_depth": 99}}
    monkeypatch.setattr(xgb_trainer, "_load_tuned_params", lambda _pair: disk_params)
    explicit = {"xgb": {"max_depth": 4}}

    overridden = xgb_trainer.ForexEnsembleTrainer(
        pair="EURUSD", tuned_params_override=explicit
    )
    defaults = xgb_trainer.ForexEnsembleTrainer(
        pair="EURUSD", tuned_params_override={}
    )
    legacy = xgb_trainer.ForexEnsembleTrainer(pair="EURUSD")

    assert overridden._tuned is explicit
    assert defaults._tuned == {}
    assert legacy._tuned is disk_params


def test_every_wfv_fold_receives_same_override_object():
    seen = []
    override = {"xgb": {"max_depth": 4}, "lgb": {"max_depth": 4}}

    class Model:
        @staticmethod
        def predict(X):
            return np.ones(len(X), dtype=int)

    class Trainer:
        def __init__(self, pair=None, tuned_params_override=None):
            seen.append((pair, tuned_params_override))
            self.model = Model()

        def train(self, *_args, **_kwargs):
            return 0.5, 0.5

    validator = xgb_trainer.WalkForwardValidator(purge=20, n_folds=5)
    result = validator.evaluate(
        Trainer, _frame(), _labels(), pair="EURUSD", tuned_params_override=override
    )

    assert len(result["folds"]) == 2
    assert len(seen) == 2
    assert all(pair == "EURUSD" and params is override for pair, params in seen)


def test_final_trainer_and_wfv_receive_same_override(monkeypatch):
    override = {"xgb": {"max_depth": 4}}
    final_seen = []
    evaluate_seen = []

    class Model:
        sufficient = True

    class Trainer:
        def __init__(self, pair=None, tuned_params_override=None):
            final_seen.append((pair, tuned_params_override))
            self.model = Model()
            self.best_model = None

        def train(self, *_args, **_kwargs):
            return 0.6, 0.7

    def fake_evaluate(self, trainer_cls, X, y, pair=None, tuned_params_override=None):
        evaluate_seen.append((trainer_cls, pair, tuned_params_override))
        return _valid_wfv()

    monkeypatch.setattr(xgb_trainer, "ForexEnsembleTrainer", Trainer)
    monkeypatch.setattr(xgb_trainer.WalkForwardValidator, "evaluate", fake_evaluate)

    xgb_trainer.train_with_wfv(
        _frame(400),
        _labels(400),
        pair="EURUSD",
        save=False,
        tuned_params_override=override,
    )

    assert evaluate_seen == [(Trainer, "EURUSD", override)]
    assert final_seen == [("EURUSD", override)]


def test_params_sha_is_deterministic_independent_of_key_order():
    first = {"xgb": {"max_depth": 4, "learning_rate": 0.03}, "lgb": {"num_leaves": 31}}
    second = {"lgb": {"num_leaves": 31}, "xgb": {"learning_rate": 0.03, "max_depth": 4}}
    expected = hashlib.sha256(
        json.dumps(first, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert tuner_module.canonical_params_sha256(first) == expected
    assert tuner_module.canonical_params_sha256(second) == expected


def test_wfv_aligned_tuner_defaults_do_not_persist_params_or_touch_cache(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tuner_module, "optuna", _FakeOptuna)
    monkeypatch.setattr(tuner_module, "_HAS_OPTUNA", True)
    monkeypatch.setattr(
        hyperparameter_cache.HyperparameterCache,
        "save",
        lambda *_args, **_kwargs: pytest.fail("WFV-aligned tuner touched cache"),
    )
    monkeypatch.setattr(
        hyperparameter_cache.HyperparameterCache,
        "get",
        lambda *_args, **_kwargs: pytest.fail("WFV-aligned tuner read cache"),
    )
    tuner = tuner_module.ForexHyperparameterTuner("EURUSD", params_dir=tmp_path)
    params = {"xgb": {"max_depth": 4}, "lgb": {"max_depth": 4}}
    monkeypatch.setattr(tuner, "_suggest_wfv_params", lambda _trial: params)
    monkeypatch.setattr(
        tuner,
        "_evaluate_inner_params",
        lambda *_args, **_kwargs: _strong_inner_summary(),
    )

    result = tuner.tune_wfv_aligned(
        _frame(),
        _labels(),
        snapshot_sha256="snapshot-identity",
        n_trials=2,
    )

    assert _FakeOptuna.sampler_seed == 42
    assert result["params"] == params
    assert result["persisted"] is False
    assert result["use_cache"] is False
    assert not (tmp_path / "best_params_EURUSD.json").exists()
    assert result["hyperparameter_provenance"]["snapshot_sha256"] == "snapshot-identity"
    assert result["hyperparameter_provenance"]["params_sha256"] == result["params_sha256"]


def test_no_sufficient_trial_returns_explicit_fail_closed_result(tmp_path, monkeypatch):
    monkeypatch.setattr(tuner_module, "optuna", _FakeOptuna)
    monkeypatch.setattr(tuner_module, "_HAS_OPTUNA", True)
    tuner = tuner_module.ForexHyperparameterTuner("EURUSD", params_dir=tmp_path)
    monkeypatch.setattr(tuner, "_suggest_wfv_params", lambda _trial: {"xgb": {"max_depth": 3}})
    insufficient = tuner_module.summarize_inner_evidence(
        [
            {
                "validation_size": 200,
                "tp": 1,
                "fp": 0,
                "signals": 1,
                "precision": 1.0,
                "accuracy": 0.5,
            }
        ]
        * 2
    )
    monkeypatch.setattr(tuner, "_evaluate_inner_params", lambda *_args, **_kwargs: insufficient)

    result = tuner.tune_wfv_aligned(
        _frame(), _labels(), snapshot_sha256="snapshot-identity", n_trials=1
    )

    assert result["status"] == "NO_INNER_EVIDENCE_SUFFICIENT_CANDIDATE"
    assert result["params"] == {}
    assert result["inner_evidence_sufficient"] is False
    assert result["inner_wfv_passed"] is False


def test_candidate_preserves_nested_tuning_provenance_and_override(monkeypatch):
    params = {"xgb": {"max_depth": 4}}
    params_sha = tuner_module.canonical_params_sha256(params)
    hyperparameter_provenance = {
        "mode": "nested_wfv_tuning",
        "pair": "EURUSD",
        "snapshot_sha256": "snapshot-identity",
        "params_sha256": params_sha,
        "selection_seed": 42,
        "trial_count": 2,
        "tuning_pool": {"start": 0, "end": 980, "row_count": 980},
        "inner_geometry": {"window": 500, "step": 200, "purge": 20, "n_folds": 2},
        "inner_metrics": {"inner_wfv_passed": True},
        "persisted": False,
    }
    captured = {}

    class Report:
        approved = True
        global_score = 90.0
        critical_count = 0
        warning_count = 0

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return _frame(300), _labels(300)

    class Model:
        sufficient = True

    class Trainer:
        model = Model()
        calibration_sufficient = True
        validation_sufficient = True
        model_valid = True

    def fake_train(X, y, pair=None, save=True, force=False, tuned_params_override=None):
        captured["override"] = tuned_params_override
        return Trainer(), _valid_wfv(), 0.6, 0.7

    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_args, **_kwargs: (True, Report()),
    )
    monkeypatch.setattr(pipeline_module, "DatasetBuilder", Builder)
    monkeypatch.setattr(pipeline_module, "train_with_wfv", fake_train)
    pipeline = pipeline_module.ForexIntegratedPipeline()

    candidate = pipeline._train_quality_candidate(
        pd.DataFrame({"close": [1.0]}),
        symbol="EURUSD",
        horizon=12,
        rr_ratio=1.0,
        dataset_provenance={"snapshot_sha256": "snapshot-identity"},
        promotion_type="initial_training",
        tuned_params_override=params,
        hyperparameter_provenance=hyperparameter_provenance,
    )

    assert captured["override"] is params
    assert candidate["metadata"]["hyperparameter_provenance"] == hyperparameter_provenance


def test_legacy_tune_api_remains_available(tmp_path, monkeypatch):
    tuner = tuner_module.ForexHyperparameterTuner("EURUSD", params_dir=tmp_path)
    monkeypatch.setattr(tuner_module, "_HAS_OPTUNA", False)

    assert callable(tuner.tune)
    assert tuner.tune(_frame(10), _labels(10), _frame(5), _labels(5)) == {}
