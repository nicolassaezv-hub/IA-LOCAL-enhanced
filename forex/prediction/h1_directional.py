"""Production contract for the validated H1 directional Random Forest.

This module defines ranking-score and abstention semantics only.  It does not
publish artifacts, activate symbols, or make any execution/profitability claim.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score

from .dataset_builder import feature_names_sha256
from .xgb_trainer import WalkForwardValidator


H1_MODEL_CONTRACT = "h1_direction_rf_v1"
H1_TARGET_PROFILE = "fixed_horizon_direction_v1"
H1_TARGET_DEFINITION_VERSION = 1
H1_HORIZON = 12
H1_FEATURE_PROFILE = "stationary_v1"
H1_FEATURE_NAMES_SHA256 = (
    "5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791"
)
H1_MODEL_FAMILY = "RandomForestClassifier"
H1_DECISION_POLICY = "oof_quartile_abstention_v1"
H1_SCORE_TYPE = "rf_raw_p_up_v1"
H1_CONFIDENCE_SEMANTICS = "oof_percentile_extremeness_v1"
H1_TERMINAL_DIRECTION_EVALUATION = "terminal_direction_at_horizon_v1"

H1_OOF_WINDOW = 1000
H1_OOF_STEP = 200
H1_OOF_PURGE = 20
H1_REQUIRED_OOF_FOLDS = 3
H1_OOF_VALIDATION_ROWS = 200
H1_REQUIRED_OOF_SCORES = 600
H1_LOWER_PERCENTILE = 0.25
H1_UPPER_PERCENTILE = 0.75

H1_INDEPENDENT_VALIDATION_PROTOCOL = "post_outer_tail_v1"
H1_INDEPENDENT_MIN_ROWS = 200
H1_INDEPENDENT_MIN_AUC = 0.55
H1_INDEPENDENT_MIN_COVERAGE = 0.30
H1_INDEPENDENT_MIN_BUY_SIGNALS = 20
H1_INDEPENDENT_MIN_SELL_SIGNALS = 20
H1_INDEPENDENT_MIN_BUY_PRECISION = 0.50
H1_INDEPENDENT_MIN_SELL_PRECISION = 0.50
H1_INDEPENDENT_MIN_POOLED_PRECISION = 0.55

_FROZEN_RF_CONFIG = {
    "n_estimators": 300,
    "max_depth": 8,
    "min_samples_leaf": 15,
    "class_weight_strategy": "TRAIN_NEGATIVE_TO_POSITIVE_RATIO",
    "random_state": 42,
    "n_jobs": -1,
}


def fixed_h1_production_rf_config() -> dict:
    """Return the immutable RF configuration validated by both holdouts."""
    return dict(_FROZEN_RF_CONFIG)


def fit_frozen_h1_random_forest(X, y) -> tuple[RandomForestClassifier, dict]:
    """Fit exactly the validated RF, resolving class weight on training only."""
    targets = np.asarray(y)
    positives = int(np.sum(targets == 1))
    negatives = int(np.sum(targets == 0))
    if positives == 0 or negatives == 0 or positives + negatives != len(targets):
        raise ValueError("H1_TRAINING_REQUIRES_BOTH_BINARY_CLASSES")
    class_weight = {0: 1.0, 1: negatives / positives}
    model = RandomForestClassifier(
        n_estimators=_FROZEN_RF_CONFIG["n_estimators"],
        max_depth=_FROZEN_RF_CONFIG["max_depth"],
        min_samples_leaf=_FROZEN_RF_CONFIG["min_samples_leaf"],
        class_weight=class_weight,
        random_state=_FROZEN_RF_CONFIG["random_state"],
        n_jobs=_FROZEN_RF_CONFIG["n_jobs"],
    )
    model.fit(X, targets)
    return model, {**fixed_h1_production_rf_config(), "class_weight": class_weight}


def h1_oof_positions(n_rows: int) -> list[dict[str, int]]:
    """Return or reject the frozen three-fold temporal OOF geometry."""
    validator = WalkForwardValidator(
        window=H1_OOF_WINDOW,
        step=H1_OOF_STEP,
        purge=H1_OOF_PURGE,
        n_folds=H1_REQUIRED_OOF_FOLDS,
    )
    positions = validator.split_positions(int(n_rows))
    if (
        len(positions) != H1_REQUIRED_OOF_FOLDS
        or any(
            item["validation_end"] - item["validation_start"]
            != H1_OOF_VALIDATION_ROWS
            for item in positions
        )
    ):
        raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
    return positions


def _finite_scores(scores) -> np.ndarray:
    values = np.asarray(scores, dtype=float).reshape(-1)
    if (
        len(values) != H1_REQUIRED_OOF_SCORES
        or not np.isfinite(values).all()
        or ((values < 0.0) | (values > 1.0)).any()
    ):
        raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
    return values


def oof_reference_sha256(scores) -> str:
    values = [float(value) for value in np.asarray(scores, dtype=float).reshape(-1)]
    payload = json.dumps(values, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_oof_decision_reference(scores, *, diagnostic_labels=None) -> dict:
    """Freeze sorted score-only quartiles; labels cannot influence thresholds."""
    del diagnostic_labels
    values = np.sort(_finite_scores(scores))
    return {
        "oof_score_reference": values.tolist(),
        "oof_reference_count": len(values),
        "oof_reference_sha256": oof_reference_sha256(values),
        "lower_score": float(np.quantile(values, H1_LOWER_PERCENTILE)),
        "upper_score": float(np.quantile(values, H1_UPPER_PERCENTILE)),
    }


def empirical_score_percentile(score: float, sorted_reference) -> float:
    value = float(score)
    reference = _finite_scores(sorted_reference)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("H1_DIRECTION_SCORE_INVALID")
    if np.any(reference[1:] < reference[:-1]):
        raise ValueError("H1_OOF_REFERENCE_INTEGRITY")
    return float(np.searchsorted(reference, value, side="right") / len(reference))


def h1_direction_decision(score: float, reference: dict | Any) -> dict:
    sorted_reference = (
        reference["oof_score_reference"]
        if isinstance(reference, dict)
        else reference.oof_score_reference
    )
    percentile = empirical_score_percentile(score, sorted_reference)
    if percentile >= H1_UPPER_PERCENTILE:
        action = "BUY"
    elif percentile <= H1_LOWER_PERCENTILE:
        action = "SELL"
    else:
        action = "HOLD"
    extremeness = float(np.clip(2.0 * abs(percentile - 0.5), 0.0, 1.0))
    return {
        "action": action,
        "direction_score": float(score),
        "decision_percentile": percentile,
        "decision_extremeness": extremeness,
    }


class H1DirectionalRandomForestModel:
    """Serializable H1 model plus its immutable temporal score reference."""

    model_contract = H1_MODEL_CONTRACT
    target_profile = H1_TARGET_PROFILE
    target_definition_version = H1_TARGET_DEFINITION_VERSION
    horizon = H1_HORIZON
    feature_profile = H1_FEATURE_PROFILE
    model_family = H1_MODEL_FAMILY
    decision_policy = H1_DECISION_POLICY
    score_type = H1_SCORE_TYPE
    confidence_semantics = H1_CONFIDENCE_SEMANTICS

    def __init__(self):
        self.model_: RandomForestClassifier | None = None
        self.model_config: dict | None = None
        self.training_class_counts: dict[int, int] | None = None
        self.feature_names: list[str] = []
        self.feature_names_sha256: str = ""
        self.oof_score_reference: list[float] = []
        self.oof_reference_count = 0
        self.oof_reference_sha256 = ""
        self.lower_score = math.nan
        self.upper_score = math.nan
        self.oof_diagnostics: list[dict] = []
        self.training_metadata: dict = {}
        self.dataset_provenance: dict = {}

    def install_oof_reference(self, scores) -> None:
        reference = build_oof_decision_reference(scores)
        for field, value in reference.items():
            setattr(self, field, value)

    def fit(
        self,
        X: pd.DataFrame,
        y,
        *,
        training_metadata: dict | None = None,
        dataset_provenance: dict | None = None,
    ):
        if not isinstance(X, pd.DataFrame):
            raise ValueError("H1_FEATURE_FRAME_REQUIRED")
        names = [str(name) for name in X.columns]
        if feature_names_sha256(names) != H1_FEATURE_NAMES_SHA256:
            raise ValueError("H1_FEATURE_SHA_MISMATCH")
        targets = pd.Series(np.asarray(y), index=X.index)
        if len(targets) != len(X):
            raise ValueError("H1_TARGET_LENGTH_MISMATCH")

        positions = h1_oof_positions(len(X))
        scores: list[float] = []
        fold_records: list[dict] = []
        for fold_number, position in enumerate(positions, start=1):
            train_slice = slice(position["train_start"], position["train_end"])
            validation_slice = slice(
                position["validation_start"], position["validation_end"]
            )
            X_train = X.iloc[train_slice]
            y_train = targets.iloc[train_slice]
            X_validation = X.iloc[validation_slice]
            y_validation = targets.iloc[validation_slice]
            if y_train.nunique() != 2:
                raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
            fold_model, _ = fit_frozen_h1_random_forest(X_train, y_train)
            fold_scores = fold_model.predict_proba(X_validation)[:, 1]
            if len(fold_scores) != H1_OOF_VALIDATION_ROWS:
                raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
            scores.extend(float(value) for value in fold_scores)
            prevalence = float(np.mean(y_validation))
            validation_has_both_classes = y_validation.nunique() == 2
            train_class_counts = {
                0: int(np.sum(y_train == 0)),
                1: int(np.sum(y_train == 1)),
            }
            fold_records.append({
                "fold": fold_number,
                **position,
                "train_class_counts": train_class_counts,
                "validation_rows": len(y_validation),
                "auc": (
                    float(roc_auc_score(y_validation, fold_scores))
                    if validation_has_both_classes else None
                ),
                "ap": float(average_precision_score(y_validation, fold_scores)),
                "ap_lift": float(
                    average_precision_score(y_validation, fold_scores) - prevalence
                ),
                "accuracy_at_0_5": float(
                    accuracy_score(y_validation, fold_scores >= 0.5)
                ),
            })

        self.install_oof_reference(scores)
        offset = 0
        for record, position in zip(fold_records, positions):
            fold_scores = scores[offset : offset + H1_OOF_VALIDATION_ROWS]
            y_validation = targets.iloc[
                position["validation_start"] : position["validation_end"]
            ].to_numpy()
            decisions = [h1_direction_decision(score, self) for score in fold_scores]
            actions = [item["action"] for item in decisions]
            buy = sum(action == "BUY" for action in actions)
            sell = sum(action == "SELL" for action in actions)
            hold = len(actions) - buy - sell
            emitted_correct = [
                (action == "BUY" and target == 1)
                or (action == "SELL" and target == 0)
                for action, target in zip(actions, y_validation)
                if action != "HOLD"
            ]
            record.update({
                "buy_count": buy,
                "sell_count": sell,
                "hold_count": hold,
                "decision_coverage": (buy + sell) / len(actions),
                "emitted_directional_precision": (
                    float(np.mean(emitted_correct)) if emitted_correct else 0.0
                ),
            })
            offset += H1_OOF_VALIDATION_ROWS
        self.oof_diagnostics = fold_records
        self.model_, self.model_config = fit_frozen_h1_random_forest(X, targets)
        self.training_class_counts = {
            0: int(np.sum(targets == 0)),
            1: int(np.sum(targets == 1)),
        }
        self.feature_names = names
        self.feature_names_sha256 = feature_names_sha256(names)
        self.training_metadata = dict(training_metadata or {})
        declared_rows = self.training_metadata.get("row_count")
        if declared_rows is not None and declared_rows != len(X):
            raise ValueError("H1_TRAINING_METADATA_MISMATCH")
        self.training_metadata["row_count"] = len(X)
        self.dataset_provenance = dict(dataset_provenance or {})
        return self

    def _fitted_model(self) -> RandomForestClassifier:
        if self.model_ is None:
            raise NotFittedError("H1DirectionalRandomForestModel is not fitted")
        return self.model_

    def predict_proba(self, X):
        return self._fitted_model().predict_proba(X)

    def predict(self, X):
        return self._fitted_model().predict(X)


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def independent_validation_sha256(evidence: dict) -> str:
    if not isinstance(evidence, dict):
        raise ValueError("H1_INDEPENDENT_VALIDATION_MISSING")
    return _canonical_sha256(evidence)


def _dataset_provenance_sha256(dataset_provenance: dict) -> str:
    if not isinstance(dataset_provenance, dict) or not dataset_provenance:
        raise ValueError("dataset provenance is required")
    return _canonical_sha256(dataset_provenance)


def _finite_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _rf_config_valid(config: Any) -> bool:
    if not isinstance(config, dict):
        return False
    if any(config.get(key) != value for key, value in _FROZEN_RF_CONFIG.items()):
        return False
    weights = config.get("class_weight")
    if not isinstance(weights, dict):
        return False
    zero = weights.get(0, weights.get("0"))
    one = weights.get(1, weights.get("1"))
    return (
        _finite_number(zero) == 1.0
        and _finite_number(one) is not None
        and float(one) > 0.0
    )


def _h1_identity_error(metadata: dict, *, symbol: str, timeframe: str, trigger: str) -> str:
    exact = (
        ("model_contract", H1_MODEL_CONTRACT, "H1_MODEL_CONTRACT_MISMATCH"),
        ("target_profile", H1_TARGET_PROFILE, "H1_TARGET_PROFILE_MISMATCH"),
        ("target_definition_version", H1_TARGET_DEFINITION_VERSION, "H1_TARGET_VERSION_MISMATCH"),
        ("horizon", H1_HORIZON, "H1_HORIZON_MISMATCH"),
        ("feature_profile", H1_FEATURE_PROFILE, "H1_FEATURE_PROFILE_MISMATCH"),
        ("feature_names_sha256", H1_FEATURE_NAMES_SHA256, "H1_FEATURE_SHA_MISMATCH"),
        ("model_family", H1_MODEL_FAMILY, "H1_MODEL_FAMILY_MISMATCH"),
        ("decision_policy", H1_DECISION_POLICY, "H1_DECISION_POLICY_MISMATCH"),
        ("score_type", H1_SCORE_TYPE, "H1_SCORE_TYPE_MISMATCH"),
        ("confidence_semantics", H1_CONFIDENCE_SEMANTICS, "H1_CONFIDENCE_SEMANTICS_MISMATCH"),
    )
    for field, expected, reason in exact:
        if metadata.get(field) != expected:
            return reason
    requested_symbol = str(symbol).upper().replace("/", "").replace("_", "")
    metadata_symbol = str(metadata.get("symbol", "")).upper().replace("/", "").replace("_", "")
    if requested_symbol != "EURUSD" or metadata_symbol != requested_symbol:
        return "SYMBOL_PROVENANCE_MISMATCH"
    if str(timeframe).upper() != "H1" or str(metadata.get("timeframe", "")).upper() != "H1":
        return "TIMEFRAME_PROVENANCE_MISMATCH"
    if metadata.get("promotion_type") != trigger:
        return "TRIGGER_PROVENANCE_MISMATCH"
    if not _rf_config_valid(metadata.get("model_config")):
        return "H1_RF_CONFIG_MISMATCH"
    if metadata.get("oof_reference_count") != H1_REQUIRED_OOF_SCORES:
        return "H1_OOF_REFERENCE_INSUFFICIENT"
    return ""


def _independent_validation_error(evidence: dict) -> str:
    identity_fields = (
        "source_sha", "snapshot_sha", "validation_start_position",
        "validation_end_position", "validation_start_timestamp",
        "validation_end_timestamp",
    )
    if any(evidence.get(field) in (None, "") for field in identity_fields):
        return "H1_INDEPENDENT_VALIDATION_IDENTITY_MISSING"
    if evidence.get("protocol") != H1_INDEPENDENT_VALIDATION_PROTOCOL:
        return "H1_INDEPENDENT_VALIDATION_PROTOCOL_MISMATCH"
    rows = evidence.get("row_count")
    start = evidence.get("validation_start_position")
    end = evidence.get("validation_end_position")
    if any(not isinstance(value, int) or isinstance(value, bool)
           for value in (rows, start, end)):
        return "H1_INDEPENDENT_VALIDATION_IDENTITY_MISSING"
    if start < 0 or rows < H1_INDEPENDENT_MIN_ROWS or end - start != rows:
        return "H1_INDEPENDENT_VALIDATION_ROWS_GATE"
    names = (
        "auc", "ap", "ap_lift", "comparator_auc", "comparator_ap_lift",
        "auc_delta", "ap_lift_delta", "coverage", "buy_precision",
        "sell_precision", "pooled_action_precision",
    )
    values = {name: _finite_number(evidence.get(name)) for name in names}
    if any(value is None for value in values.values()):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    unit_interval_metrics = (
        "auc", "ap", "comparator_auc", "buy_precision", "sell_precision",
        "pooled_action_precision", "coverage",
    )
    if any(not 0.0 <= values[name] <= 1.0 for name in unit_interval_metrics):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if not math.isclose(
        values["auc_delta"], values["auc"] - values["comparator_auc"],
        rel_tol=1e-12, abs_tol=1e-12,
    ) or not math.isclose(
        values["ap_lift_delta"],
        values["ap_lift"] - values["comparator_ap_lift"],
        rel_tol=1e-12, abs_tol=1e-12,
    ):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if values["auc"] < H1_INDEPENDENT_MIN_AUC:
        return "H1_INDEPENDENT_AUC_GATE"
    if values["ap_lift"] <= 0.0:
        return "H1_INDEPENDENT_AP_LIFT_GATE"
    if values["auc_delta"] <= 0.0:
        return "H1_COMPARATOR_AUC_GATE"
    if values["ap_lift_delta"] <= 0.0:
        return "H1_COMPARATOR_AP_LIFT_GATE"
    buy = evidence.get("buy_count")
    sell = evidence.get("sell_count")
    hold = evidence.get("hold_count")
    if any(not isinstance(value, int) or isinstance(value, bool)
           for value in (buy, sell, hold)):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if min(buy, sell, hold) < 0 or buy + sell + hold != rows:
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    coverage = (buy + sell) / rows
    if not math.isclose(values["coverage"], coverage, rel_tol=1e-12, abs_tol=1e-12):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if coverage < H1_INDEPENDENT_MIN_COVERAGE:
        return "H1_ACTION_COVERAGE_GATE"
    if buy < H1_INDEPENDENT_MIN_BUY_SIGNALS:
        return "H1_BUY_SIGNALS_GATE"
    if sell < H1_INDEPENDENT_MIN_SELL_SIGNALS:
        return "H1_SELL_SIGNALS_GATE"
    if values["buy_precision"] <= H1_INDEPENDENT_MIN_BUY_PRECISION:
        return "H1_BUY_PRECISION_GATE"
    if values["sell_precision"] <= H1_INDEPENDENT_MIN_SELL_PRECISION:
        return "H1_SELL_PRECISION_GATE"
    pooled = (
        buy * values["buy_precision"] + sell * values["sell_precision"]
    ) / (buy + sell)
    if not math.isclose(
        values["pooled_action_precision"], pooled, rel_tol=1e-12, abs_tol=1e-12
    ):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if pooled < H1_INDEPENDENT_MIN_POOLED_PRECISION:
        return "H1_POOLED_ACTION_PRECISION_GATE"
    if evidence.get("passed") is not True:
        return "H1_INDEPENDENT_VALIDATION_FAILED"
    return ""


def h1_production_eligibility_error(
    metadata: dict | None,
    *,
    symbol: str,
    timeframe: str,
    trigger: str,
    dataset_provenance: dict,
) -> str:
    if not isinstance(metadata, dict):
        return "CANDIDATE_METADATA_MISSING"
    reason = _h1_identity_error(
        metadata, symbol=symbol, timeframe=timeframe, trigger=trigger
    )
    if reason:
        return reason
    try:
        expected_provenance = _dataset_provenance_sha256(dataset_provenance)
    except ValueError:
        return "DATASET_PROVENANCE_MISSING"
    if metadata.get("dataset_provenance_sha256") != expected_provenance:
        return "DATASET_PROVENANCE_MISMATCH"
    evidence = metadata.get("independent_validation")
    if not isinstance(evidence, dict):
        return "H1_INDEPENDENT_VALIDATION_MISSING"
    try:
        evidence_sha = independent_validation_sha256(evidence)
    except (TypeError, ValueError):
        return "H1_INDEPENDENT_VALIDATION_EVIDENCE_INVALID"
    if metadata.get("independent_validation_sha256") != evidence_sha:
        return "H1_INDEPENDENT_VALIDATION_SHA_MISMATCH"
    return _independent_validation_error(evidence)


def build_h1_production_metadata(
    model: H1DirectionalRandomForestModel,
    *,
    symbol: str,
    timeframe: str,
    promotion_type: str,
    dataset_provenance: dict,
    independent_validation: dict | None = None,
) -> dict:
    """Build the canonical metadata envelope for a future H1 candidate."""
    if dict(model.dataset_provenance) != dict(dataset_provenance):
        raise ValueError("DATASET_PROVENANCE_MISMATCH")
    metadata = {
        "model_contract": H1_MODEL_CONTRACT,
        "symbol": str(symbol).upper().replace("/", "").replace("_", ""),
        "timeframe": str(timeframe).upper(),
        "promotion_type": promotion_type,
        "target_profile": H1_TARGET_PROFILE,
        "target_definition_version": H1_TARGET_DEFINITION_VERSION,
        "horizon": H1_HORIZON,
        "feature_profile": H1_FEATURE_PROFILE,
        "feature_names_sha256": model.feature_names_sha256,
        "model_family": H1_MODEL_FAMILY,
        "model_config": dict(model.model_config or {}),
        "decision_policy": H1_DECISION_POLICY,
        "score_type": H1_SCORE_TYPE,
        "confidence_semantics": H1_CONFIDENCE_SEMANTICS,
        "oof_reference_count": model.oof_reference_count,
        "oof_reference_sha256": model.oof_reference_sha256,
        "oof_lower_score": model.lower_score,
        "oof_upper_score": model.upper_score,
        "oof_diagnostics": list(model.oof_diagnostics),
        "training_class_counts": dict(model.training_class_counts or {}),
        "training_metadata": dict(model.training_metadata),
        "dataset_provenance_sha256": _dataset_provenance_sha256(
            dataset_provenance
        ),
    }
    if independent_validation is not None:
        metadata["independent_validation"] = dict(independent_validation)
        metadata["independent_validation_sha256"] = (
            independent_validation_sha256(independent_validation)
        )
    return metadata


def h1_runtime_contract_error(model: object, feature_names) -> str:
    """Return a fail-closed reason before one live H1 score is computed."""
    exact = (
        ("model_contract", H1_MODEL_CONTRACT, "H1_MODEL_CONTRACT_MISMATCH"),
        ("target_profile", H1_TARGET_PROFILE, "H1_TARGET_PROFILE_MISMATCH"),
        ("target_definition_version", H1_TARGET_DEFINITION_VERSION, "H1_TARGET_VERSION_MISMATCH"),
        ("horizon", H1_HORIZON, "H1_HORIZON_MISMATCH"),
        ("feature_profile", H1_FEATURE_PROFILE, "H1_FEATURE_PROFILE_MISMATCH"),
        ("model_family", H1_MODEL_FAMILY, "H1_MODEL_FAMILY_MISMATCH"),
        ("decision_policy", H1_DECISION_POLICY, "H1_DECISION_POLICY_MISMATCH"),
        ("score_type", H1_SCORE_TYPE, "H1_SCORE_TYPE_MISMATCH"),
        ("confidence_semantics", H1_CONFIDENCE_SEMANTICS, "H1_CONFIDENCE_SEMANTICS_MISMATCH"),
    )
    for field, expected, reason in exact:
        if getattr(model, field, None) != expected:
            return reason
    names = [str(name) for name in feature_names]
    if (
        names != list(getattr(model, "feature_names", []))
        or feature_names_sha256(names) != H1_FEATURE_NAMES_SHA256
        or getattr(model, "feature_names_sha256", None) != H1_FEATURE_NAMES_SHA256
    ):
        return "H1_FEATURE_SHA_MISMATCH"
    if not callable(getattr(model, "predict_proba", None)):
        return "H1_ARTIFACT_PREDICT_PROBA_MISSING"
    try:
        reference = build_oof_decision_reference(model.oof_score_reference)
    except (AttributeError, TypeError, ValueError):
        return "H1_OOF_REFERENCE_INTEGRITY"
    for field in (
        "oof_reference_count", "oof_reference_sha256", "lower_score", "upper_score"
    ):
        actual = getattr(model, field, None)
        expected = reference[field]
        if isinstance(expected, float):
            if _finite_number(actual) is None or not math.isclose(
                float(actual), expected, rel_tol=1e-12, abs_tol=1e-12
            ):
                return "H1_OOF_REFERENCE_INTEGRITY"
        elif actual != expected:
            return "H1_OOF_REFERENCE_INTEGRITY"
    return ""


def validate_h1_artifact_bundle(bundle: dict) -> None:
    """Recompute all structural identities of one serialized H1 artifact."""
    if not isinstance(bundle, dict):
        raise ValueError("H1_ARTIFACT_INVALID")
    model = bundle.get("model")
    metadata = bundle.get("metadata")
    names = bundle.get("feature_names")
    if getattr(model, "model_contract", None) != H1_MODEL_CONTRACT:
        raise ValueError("H1_MODEL_CONTRACT_MISMATCH")
    if not isinstance(metadata, dict) or metadata.get("model_contract") != H1_MODEL_CONTRACT:
        raise ValueError("H1_MODEL_CONTRACT_MISMATCH")
    if not isinstance(names, list) or not names:
        raise ValueError("H1_FEATURE_NAMES_MISSING")
    names = [str(name) for name in names]
    if (
        feature_names_sha256(names) != H1_FEATURE_NAMES_SHA256
        or getattr(model, "feature_names", None) != names
        or getattr(model, "feature_names_sha256", None) != H1_FEATURE_NAMES_SHA256
        or metadata.get("feature_names_sha256") != H1_FEATURE_NAMES_SHA256
    ):
        raise ValueError("H1_FEATURE_SHA_MISMATCH")
    exact_model_fields = (
        ("target_profile", H1_TARGET_PROFILE),
        ("target_definition_version", H1_TARGET_DEFINITION_VERSION),
        ("horizon", H1_HORIZON),
        ("feature_profile", H1_FEATURE_PROFILE),
        ("model_family", H1_MODEL_FAMILY),
        ("decision_policy", H1_DECISION_POLICY),
        ("score_type", H1_SCORE_TYPE),
        ("confidence_semantics", H1_CONFIDENCE_SEMANTICS),
    )
    if any(getattr(model, field, None) != expected for field, expected in exact_model_fields):
        raise ValueError("H1_ARTIFACT_CONTRACT_MISMATCH")
    if any(metadata.get(field) != expected for field, expected in exact_model_fields):
        raise ValueError("H1_ARTIFACT_CONTRACT_MISMATCH")
    if not _rf_config_valid(getattr(model, "model_config", None)):
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    if metadata.get("model_config") != model.model_config:
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    fitted = getattr(model, "model_", None)
    if (
        not isinstance(fitted, RandomForestClassifier)
        or not callable(getattr(fitted, "predict_proba", None))
    ):
        raise ValueError("H1_ARTIFACT_PREDICT_PROBA_MISSING")
    params = fitted.get_params() if callable(getattr(fitted, "get_params", None)) else {}
    for field in ("n_estimators", "max_depth", "min_samples_leaf", "random_state", "n_jobs"):
        if params.get(field) != _FROZEN_RF_CONFIG[field]:
            raise ValueError("H1_RF_CONFIG_MISMATCH")
    if params.get("class_weight") != model.model_config.get("class_weight"):
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    if (
        list(getattr(fitted, "feature_names_in_", [])) != names
        or getattr(fitted, "n_features_in_", None) != len(names)
    ):
        raise ValueError("H1_FEATURE_SHA_MISMATCH")
    class_counts = getattr(model, "training_class_counts", None)
    if not isinstance(class_counts, dict):
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    negatives = class_counts.get(0, class_counts.get("0"))
    positives = class_counts.get(1, class_counts.get("1"))
    if (
        not isinstance(negatives, int)
        or not isinstance(positives, int)
        or negatives <= 0
        or positives <= 0
        or not math.isclose(
            float(model.model_config["class_weight"][1]),
            negatives / positives,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    ):
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    if metadata.get("training_class_counts") != class_counts:
        raise ValueError("H1_RF_CONFIG_MISMATCH")
    training_metadata = getattr(model, "training_metadata", None)
    if (
        not isinstance(training_metadata, dict)
        or metadata.get("training_metadata") != training_metadata
    ):
        raise ValueError("H1_TRAINING_METADATA_MISMATCH")
    try:
        training_rows = int(training_metadata["row_count"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("H1_TRAINING_METADATA_MISMATCH")
    if training_rows <= 0 or negatives + positives != training_rows:
        raise ValueError("H1_TRAINING_METADATA_MISMATCH")
    dataset_provenance = getattr(model, "dataset_provenance", None)
    try:
        model_provenance_sha = _dataset_provenance_sha256(dataset_provenance)
    except ValueError as exc:
        raise ValueError("DATASET_PROVENANCE_MISSING") from exc
    if metadata.get("dataset_provenance_sha256") != model_provenance_sha:
        raise ValueError("DATASET_PROVENANCE_MISMATCH")
    diagnostics = getattr(model, "oof_diagnostics", None)
    if (
        not isinstance(diagnostics, list)
        or metadata.get("oof_diagnostics") != diagnostics
    ):
        raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
    try:
        expected_positions = h1_oof_positions(training_rows)
    except ValueError as exc:
        raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT") from exc
    if len(diagnostics) != H1_REQUIRED_OOF_FOLDS:
        raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
    position_fields = (
        "train_start", "train_end", "validation_start", "validation_end"
    )
    for fold_number, (record, position) in enumerate(
        zip(diagnostics, expected_positions), start=1
    ):
        if not isinstance(record, dict) or record.get("fold") != fold_number:
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        if any(record.get(field) != position[field] for field in position_fields):
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        if record.get("validation_rows") != H1_OOF_VALIDATION_ROWS:
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        fold_counts = record.get("train_class_counts")
        if not isinstance(fold_counts, dict):
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        fold_zero = fold_counts.get(0, fold_counts.get("0"))
        fold_one = fold_counts.get(1, fold_counts.get("1"))
        if (
            not isinstance(fold_zero, int)
            or isinstance(fold_zero, bool)
            or not isinstance(fold_one, int)
            or isinstance(fold_one, bool)
            or fold_zero <= 0
            or fold_one <= 0
            or fold_zero + fold_one != position["train_end"] - position["train_start"]
        ):
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        buy = record.get("buy_count")
        sell = record.get("sell_count")
        hold = record.get("hold_count")
        if (
            any(not isinstance(value, int) or isinstance(value, bool)
                for value in (buy, sell, hold))
            or min(buy, sell, hold) < 0
            or buy + sell + hold != H1_OOF_VALIDATION_ROWS
        ):
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
        coverage = _finite_number(record.get("decision_coverage"))
        precision = _finite_number(record.get("emitted_directional_precision"))
        if (
            coverage is None
            or precision is None
            or not 0.0 <= precision <= 1.0
            or not math.isclose(
                coverage,
                (buy + sell) / H1_OOF_VALIDATION_ROWS,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("H1_OOF_REFERENCE_INSUFFICIENT")
    reference = np.asarray(getattr(model, "oof_score_reference", []), dtype=float)
    try:
        recomputed = build_oof_decision_reference(reference)
    except ValueError as exc:
        raise ValueError("H1_OOF_REFERENCE_INTEGRITY") from exc
    for field in (
        "oof_reference_count", "oof_reference_sha256", "lower_score", "upper_score"
    ):
        actual = getattr(model, field, None)
        expected = recomputed[field]
        if isinstance(expected, float):
            matches = _finite_number(actual) is not None and math.isclose(
                float(actual), expected, rel_tol=1e-12, abs_tol=1e-12
            )
        else:
            matches = actual == expected
        if not matches:
            raise ValueError("H1_OOF_REFERENCE_INTEGRITY")
    if reference.tolist() != recomputed["oof_score_reference"]:
        raise ValueError("H1_OOF_REFERENCE_INTEGRITY")
    metadata_reference_fields = {
        "oof_reference_count": recomputed["oof_reference_count"],
        "oof_reference_sha256": recomputed["oof_reference_sha256"],
        "oof_lower_score": recomputed["lower_score"],
        "oof_upper_score": recomputed["upper_score"],
    }
    for field, expected in metadata_reference_fields.items():
        actual = metadata.get(field)
        if isinstance(expected, float):
            matches = _finite_number(actual) is not None and math.isclose(
                float(actual), expected, rel_tol=1e-12, abs_tol=1e-12
            )
        else:
            matches = actual == expected
        if not matches:
            raise ValueError("H1_OOF_REFERENCE_INTEGRITY")
