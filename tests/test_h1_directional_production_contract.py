"""Frozen production contract for the validated H1 directional RF hypothesis."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from forex.prediction.dataset_builder import feature_names_sha256
from forex.prediction.research_hypotheses import FixedHorizonRandomForestClassifier
from forex.prediction.retrain_manager import RetrainManager
from infra.db.database import SQLiteDatabase

from forex.prediction import h1_directional as h1


pytestmark = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array has been deprecated:DeprecationWarning"
)


VALIDATED_FEATURE_NAMES = [
    "returns", "hour", "day_of_week", "session", "volume", "RSI_14",
    "volatility_24h", "h4_rsi", "h4_return5", "h4_trend", "d1_rsi",
    "d1_return5", "d1_trend", "returns_lag_1", "returns_lag_2",
    "returns_lag_3", "returns_lag_5", "returns_lag_10", "body_strength",
    "upper_shadow", "lower_shadow", "volatility_regime", "ADX_14",
    "plus_DI", "minus_DI", "stoch_k", "stoch_d", "stoch_cross",
    "williams_r", "tick_vol_flow_diverge", "bb_squeeze", "bb_pct_b",
    "pattern_doji", "pattern_hammer", "pattern_shooting_star",
    "pattern_bull_engulf", "pattern_bear_engulf", "ema20_above_50",
    "ema_cross_signal", "ema50_above_200", "rsi_overbought",
    "rsi_oversold", "rsi_slope", "price_vs_ema200", "price_in_range_50",
    "ema20_slope", "session_tokyo", "session_london", "session_newyork",
    "atr_ratio", "atr_expansion", "trend_align_score", "close_vs_h4",
    "rsi_divergence", "candle_body_ratio", "momentum_accel",
    "volume_relative", "h4_rsi_extreme", "open_vs_close",
    "high_vs_close", "low_vs_close", "range_pct", "body_pct",
    "close_vs_ema20", "close_vs_ema50", "close_vs_ema200", "ema20_vs_50",
    "ema50_vs_200", "trend_strength_pct", "close_vs_lag_1",
    "close_vs_lag_2", "close_vs_lag_3", "close_vs_lag_5",
    "close_vs_lag_10", "close_vs_rollmean_5", "close_vs_rollmean_10",
    "close_vs_rollmean_20", "rolling_std_pct_5", "rolling_std_pct_10",
    "rolling_std_pct_20", "momentum_pct_5", "momentum_pct_10",
    "bb_width_pct", "atr_pct", "macd_pct", "macd_signal_pct",
    "macd_hist_pct", "spread_pct", "h4_close_vs_ema20",
    "h4_close_vs_ema50", "h4_close_vs_ema200", "h4_ema20_vs_50",
    "h4_ema50_vs_200", "h4_atr_pct", "h4_macd_pct",
    "d1_close_vs_ema20", "d1_close_vs_ema50", "d1_close_vs_ema200",
    "d1_ema20_vs_50", "d1_ema50_vs_200", "d1_atr_pct", "d1_macd_pct",
]


def _matrix(rows: int = 180, columns=VALIDATED_FEATURE_NAMES):
    rng = np.random.default_rng(20260831)
    X = pd.DataFrame(rng.normal(size=(rows, len(columns))), columns=columns)
    y = pd.Series(np.arange(rows) % 2, dtype=int)
    return X, y


def _independent_evidence(**overrides) -> dict:
    evidence = {
        "protocol": h1.H1_INDEPENDENT_VALIDATION_PROTOCOL,
        "source_sha": "a" * 40,
        "snapshot_sha": "b" * 64,
        "validation_start_position": 0,
        "validation_end_position": 200,
        "validation_start_timestamp": "2026-09-01T00:00:00+00:00",
        "validation_end_timestamp": "2026-09-12T00:00:00+00:00",
        "row_count": 200,
        "auc": 0.60,
        "ap": 0.60,
        "ap_lift": 0.05,
        "comparator_auc": 0.52,
        "comparator_ap_lift": 0.01,
        "auc_delta": 0.08,
        "ap_lift_delta": 0.04,
        "buy_count": 60,
        "sell_count": 60,
        "hold_count": 80,
        "coverage": 0.60,
        "buy_precision": 0.56,
        "sell_precision": 0.57,
        "pooled_action_precision": 0.565,
        "passed": True,
    }
    evidence.update(overrides)
    return evidence


def _resolved_config(ratio: float = 1.0) -> dict:
    return {
        **h1.fixed_h1_production_rf_config(),
        "class_weight": {0: 1.0, 1: ratio},
    }


def _synthetic_oof_diagnostics() -> list[dict]:
    return [
        {
            "fold": fold,
            **position,
            "train_class_counts": {0: 490, 1: 490},
            "validation_rows": 200,
            "auc": 0.60,
            "ap": 0.60,
            "ap_lift": 0.10,
            "accuracy_at_0_5": 0.55,
            "buy_count": 50,
            "sell_count": 50,
            "hold_count": 100,
            "decision_coverage": 0.50,
            "emitted_directional_precision": 0.56,
        }
        for fold, position in enumerate(h1.h1_oof_positions(1620), start=1)
    ]


def _metadata(dataset_provenance=None, **overrides) -> dict:
    dataset_provenance = dataset_provenance or {"snapshot_sha256": "snapshot"}
    evidence = _independent_evidence()
    reference = h1.build_oof_decision_reference(np.linspace(0.0, 1.0, 600))
    metadata = {
        "model_contract": h1.H1_MODEL_CONTRACT,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "promotion_type": "initial_training",
        "target_profile": h1.H1_TARGET_PROFILE,
        "target_definition_version": h1.H1_TARGET_DEFINITION_VERSION,
        "horizon": h1.H1_HORIZON,
        "feature_profile": h1.H1_FEATURE_PROFILE,
        "feature_names_sha256": h1.H1_FEATURE_NAMES_SHA256,
        "model_family": h1.H1_MODEL_FAMILY,
        "model_config": _resolved_config(),
        "decision_policy": h1.H1_DECISION_POLICY,
        "score_type": h1.H1_SCORE_TYPE,
        "confidence_semantics": h1.H1_CONFIDENCE_SEMANTICS,
        "oof_reference_count": h1.H1_REQUIRED_OOF_SCORES,
        "oof_reference_sha256": reference["oof_reference_sha256"],
        "oof_lower_score": reference["lower_score"],
        "oof_upper_score": reference["upper_score"],
        "oof_diagnostics": _synthetic_oof_diagnostics(),
        "training_class_counts": {0: 810, 1: 810},
        "training_metadata": {"fixture": True, "row_count": 1620},
        "dataset_provenance_sha256": RetrainManager.dataset_provenance_sha256(
            dataset_provenance
        ),
        "independent_validation": evidence,
        "independent_validation_sha256": h1.independent_validation_sha256(evidence),
    }
    metadata.update(overrides)
    return metadata


class _ScoreEstimator:
    def __init__(self, score: float):
        self.score = float(score)
        self.calls = 0

    def predict_proba(self, X):
        self.calls += 1
        score = np.full(len(X), self.score)
        return np.column_stack([1.0 - score, score])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _signal_model(score: float):
    model = SimpleNamespace(
        model_contract=h1.H1_MODEL_CONTRACT,
        target_profile=h1.H1_TARGET_PROFILE,
        target_definition_version=h1.H1_TARGET_DEFINITION_VERSION,
        horizon=h1.H1_HORIZON,
        feature_profile=h1.H1_FEATURE_PROFILE,
        feature_names=list(VALIDATED_FEATURE_NAMES),
        feature_names_sha256=h1.H1_FEATURE_NAMES_SHA256,
        model_family=h1.H1_MODEL_FAMILY,
        model_config=_resolved_config(),
        decision_policy=h1.H1_DECISION_POLICY,
        score_type=h1.H1_SCORE_TYPE,
        confidence_semantics=h1.H1_CONFIDENCE_SEMANTICS,
        oof_score_reference=np.linspace(0.0, 1.0, 600).tolist(),
        oof_reference_count=600,
        oof_reference_sha256=h1.oof_reference_sha256(np.linspace(0.0, 1.0, 600)),
        lower_score=float(np.quantile(np.linspace(0.0, 1.0, 600), 0.25)),
        upper_score=float(np.quantile(np.linspace(0.0, 1.0, 600), 0.75)),
        model_=_ScoreEstimator(score),
        sufficient=False,
    )
    model.predict_proba = model.model_.predict_proba
    return model


def test_validated_feature_identity_is_frozen():
    assert len(VALIDATED_FEATURE_NAMES) == 102
    assert feature_names_sha256(VALIDATED_FEATURE_NAMES) == (
        "5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791"
    )
    assert h1.H1_FEATURE_NAMES_SHA256 == feature_names_sha256(VALIDATED_FEATURE_NAMES)


def test_production_random_forest_is_prediction_equivalent_to_frozen_research():
    X, y = _matrix(rows=180, columns=VALIDATED_FEATURE_NAMES[:6])
    research = FixedHorizonRandomForestClassifier().fit(X, y)
    production, resolved = h1.fit_frozen_h1_random_forest(X, y)

    np.testing.assert_allclose(
        production.predict_proba(X),
        research.predict_proba(X),
        rtol=1e-15,
        atol=1e-15,
    )
    np.testing.assert_array_equal(production.predict(X), research.predict(X))
    assert resolved == research.resolved_config_


def test_oof_geometry_is_exact_and_dynamic():
    positions = h1.h1_oof_positions(1620)
    assert positions == [
        {"train_start": 0, "train_end": 980,
         "validation_start": 1020, "validation_end": 1220},
        {"train_start": 200, "train_end": 1180,
         "validation_start": 1220, "validation_end": 1420},
        {"train_start": 400, "train_end": 1380,
         "validation_start": 1420, "validation_end": 1620},
    ]


def test_candidate_builder_collects_exact_frozen_oof_evidence(monkeypatch):
    X, y = _matrix(rows=1620)
    calls = []

    def fake_fit(X_fit, y_fit):
        calls.append((len(X_fit), set(np.asarray(y_fit))))
        return _ScoreEstimator(0.2 + 0.15 * len(calls)), _resolved_config()

    monkeypatch.setattr(h1, "fit_frozen_h1_random_forest", fake_fit)
    model = h1.H1DirectionalRandomForestModel().fit(
        X,
        y,
        training_metadata={"fixture": True},
        dataset_provenance={"snapshot_sha256": "snapshot"},
    )

    assert calls == [
        (980, {0, 1}),
        (980, {0, 1}),
        (980, {0, 1}),
        (1620, {0, 1}),
    ]
    assert model.oof_reference_count == 600
    assert len(model.oof_diagnostics) == 3
    assert all(record["validation_rows"] == 200 for record in model.oof_diagnostics)
    assert all(set(record["train_class_counts"]) == {0, 1}
               for record in model.oof_diagnostics)
    assert model.training_metadata["row_count"] == 1620


def test_oof_requires_exactly_three_folds():
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INSUFFICIENT"):
        h1.h1_oof_positions(1419)


@pytest.mark.parametrize("count", [0, 599, 601])
def test_oof_reference_requires_exactly_600_finite_scores(count):
    scores = np.linspace(0.0, 1.0, count) if count else []
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INSUFFICIENT"):
        h1.build_oof_decision_reference(scores)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_oof_reference_rejects_non_finite_scores(bad):
    scores = np.linspace(0.0, 1.0, 600)
    scores[100] = bad
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INSUFFICIENT"):
        h1.build_oof_decision_reference(scores)


def test_quartile_policy_depends_only_on_scores_not_labels():
    scores = np.linspace(0.0, 1.0, 600) ** 2
    labels_a = np.arange(600) % 2
    labels_b = 1 - labels_a
    a = h1.build_oof_decision_reference(scores, diagnostic_labels=labels_a)
    b = h1.build_oof_decision_reference(scores, diagnostic_labels=labels_b)

    assert a["lower_score"] == b["lower_score"]
    assert a["upper_score"] == b["upper_score"]
    assert a["oof_reference_sha256"] == b["oof_reference_sha256"]


def test_oof_reference_and_sha_are_deterministic_and_sorted():
    scores = np.random.default_rng(42).uniform(size=600)
    first = h1.build_oof_decision_reference(scores)
    second = h1.build_oof_decision_reference(scores[::-1])

    assert first == second
    assert first["oof_score_reference"] == sorted(first["oof_score_reference"])
    assert first["oof_reference_count"] == 600
    assert first["oof_reference_sha256"] == h1.oof_reference_sha256(
        first["oof_score_reference"]
    )


def test_empirical_percentile_and_quartile_boundaries_are_deterministic_inclusive():
    reference = h1.build_oof_decision_reference(np.linspace(0.0, 1.0, 600))

    lower = h1.h1_direction_decision(reference["lower_score"], reference)
    upper = h1.h1_direction_decision(reference["upper_score"], reference)
    middle = h1.h1_direction_decision(0.50, reference)

    assert lower["decision_percentile"] == 0.25
    assert lower["action"] == "SELL"
    assert upper["decision_percentile"] == 0.75
    assert upper["action"] == "BUY"
    assert middle["action"] == "HOLD"


@pytest.mark.parametrize(
    ("score", "action"),
    [(0.80, "BUY"), (0.20, "SELL"), (0.50, "HOLD")],
)
def test_predictor_h1_uses_only_oof_quartile_policy(score, action, monkeypatch):
    from forex.prediction.predictor import ForexPredictor

    model = _signal_model(score)
    predictor = ForexPredictor(min_confidence=0.99, min_adx=999.0)
    monkeypatch.setattr(predictor, "load_model", lambda pair=None: model)
    X = pd.DataFrame([[0.0] * len(VALIDATED_FEATURE_NAMES)], columns=VALIDATED_FEATURE_NAMES)
    X["ADX_14"] = 0.0

    result = predictor.signal(X, pair="EURUSD")

    assert result["action"] == action
    assert result["direction_score"] == score
    assert result["decision_policy"] == h1.H1_DECISION_POLICY
    assert result["score_type"] == h1.H1_SCORE_TYPE
    assert result["confidence_semantics"] == h1.H1_CONFIDENCE_SEMANTICS
    assert result["confidence"] == pytest.approx(2 * abs(result["decision_percentile"] - 0.5))
    assert "est_prob_correct" not in result
    assert result["model_contract"] == h1.H1_MODEL_CONTRACT


def test_h1_feature_sha_mismatch_holds_without_calling_model(monkeypatch):
    from forex.prediction.predictor import ForexPredictor

    model = _signal_model(0.90)
    predictor = ForexPredictor()
    monkeypatch.setattr(predictor, "load_model", lambda pair=None: model)
    X = pd.DataFrame([[0.0] * (len(VALIDATED_FEATURE_NAMES) - 1)],
                     columns=VALIDATED_FEATURE_NAMES[:-1])

    result = predictor.signal(X, pair="EURUSD")

    assert result["action"] == "HOLD"
    assert result["model_valid"] is False
    assert result["hold_reason"] == "H1_FEATURE_SHA_MISMATCH"
    assert model.model_.calls == 0


def test_h1_feature_profile_dispatch_requests_stationary_v1(monkeypatch):
    from forex.prediction import predictor as predictor_module

    model = _signal_model(0.90)
    predictor = predictor_module.ForexPredictor()
    monkeypatch.setattr(predictor, "load_model", lambda pair=None: model)
    calls = []

    def predict_features(self, **kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            [[0.0] * len(VALIDATED_FEATURE_NAMES)], columns=VALIDATED_FEATURE_NAMES
        )

    monkeypatch.setattr(predictor_module.DatasetBuilder, "predict_features", predict_features)

    prepared = predictor.prepare_features(pd.DataFrame({"close": [1.0]}), pair="EURUSD")

    assert list(prepared.columns) == VALIDATED_FEATURE_NAMES
    assert calls == [{"n_rows": 1, "feature_profile": "stationary_v1"}]


def test_h1_bridge_summary_makes_no_probability_claim(monkeypatch):
    from forex.prediction.forex_prediction_bridge import ForexPredictionBridge

    bridge = ForexPredictionBridge()
    monkeypatch.setattr(
        bridge,
        "analyze",
        lambda *_args, **_kwargs: {
            "pair": "EURUSD",
            "action": "BUY",
            "model_contract": h1.H1_MODEL_CONTRACT,
            "direction_score": 0.73,
            "decision_percentile": 0.82,
            "confidence": 0.64,
        },
    )

    result = bridge.analyze_for_astra("unused.csv", pair="EURUSD")

    assert "direction_score=0.7300" in result["summary"]
    assert "percentile=0.8200" in result["summary"]
    assert "prob_acierto" not in result["summary"]


def test_legacy_bridge_summary_keeps_existing_probability_surface(monkeypatch):
    from forex.prediction.forex_prediction_bridge import ForexPredictionBridge

    bridge = ForexPredictionBridge()
    monkeypatch.setattr(
        bridge,
        "analyze",
        lambda *_args, **_kwargs: {
            "pair": "EURUSD",
            "action": "BUY",
            "confidence": 0.80,
            "est_prob_correct": 80.0,
            "signal_strength": 75.0,
        },
    )

    result = bridge.analyze_for_astra("unused.csv", pair="EURUSD")

    assert "prob_acierto=80.0%" in result["summary"]


def test_legacy_predictor_keeps_confidence_and_adx_gates(monkeypatch):
    from forex.prediction.predictor import ForexPredictor

    class Legacy:
        sufficient = True

        @staticmethod
        def predict_proba(X):
            return np.tile([0.2, 0.8], (len(X), 1))

    predictor = ForexPredictor(min_confidence=0.65, min_adx=22.0)
    monkeypatch.setattr(predictor, "load_model", lambda pair=None: Legacy())
    result = predictor.signal(pd.DataFrame({"feature": [1.0], "ADX_14": [10.0]}), pair="EURUSD")

    assert result["action"] == "HOLD"
    assert result["est_prob_correct"] == 80.0
    assert "ADX 10.0 < 22.0" in result["hold_reason"]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"auc": 0.549, "auc_delta": 0.029}, "H1_INDEPENDENT_AUC_GATE"),
        ({"ap_lift": 0.0, "ap_lift_delta": -0.01}, "H1_INDEPENDENT_AP_LIFT_GATE"),
        ({"comparator_auc": 0.60, "auc_delta": 0.0}, "H1_COMPARATOR_AUC_GATE"),
        ({"comparator_ap_lift": 0.05, "ap_lift_delta": 0.0}, "H1_COMPARATOR_AP_LIFT_GATE"),
        ({"buy_count": 29, "sell_count": 30, "hold_count": 141,
          "coverage": 0.295, "pooled_action_precision": 0.565},
         "H1_ACTION_COVERAGE_GATE"),
        ({"buy_count": 19, "sell_count": 41, "hold_count": 140,
          "coverage": 0.30, "pooled_action_precision": 0.5668333333333333},
         "H1_BUY_SIGNALS_GATE"),
        ({"buy_count": 41, "sell_count": 19, "hold_count": 140,
          "coverage": 0.30, "pooled_action_precision": 0.5631666666666667},
         "H1_SELL_SIGNALS_GATE"),
        ({"buy_precision": 0.50, "pooled_action_precision": 0.535},
         "H1_BUY_PRECISION_GATE"),
        ({"sell_precision": 0.50, "pooled_action_precision": 0.53},
         "H1_SELL_PRECISION_GATE"),
        ({"buy_precision": 0.54, "sell_precision": 0.55,
          "pooled_action_precision": 0.545}, "H1_POOLED_ACTION_PRECISION_GATE"),
    ],
)
def test_h1_independent_validation_gates_fail_closed(mutation, reason):
    provenance = {"snapshot_sha256": "snapshot"}
    evidence = _independent_evidence(**mutation)
    metadata = _metadata(
        provenance,
        independent_validation=evidence,
        independent_validation_sha256=h1.independent_validation_sha256(evidence),
    )

    assert h1.h1_production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance=provenance,
    ) == reason


def test_h1_missing_independent_validation_fails_closed():
    metadata = _metadata()
    metadata.pop("independent_validation")
    metadata.pop("independent_validation_sha256")

    assert RetrainManager._production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance={"snapshot_sha256": "snapshot"},
    ) == "H1_INDEPENDENT_VALIDATION_MISSING"


def test_h1_independent_evidence_sha_mismatch_fails_closed():
    metadata = _metadata(independent_validation_sha256="0" * 64)
    assert h1.h1_production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance={"snapshot_sha256": "snapshot"},
    ) == "H1_INDEPENDENT_VALIDATION_SHA_MISMATCH"


def test_h1_dataset_provenance_mismatch_fails_closed():
    metadata = _metadata(dataset_provenance_sha256="0" * 64)
    assert h1.h1_production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance={"snapshot_sha256": "snapshot"},
    ) == "DATASET_PROVENANCE_MISMATCH"


def test_complete_h1_metadata_passes_without_legacy_65_percent_fields():
    metadata = _metadata()
    assert "precision" not in metadata
    assert "calibration" not in metadata
    assert "wfv" not in metadata

    assert RetrainManager._production_eligibility_error(
        metadata,
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance={"snapshot_sha256": "snapshot"},
    ) == ""


def test_legacy_metadata_still_uses_original_eligibility_path():
    assert RetrainManager._production_eligibility_error(
        {},
        symbol="EURUSD",
        timeframe="H1",
        trigger="initial_training",
        dataset_provenance={"snapshot_sha256": "snapshot"},
    ) == "QUALITY_GATE_EVIDENCE_MISSING"


def _synthetic_fitted_h1_model():
    X, y = _matrix(rows=180)
    fitted, config = h1.fit_frozen_h1_random_forest(X, y)
    model = h1.H1DirectionalRandomForestModel()
    model.model_ = fitted
    model.model_config = config
    model.training_class_counts = {0: 810, 1: 810}
    model.feature_names = list(VALIDATED_FEATURE_NAMES)
    model.feature_names_sha256 = h1.H1_FEATURE_NAMES_SHA256
    model.install_oof_reference(np.linspace(0.0, 1.0, 600))
    model.oof_diagnostics = _synthetic_oof_diagnostics()
    model.training_metadata = {"fixture": True, "row_count": 1620}
    model.dataset_provenance = {"snapshot_sha256": "snapshot"}
    return model


def _qualified_database(path):
    from forex.data.symbol_catalog import get_symbol_spec

    database = SQLiteDatabase(str(path))
    spec = get_symbol_spec("EURUSD")
    database.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='qualified' WHERE symbol_code='EURUSD'"
        )
    return database


def test_h1_promotion_without_independent_validation_is_rejected_before_artifact(tmp_path):
    from forex.prediction.model_storage import ModelStorage

    database = _qualified_database(tmp_path / "missing-validation.sqlite")
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    metadata = _metadata()
    metadata.pop("independent_validation")
    metadata.pop("independent_validation_sha256")

    with pytest.raises(ValueError, match="H1_INDEPENDENT_VALIDATION_MISSING"):
        manager.promote_initial_model(
            _synthetic_fitted_h1_model(),
            pair="EURUSD",
            dataset_provenance={"snapshot_sha256": "snapshot"},
            feature_names=VALIDATED_FEATURE_NAMES,
            metadata=metadata,
        )

    assert storage.latest_exists("EURUSD") is False
    assert database.get_retrain_runs("EURUSD") == []


def test_complete_synthetic_h1_can_promote_and_audit(tmp_path):
    from forex.prediction.model_storage import ModelStorage

    database = _qualified_database(tmp_path / "eligible.sqlite")
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    provenance = {"snapshot_sha256": "snapshot"}
    model = _synthetic_fitted_h1_model()

    result = manager.promote_initial_model(
        model,
        pair="EURUSD",
        dataset_provenance=provenance,
        feature_names=VALIDATED_FEATURE_NAMES,
        metadata=_metadata(provenance),
    )

    assert result["status"] == "PROMOTED"
    audit = manager.audit_pair_model("EURUSD")
    assert audit["eligible"] is True
    assert audit["reason"] == "PRODUCTION_ELIGIBLE"
    assert audit["model_id"].startswith("model_")


def test_model_storage_round_trip_and_oof_integrity_audit(tmp_path):
    from forex.prediction.model_storage import ModelStorage

    model = _synthetic_fitted_h1_model()
    metadata = _metadata()
    storage = ModelStorage(tmp_path / "models")
    artifact = storage.stage_model(
        model,
        name="h1_rf",
        version="v1",
        feature_names=VALIDATED_FEATURE_NAMES,
        metadata=metadata,
    )

    bundle = storage.validate_artifact(artifact)
    assert bundle["model"].model_contract == h1.H1_MODEL_CONTRACT
    assert bundle["feature_names"] == VALIDATED_FEATURE_NAMES

    tampered = copy.deepcopy(bundle)
    tampered["model"].upper_score += 0.01
    tampered_path = tmp_path / "models" / "tampered-threshold.pkl"
    joblib.dump(tampered, tampered_path)
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INTEGRITY"):
        storage.validate_artifact(tampered_path)

    tampered = copy.deepcopy(bundle)
    tampered["model"].oof_score_reference[0] = 0.99
    tampered_path = tmp_path / "models" / "tampered-reference.pkl"
    joblib.dump(tampered, tampered_path)
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INTEGRITY"):
        storage.validate_artifact(tampered_path)

    tampered = copy.deepcopy(bundle)
    tampered["metadata"]["oof_reference_sha256"] = "0" * 64
    tampered_path = tmp_path / "models" / "tampered-metadata-reference.pkl"
    joblib.dump(tampered, tampered_path)
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INTEGRITY"):
        storage.validate_artifact(tampered_path)

    tampered = copy.deepcopy(bundle)
    tampered["model"].oof_diagnostics[0]["train_class_counts"] = {0: 980, 1: 0}
    tampered["metadata"]["oof_diagnostics"] = tampered["model"].oof_diagnostics
    tampered_path = tmp_path / "models" / "tampered-oof-geometry.pkl"
    joblib.dump(tampered, tampered_path)
    with pytest.raises(ValueError, match="H1_OOF_REFERENCE_INSUFFICIENT"):
        storage.validate_artifact(tampered_path)
