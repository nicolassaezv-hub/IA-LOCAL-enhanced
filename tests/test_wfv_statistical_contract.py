import numpy as np
import pandas as pd
import pytest

from forex.prediction.retrain_manager import RetrainManager
from forex.prediction.xgb_trainer import (
    MIN_WFV_FOLDS,
    MIN_WFV_SIGNALS_PER_FOLD,
    WalkForwardValidator,
    wfv_quality_passed,
)


def _validation_case(tp, fp, *, validation_size=300):
    signals = tp + fp
    assert signals <= validation_size
    predictions = np.zeros(validation_size, dtype=int)
    predictions[:signals] = 1
    target = np.zeros(validation_size, dtype=int)
    target[:tp] = 1
    return pd.Series(target), predictions


def _evaluate_cases(*cases):
    folds = []
    predictions = []
    for target, predicted in cases:
        train_target = pd.Series(([0] * 20) + ([1] * 20))
        folds.append((
            pd.DataFrame({"feature": range(40)}),
            train_target,
            pd.DataFrame({"feature": range(len(target))}),
            target,
        ))
        predictions.append(predicted)

    prediction_iterator = iter(predictions)

    class FixedModel:
        def __init__(self, values):
            self.values = values

        def predict(self, _features):
            return self.values

    class FixedTrainer:
        def __init__(self, pair=None):
            self.pair = pair
            self.model = None

        def train(self, *_args, **_kwargs):
            self.model = FixedModel(next(prediction_iterator))

    validator = WalkForwardValidator(purge=20, n_folds=5)
    validator.split = lambda _X, _y: folds
    return validator.evaluate(
        FixedTrainer,
        pd.DataFrame({"feature": [0]}),
        pd.Series([0]),
        pair="EURUSD",
    )


def _passing_wfv():
    return _evaluate_cases(
        _validation_case(21, 9),
        _validation_case(20, 10),
    )


def _production_metadata(wfv, *, calibration=True, validation=True):
    return {
        "quality_gate": {"passed": True, "approved": True, "score": 90.0},
        "wfv": wfv,
        "precision": 0.70,
        "eligibility": {
            "quality_gate_passed": True,
            "wfv_passed": wfv_quality_passed(wfv),
            "calibration_passed": calibration,
            "validation_passed": validation,
            "validation_precision": 0.70,
            "model_valid": bool(calibration and validation),
        },
    }


def test_trivial_perfect_fold_cannot_inflate_wfv_pass():
    result = _evaluate_cases(
        _validation_case(81, 64),
        _validation_case(1, 0),
    )

    assert result["folds"][0]["tp"] == 81
    assert result["folds"][0]["fp"] == 64
    assert result["folds"][0]["signals"] == 145
    assert result["folds"][1]["tp"] == 1
    assert result["folds"][1]["signals"] == 1
    assert result["total_tp"] == 82
    assert result["total_fp"] == 64
    assert result["total_signals"] == 146
    assert result["pooled_precision"] == pytest.approx(82 / 146)
    assert result["evidence_sufficient"] is False
    assert result["wfv_passed"] is False
    assert wfv_quality_passed(result) is False


def test_zero_signal_fold_fails_wfv_evidence():
    result = _evaluate_cases(
        _validation_case(0, 0),
        _validation_case(30, 10),
    )

    assert result["folds"][0]["signals"] == 0
    assert result["folds"][0]["precision"] == 0.0
    assert result["evidence_sufficient"] is False
    assert result["wfv_passed"] is False
    assert wfv_quality_passed(result) is False


def test_single_high_evidence_fold_fails_minimum_fold_count():
    result = _evaluate_cases(_validation_case(40, 0))

    assert result["folds"][0]["signals"] >= MIN_WFV_SIGNALS_PER_FOLD
    assert len(result["folds"]) < MIN_WFV_FOLDS
    assert result["evidence_sufficient"] is False
    assert result["wfv_passed"] is False
    assert wfv_quality_passed(result) is False


def test_multiple_sufficient_folds_pass_existing_and_pooled_gates():
    result = _passing_wfv()

    assert all(
        fold["signals"] >= MIN_WFV_SIGNALS_PER_FOLD
        for fold in result["folds"]
    )
    assert result["pooled_precision"] == pytest.approx(41 / 60)
    assert result["evidence_sufficient"] is True
    assert result["wfv_passed"] is True
    assert wfv_quality_passed(result) is True


def test_pooled_precision_can_reject_when_unweighted_gate_passes():
    result = _evaluate_cases(
        _validation_case(30, 0),
        _validation_case(30, 70),
    )

    assert result["avg_precision"] == 0.65
    assert result["evidence_sufficient"] is True
    assert result["pooled_precision"] == pytest.approx(60 / 130)
    assert result["wfv_passed"] is False
    assert wfv_quality_passed(result) is False


def test_legacy_wfv_metadata_without_directional_counts_fails_closed():
    legacy = {
        "folds": [{"fold": 1, "precision": 1.0, "accuracy": 1.0}],
        "avg_precision": 1.0,
        "median_precision": 1.0,
        "wfv_passed": True,
    }

    assert wfv_quality_passed(legacy) is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fold_signals", 31),
        ("fold_precision", 0.71),
        ("fold_validation_size", 29),
        ("total_tp", 43),
        ("total_signals", True),
    ],
)
def test_incoherent_wfv_counts_fail_closed(field, value):
    result = _passing_wfv()
    if field == "fold_signals":
        result["folds"][0]["signals"] = value
    elif field == "fold_precision":
        result["folds"][0]["precision"] = value
    elif field == "fold_validation_size":
        result["folds"][0]["validation_size"] = value
    else:
        result[field] = value

    assert wfv_quality_passed(result) is False


def test_1789_rows_keep_existing_two_walk_forward_splits():
    X = pd.DataFrame({"feature": range(1789)})
    y = pd.Series(np.tile([0, 1], 895)[:1789])

    folds = WalkForwardValidator(purge=20, n_folds=5).split(X, y)

    assert len(folds) == 2
    first_train, _, first_validation, _ = folds[0]
    second_train, _, second_validation, _ = folds[1]
    assert list(first_train.index[[0, -1]]) == [0, 979]
    assert list(first_validation.index[[0, -1]]) == [1020, 1319]
    assert list(second_train.index[[0, -1]]) == [300, 1279]
    assert list(second_validation.index[[0, -1]]) == [1320, 1619]
    assert len(first_train) == len(second_train) == 980
    assert len(first_validation) == len(second_validation) == 300


@pytest.mark.parametrize(
    ("calibration", "validation", "expected_gate"),
    [
        (False, True, "CALIBRATION_GATE"),
        (True, False, "VALIDATION_GATE"),
    ],
)
def test_passing_wfv_does_not_bypass_calibration_or_validation(
    calibration, validation, expected_gate
):
    metadata = _production_metadata(
        _passing_wfv(),
        calibration=calibration,
        validation=validation,
    )

    assert RetrainManager._production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="manual_quality_retrain",
        dataset_provenance={},
    ) == expected_gate


def test_retrain_manager_rejects_statistically_insufficient_wfv():
    insufficient = _evaluate_cases(
        _validation_case(81, 64),
        _validation_case(1, 0),
    )
    metadata = _production_metadata(insufficient)
    metadata["eligibility"]["wfv_passed"] = True

    assert RetrainManager._production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="manual_quality_retrain",
        dataset_provenance={},
    ) == "WFV_GATE"
