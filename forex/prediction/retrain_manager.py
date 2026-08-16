"""Outcome-driven, recoverable adaptive retraining coordination."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from infra.db.database import SQLiteDatabase
from .model_storage import ModelStorage, _PROMOTION_AUTHORITY

logger = logging.getLogger(__name__)


class RetrainTrigger(str, Enum):
    INITIAL_TRAINING = "initial_training"
    BOOTSTRAP_REVALIDATION = "bootstrap_revalidation"
    WIN_RATE_DROP = "win_rate_drop"
    REGIME_CHANGE = "regime_change"
    NEW_DATA_THRESHOLD = "new_data_threshold"
    OUTCOME_EVIDENCE = "outcome_evidence"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    ACCURACY_DROP = "accuracy_drop"
    NONE = "none"


@dataclass
class RetrainDecision:
    needed: bool = False
    trigger: RetrainTrigger = RetrainTrigger.NONE
    reason: str = ""
    details: dict = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "needed": self.needed,
            "trigger": self.trigger.value,
            "reason": self.reason,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class RetrainRecord:
    pair: str = ""
    timeframe: str = ""
    trigger: str = ""
    old_model: str = ""
    new_model: str = ""
    old_win_rate: float = 0.0
    new_win_rate: float = 0.0
    old_accuracy: float = 0.0
    new_accuracy: float = 0.0
    duration_sec: float = 0.0
    success: bool = False
    error: str = ""
    timestamp: str = ""
    run_id: str = ""
    status: str = "FAILED"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


DEFAULT_CONFIG = {
    "win_rate_drop_threshold": 0.10,
    "accuracy_drop_threshold": 0.05,
    "new_data_threshold": 500,
    "scheduled_interval_days": 7,
    "min_predictions_for_eval": 20,
    "min_new_outcomes": 20,
    "running_timeout_seconds": 3600,
}

RETRAIN_RUNNING_TIMEOUT_ENV = "ASTRA_RETRAIN_RUNNING_TIMEOUT_SECONDS"

_OWNER_TOKEN = f"{os.getpid()}:{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RetrainManager:
    """Create one retrain run per durable outcome evidence window."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        config: dict | None = None,
        *,
        database: SQLiteDatabase | None = None,
        storage: ModelStorage | None = None,
        now_func: Callable[[], datetime] | None = None,
    ):
        if database is not None and db_path is not None:
            raise ValueError("provide database or db_path, not both")
        self.database = database or SQLiteDatabase(str(db_path) if db_path else None)
        self.db_path = self.database.db_path
        configured = dict(config or {})
        if "running_timeout_seconds" not in configured:
            configured["running_timeout_seconds"] = os.getenv(
                RETRAIN_RUNNING_TIMEOUT_ENV,
                str(DEFAULT_CONFIG["running_timeout_seconds"]),
            )
        self.config = {**DEFAULT_CONFIG, **configured}
        if int(self.config["min_new_outcomes"]) <= 0:
            raise ValueError("min_new_outcomes must be positive")
        if float(self.config["running_timeout_seconds"]) <= 0:
            raise ValueError("running_timeout_seconds must be positive")
        self.storage = storage or ModelStorage()
        self._now_func = now_func or (lambda: datetime.now(timezone.utc))

    def _utc_now(self) -> datetime:
        value = self._now_func()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def store_baseline(
        self,
        pair: str,
        timeframe: str,
        model_name: str,
        win_rate: float,
        accuracy: float,
    ) -> None:
        self.database.save_model_quality({
            "symbol": pair.upper(),
            "timeframe": timeframe.upper(),
            "accuracy": accuracy,
            "precision": win_rate,
            "status": "active",
        })

    def get_baseline(
        self, pair: str, timeframe: str, model_name: str = ""
    ) -> dict | None:
        rows = self.database.get_model_quality(pair.upper(), timeframe.upper())
        if not rows:
            return None
        row = rows[0]
        return {
            "pair": pair.upper(),
            "timeframe": timeframe.upper(),
            "model_name": model_name,
            "win_rate": float(row.get("precision") or 0.0),
            "accuracy": float(row.get("accuracy") or 0.0),
            "timestamp": row.get("last_evaluated"),
        }

    def check_retrain_needed(
        self,
        pair: str = "",
        timeframe: str = "H1",
        current_win_rate: float | None = None,
        current_accuracy: float | None = None,
        model_name: str = "",
        new_rows_count: int = 0,
        last_regime: str = "",
        current_regime: str = "",
        last_retrain_date: datetime | None = None,
        prediction_count: int = 0,
    ) -> RetrainDecision:
        decision = RetrainDecision(timestamp=_now())
        baseline = self.get_baseline(pair, timeframe, model_name)
        details: dict = {}
        if baseline:
            details.update({
                "baseline_win_rate": baseline["win_rate"],
                "baseline_accuracy": baseline["accuracy"],
                "baseline_model": baseline["model_name"],
            })
        if current_win_rate is not None and baseline:
            drop = baseline["win_rate"] - current_win_rate
            details["win_rate_drop"] = round(drop, 4)
            if (
                drop >= self.config["win_rate_drop_threshold"]
                and prediction_count >= self.config["min_predictions_for_eval"]
            ):
                return RetrainDecision(
                    True, RetrainTrigger.WIN_RATE_DROP,
                    f"Win rate drop {drop:.1%}", details, decision.timestamp,
                )
        if current_accuracy is not None and baseline:
            drop = baseline["accuracy"] - current_accuracy
            details["accuracy_drop"] = round(drop, 4)
            if (
                drop >= self.config["accuracy_drop_threshold"]
                and prediction_count >= self.config["min_predictions_for_eval"]
            ):
                return RetrainDecision(
                    True, RetrainTrigger.ACCURACY_DROP,
                    f"Accuracy drop {drop:.1%}", details, decision.timestamp,
                )
        if last_regime and current_regime and last_regime != current_regime:
            return RetrainDecision(
                True, RetrainTrigger.REGIME_CHANGE,
                f"Regime changed from {last_regime} to {current_regime}",
                {**details, "last_regime": last_regime, "current_regime": current_regime},
                decision.timestamp,
            )
        if new_rows_count >= self.config["new_data_threshold"]:
            return RetrainDecision(
                True, RetrainTrigger.NEW_DATA_THRESHOLD,
                f"New rows reached {new_rows_count}",
                {**details, "new_rows": new_rows_count}, decision.timestamp,
            )
        comparison_now = (
            datetime.now(timezone.utc)
            if last_retrain_date and last_retrain_date.tzinfo is not None
            else datetime.now()
        )
        if last_retrain_date and (
            comparison_now - last_retrain_date
            >= timedelta(days=self.config["scheduled_interval_days"])
        ):
            return RetrainDecision(
                True, RetrainTrigger.SCHEDULED, "Scheduled interval elapsed",
                details, decision.timestamp,
            )
        decision.details = details
        return decision

    def ensure_pending_from_outcomes(
        self,
        pair: str,
        *,
        timeframe: str = "H1",
        dataset_provenance: dict,
    ) -> dict | None:
        """Persist eligibility once enough new finalized outcomes exist."""
        symbol = pair.upper()
        tf = timeframe.upper()
        existing = self.database.get_retrain_runs(symbol)
        active = next(
            (row for row in existing if row["status"] in {"PENDING", "RUNNING", "VALIDATED"}),
            None,
        )
        if active:
            return active
        last_consumed = max(
            (int(row.get("last_outcome_id") or 0) for row in existing),
            default=0,
        )
        outcomes = self.database.get_finalized_outcomes(symbol, tf, after_id=last_consumed)
        minimum = int(self.config["min_new_outcomes"])
        if len(outcomes) < minimum:
            return None
        outcome_ids = [int(row["id"]) for row in outcomes]
        evidence_payload = json.dumps(
            {
                "symbol": symbol,
                "timeframe": tf,
                "outcome_ids": outcome_ids,
                "dataset_provenance": dataset_provenance,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_key = hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest()
        run_id = "retrain_" + evidence_key[:24]
        latest = self.storage.base_dir / f"latest_{_clean_pair(symbol)}.pkl"
        source_hash = self.storage.checksum(latest) if latest.is_file() else None
        timestamp = _now()
        return self.database.create_retrain_run({
            "run_id": run_id,
            "evidence_key": evidence_key,
            "symbol": symbol,
            "timeframe": tf,
            "trigger": RetrainTrigger.OUTCOME_EVIDENCE.value,
            "status": "PENDING",
            "source_model_path": str(latest) if latest.is_file() else None,
            "source_model_sha256": source_hash,
            "dataset_provenance": dataset_provenance,
            "outcome_ids": outcome_ids,
            "last_outcome_id": outcome_ids[-1],
            "created_at": timestamp,
            "updated_at": timestamp,
        })

    def ensure_bootstrap_revalidation(
        self,
        pair: str,
        *,
        timeframe: str = "H1",
        dataset_provenance: dict,
    ) -> dict | None:
        """Create one durable replacement run for a provable legacy alias."""
        symbol = _clean_pair(pair)
        tf = str(timeframe).upper().strip()
        if tf != "H1":
            return None
        if not isinstance(dataset_provenance, dict) or not dataset_provenance:
            raise ValueError("bootstrap revalidation requires dataset provenance")

        audit = self.audit_pair_model(symbol)
        if not audit.get("bootstrap_revalidation"):
            for run in self.database.get_retrain_runs(symbol, limit=100000):
                if (
                    run.get("timeframe") == tf
                    and run.get("trigger")
                    == RetrainTrigger.BOOTSTRAP_REVALIDATION.value
                    and run.get("status") == "RUNNING"
                ):
                    self._recover_interrupted_running(run)
            return None
        latest = self.storage.base_dir / f"latest_{symbol}.pkl"
        source_path = Path(audit["source_model_path"])
        source_hash = audit["source_model_sha256"]
        if source_path.resolve() != latest.resolve() or not latest.is_file():
            return None
        try:
            self.storage.validate_artifact(latest)
            current_hash = self.storage.checksum(latest)
        except Exception:
            return None
        if current_hash != source_hash:
            return None

        existing = next(
            (
                run for run in self.database.get_retrain_runs(symbol, limit=100000)
                if run.get("timeframe") == tf
                and run.get("trigger") == RetrainTrigger.BOOTSTRAP_REVALIDATION.value
                and run.get("source_model_sha256") == source_hash
            ),
            None,
        )
        if existing is not None:
            if existing.get("status") == "RUNNING":
                transitioned = self._recover_interrupted_running(existing)
                if transitioned is not None:
                    return transitioned
                return self._get_run(existing["run_id"])
            return existing

        evidence_identity = {
            "symbol": symbol,
            "timeframe": tf,
            "trigger": RetrainTrigger.BOOTSTRAP_REVALIDATION.value,
            "source_model_sha256": source_hash,
        }
        evidence_payload = json.dumps(
            evidence_identity, sort_keys=True, separators=(",", ":")
        )
        evidence_key = hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest()
        timestamp = _now()
        return self.database.create_retrain_run({
            "run_id": "bootstrap_" + evidence_key[:24],
            "evidence_key": evidence_key,
            "symbol": symbol,
            "timeframe": tf,
            "trigger": RetrainTrigger.BOOTSTRAP_REVALIDATION.value,
            "status": "PENDING",
            "source_model_path": str(latest),
            "source_model_sha256": source_hash,
            "dataset_provenance": dataset_provenance,
            "outcome_ids": [],
            "last_outcome_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        })

    def _get_run(self, run_id: str) -> dict:
        run = next(
            (row for row in self.database.get_retrain_runs(limit=100000) if row["run_id"] == run_id),
            None,
        )
        if not run:
            raise KeyError(f"unknown retrain run {run_id}")
        return run

    def _recover_interrupted_running(self, run: dict) -> dict | None:
        """Recover only a stale, checksum-identical bootstrap; fail other stale runs."""
        if run.get("status") != "RUNNING":
            return None
        heartbeat = run.get("heartbeat_at") or run.get("updated_at")
        heartbeat_time = None
        if heartbeat:
            try:
                heartbeat_time = datetime.fromisoformat(
                    str(heartbeat).replace("Z", "+00:00")
                )
            except ValueError:
                heartbeat_time = None
        if heartbeat_time is not None and heartbeat_time.tzinfo is None:
            heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)
        timed_out = (
            heartbeat_time is None
            or (self._utc_now() - heartbeat_time).total_seconds()
            >= float(self.config["running_timeout_seconds"])
        )
        if not timed_out:
            return None

        target_status = "FAILED"
        reason = "interrupted: stale RUNNING retrain detected during recovery"
        if run.get("trigger") == RetrainTrigger.BOOTSTRAP_REVALIDATION.value:
            audit = self.audit_pair_model(run["symbol"])
            latest = self.storage.base_dir / f"latest_{_clean_pair(run['symbol'])}.pkl"
            source_path = Path(run.get("source_model_path") or "")
            source_hash = run.get("source_model_sha256")
            source_matches = bool(
                audit.get("bootstrap_revalidation") is True
                and source_hash
                and audit.get("source_model_sha256") == source_hash
                and source_path.resolve() == latest.resolve()
                and latest.is_file()
            )
            if source_matches:
                try:
                    self.storage.validate_artifact(latest)
                    source_matches = self.storage.checksum(latest) == source_hash
                except Exception:
                    source_matches = False
            if source_matches:
                target_status = "PENDING"
                reason = (
                    "interrupted: stale RUNNING bootstrap recovered for full "
                    "revalidation with unchanged source checksum"
                )
            else:
                audit_reason = audit.get("reason", "CHECKSUM_MISMATCH")
                reason = (
                    f"{audit_reason}: interrupted bootstrap source is no longer "
                    "eligible for retry"
                )

        transitioned = self.database.transition_interrupted_retrain_run(
            run["run_id"],
            expected_heartbeat=heartbeat,
            status=target_status,
            error=reason,
            transitioned_at=self._utc_now().isoformat(),
        )
        if transitioned is not None:
            logger.warning(
                "Recovered interrupted retrain %s as %s",
                run["run_id"],
                target_status,
            )
        return transitioned

    def execute_retrain(
        self,
        run_id: str,
        train_func: Callable[[str, str, dict], object],
        *,
        validator: Callable[[object], bool] | None = None,
    ) -> dict:
        """Train, validate and promote without exposing a partial latest model."""
        return self._execute_run(
            run_id,
            train_func,
            validator=validator,
            provenance_status="PROMOTED",
        )

    def promote_initial_model(
        self,
        model: object,
        *,
        pair: str,
        timeframe: str = "H1",
        dataset_provenance: dict,
        feature_names: list | None = None,
        metadata: dict | None = None,
        validator: Callable[[object], bool] | None = None,
    ) -> dict:
        """Publish the first symbol model with explicit non-retrain provenance."""
        symbol = _clean_pair(pair)
        tf = str(timeframe).upper().strip()
        if not tf:
            raise ValueError("initial training timeframe is required")
        if not isinstance(dataset_provenance, dict) or not dataset_provenance:
            raise ValueError("initial training requires dataset provenance")
        eligibility_error = self._initial_eligibility_error(metadata)
        if eligibility_error:
            raise ValueError(
                f"initial training lacks production eligibility: {eligibility_error}"
            )
        latest = self.storage.base_dir / f"latest_{symbol}.pkl"
        if latest.exists():
            raise RuntimeError(
                f"initial training cannot replace existing symbol model: {latest}"
            )
        evidence_payload = json.dumps(
            {
                "symbol": symbol,
                "timeframe": tf,
                "dataset_provenance": dataset_provenance,
                "promotion_type": RetrainTrigger.INITIAL_TRAINING.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_key = hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest()
        run_id = "initial_" + evidence_key[:24]
        timestamp = _now()
        run = self.database.create_retrain_run({
            "run_id": run_id,
            "evidence_key": evidence_key,
            "symbol": symbol,
            "timeframe": tf,
            "trigger": RetrainTrigger.INITIAL_TRAINING.value,
            "status": "PENDING",
            "source_model_path": None,
            "source_model_sha256": None,
            "dataset_provenance": dataset_provenance,
            "outcome_ids": [],
            "last_outcome_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        if run["status"] != "PENDING":
            return run
        training_result = {
            "model": model,
            "feature_names": feature_names,
            "metadata": {
                **(metadata or {}),
                "promotion_type": RetrainTrigger.INITIAL_TRAINING.value,
            },
        }
        return self._execute_run(
            run_id,
            lambda *_args: training_result,
            validator=validator,
            provenance_status="INITIAL_TRAINING",
        )

    @staticmethod
    def _initial_eligibility_error(metadata: dict | None) -> str:
        """Return why calibration, validation and WFV evidence is insufficient."""
        from .xgb_trainer import MIN_PRECISION_THRESHOLD, wfv_quality_passed

        evidence = (metadata or {}).get("eligibility")
        wfv = (metadata or {}).get("wfv")
        if not isinstance(evidence, dict) or not isinstance(wfv, dict):
            return "WFV_EVIDENCE_MISSING"
        if "calibration_passed" not in evidence:
            return "CALIBRATION_EVIDENCE_MISSING"
        if evidence.get("calibration_passed") is not True:
            return "CALIBRATION_GATE"
        if "validation_passed" not in evidence:
            return "VALIDATION_EVIDENCE_MISSING"
        if evidence.get("validation_passed") is not True:
            return "VALIDATION_GATE"
        try:
            validation_precision = float(evidence["validation_precision"])
        except (KeyError, TypeError, ValueError):
            return "VALIDATION_EVIDENCE_MISSING"
        if validation_precision < MIN_PRECISION_THRESHOLD:
            return "VALIDATION_GATE"
        if evidence.get("wfv_passed") is not True or not wfv_quality_passed(wfv):
            return "WFV_GATE"
        return ""

    def audit_pair_model(self, pair: str) -> dict:
        """Certify the current pair alias without mutating runtime state."""
        symbol = _clean_pair(pair)
        latest = self.storage.base_dir / f"latest_{symbol}.pkl"
        if not latest.is_file():
            return {"eligible": False, "reason": "MODEL_NOT_DEPLOYED"}
        try:
            bundle = self.storage.validate_artifact(latest)
            checksum = self.storage.checksum(latest)
        except Exception as exc:
            return {
                "eligible": False,
                "reason": "ARTIFACT_INVALID",
                "error_type": type(exc).__name__,
            }
        provenance = [
            row for row in self.database.get_model_provenance(symbol)
            if row.get("status") in {"INITIAL_TRAINING", "PROMOTED"}
        ]
        matches = [
            row for row in provenance if row.get("artifact_sha256") == checksum
        ]
        if not matches:
            return {
                "eligible": False,
                "reason": "CHECKSUM_MISMATCH" if provenance else "PROVENANCE_MISSING",
            }
        if len(matches) != 1:
            return {"eligible": False, "reason": "PROVENANCE_AMBIGUOUS"}
        matching = matches[0]
        if matching["status"] == "INITIAL_TRAINING":
            metadata = bundle.get("metadata", {}) if isinstance(bundle, dict) else {}
            reason = self._initial_eligibility_error(metadata)
            if reason:
                revalidatable = reason in {
                    "WFV_EVIDENCE_MISSING",
                    "CALIBRATION_EVIDENCE_MISSING",
                    "VALIDATION_EVIDENCE_MISSING",
                }
                result = {"eligible": False, "reason": reason}
                if revalidatable:
                    result.update({
                        "bootstrap_revalidation": True,
                        "source_model_path": str(latest),
                        "source_model_sha256": checksum,
                    })
                return result
        return {
            "eligible": True,
            "reason": "PRODUCTION_ELIGIBLE",
            "model_id": matching.get("model_id"),
        }

    def _execute_run(
        self,
        run_id: str,
        train_func: Callable[[str, str, dict], object],
        *,
        validator: Callable[[object], bool] | None,
        provenance_status: str,
    ) -> dict:
        run = self._get_run(run_id)
        if run["status"] != "PENDING":
            return run
        timestamp = _now()
        run = self.database.claim_retrain_run(run_id, _OWNER_TOKEN, timestamp)
        if run is None:
            current = self._get_run(run_id)
            return current
        outcome_ids = json.loads(run["outcome_ids"])
        dataset_provenance = json.loads(run["dataset_provenance"])
        artifact: Path | None = None
        latest: Path | None = None
        rollback: Path | None = None
        try:
            context = {
                "run_id": run_id,
                "outcome_ids": outcome_ids,
                "dataset_provenance": dataset_provenance,
                "source_model_path": run.get("source_model_path"),
                "source_model_sha256": run.get("source_model_sha256"),
            }
            trained = train_func(run["symbol"], run["timeframe"], context)
            heartbeat_at = _now()
            self.database.update_retrain_run(run_id, {
                "heartbeat_at": heartbeat_at,
                "updated_at": heartbeat_at,
            })
            if isinstance(trained, dict):
                if "model" not in trained:
                    raise ValueError("training result has no model")
                model = trained["model"]
                feature_names = trained.get("feature_names")
                training_metadata = trained.get("metadata") or {}
            else:
                model = trained
                feature_names = None
                training_metadata = {}
            if model is None:
                raise ValueError("training returned no model")
            artifact = self.storage.stage_model(
                model,
                name=f"ensemble_{run['symbol']}_{run['timeframe']}",
                version=run_id,
                feature_names=feature_names,
                metadata={**training_metadata, **context},
            )
            heartbeat_at = _now()
            self.database.update_retrain_run(run_id, {
                "heartbeat_at": heartbeat_at,
                "updated_at": heartbeat_at,
            })
            self.storage.validate_artifact(artifact, validator)
            artifact_hash = self.storage.checksum(artifact)
            validated_at = _now()
            self.database.update_retrain_run(run_id, {
                "status": "VALIDATED",
                "artifact_path": str(artifact),
                "artifact_sha256": artifact_hash,
                "validated_at": validated_at,
                "heartbeat_at": validated_at,
                "updated_at": validated_at,
            })
            latest = self.storage.base_dir / f"latest_{_clean_pair(run['symbol'])}.pkl"
            source_hash = run.get("source_model_sha256")
            if source_hash:
                source_path = Path(run.get("source_model_path") or "")
                if source_path.resolve() != latest.resolve():
                    raise ValueError("source model path does not identify the current alias")
                if not latest.is_file() or self.storage.checksum(latest) != source_hash:
                    raise ValueError("source model alias changed before promotion")
            if latest.exists():
                with tempfile.NamedTemporaryFile(
                    dir=self.storage.base_dir,
                    prefix=f".{latest.name}.{run_id}.rollback.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    rollback = Path(handle.name)
                shutil.copyfile(latest, rollback)
                with rollback.open("r+b") as handle:
                    os.fsync(handle.fileno())
            promoted = self.storage.promote_artifact(
                artifact,
                pair=run["symbol"],
                validator=validator,
                _authority=_PROMOTION_AUTHORITY,
            )
            promoted_at = _now()
            provenance = {
                "model_id": "model_" + artifact_hash[:32],
                "retrain_run_id": run_id,
                "symbol": run["symbol"],
                "timeframe": run["timeframe"],
                "artifact_path": str(artifact),
                "artifact_sha256": artifact_hash,
                "source_model_path": run.get("source_model_path"),
                "source_model_sha256": run.get("source_model_sha256"),
                "dataset_provenance": dataset_provenance,
                "outcome_ids": outcome_ids,
                "trained_at": run["updated_at"],
                "validated_at": validated_at,
                "promoted_at": promoted_at,
                "latest_path": str(promoted),
                "status": provenance_status,
            }
            promoted_run = self.database.finalize_model_promotion(run_id, provenance)
            if rollback is not None:
                completed_rollback = rollback
                rollback = None
                try:
                    completed_rollback.unlink(missing_ok=True)
                except OSError as exc:
                    # Recovery reports residual .tmp evidence without reverting
                    # a DB-certified promotion.
                    logger.warning(
                        "Could not remove promotion rollback evidence %s: %s",
                        completed_rollback,
                        exc,
                    )
            return promoted_run
        except Exception as exc:
            if latest is not None and rollback is not None and rollback.exists():
                os.replace(rollback, latest)
                rollback = None
            elif latest is not None and artifact is not None and latest.exists():
                if self.storage.checksum(latest) == self.storage.checksum(artifact):
                    latest.unlink()
            failed_at = _now()
            self.database.update_retrain_run(run_id, {
                "status": "FAILED",
                "error": f"{type(exc).__name__}: {exc}",
                "updated_at": failed_at,
            })
            return self._get_run(run_id)
        finally:
            if rollback is not None:
                rollback.unlink(missing_ok=True)

    def reconcile(self) -> dict:
        """Detect crash states and DB/filesystem provenance mismatches."""
        issues: list[dict] = []
        recovered: list[str] = []
        provenance_rows = self.database.get_model_provenance()
        provenance_by_run = {
            row["retrain_run_id"]: row for row in provenance_rows
        }
        active_run_by_symbol: dict[str, str] = {}
        for row in provenance_rows:
            active_run_by_symbol.setdefault(row["symbol"], row["retrain_run_id"])
        for run in self.database.get_retrain_runs(limit=100000):
            if run["status"] == "RUNNING":
                transitioned = self._recover_interrupted_running(run)
                if transitioned is not None:
                    recovered.append(run["run_id"])
                continue
            artifact = Path(run["artifact_path"]) if run.get("artifact_path") else None
            latest = Path(run["latest_path"]) if run.get("latest_path") else (
                self.storage.base_dir / f"latest_{_clean_pair(run['symbol'])}.pkl"
            )
            if run["status"] == "VALIDATED":
                issues.append({
                    "run_id": run["run_id"],
                    "symbol": run["symbol"],
                    "code": "promotion_incomplete",
                    "artifact_exists": bool(artifact and artifact.is_file()),
                })
            elif run["status"] == "PROMOTED":
                provenance = provenance_by_run.get(run["run_id"])
                if provenance is None:
                    issues.append({
                        "run_id": run["run_id"], "symbol": run["symbol"],
                        "code": "model_provenance_missing",
                    })
                elif provenance["artifact_sha256"] != run["artifact_sha256"]:
                    issues.append({
                        "run_id": run["run_id"], "symbol": run["symbol"],
                        "code": "model_provenance_mismatch",
                    })
                elif not artifact or not artifact.is_file():
                    issues.append({
                        "run_id": run["run_id"], "symbol": run["symbol"],
                        "code": "artifact_missing",
                    })
                elif (
                    active_run_by_symbol.get(run["symbol"]) == run["run_id"]
                    and not latest.is_file()
                ):
                    issues.append({
                        "run_id": run["run_id"], "symbol": run["symbol"],
                        "code": "latest_missing",
                    })
                elif (
                    self.storage.checksum(artifact) != run["artifact_sha256"]
                    or (
                        active_run_by_symbol.get(run["symbol"]) == run["run_id"]
                        and self.storage.checksum(latest) != run["artifact_sha256"]
                    )
                ):
                    issues.append({
                        "run_id": run["run_id"], "symbol": run["symbol"],
                        "code": "artifact_mismatch",
                    })
        certified_hashes = {
            (row["symbol"], row["artifact_sha256"])
            for row in provenance_rows
            if row["status"] in {"PROMOTED", "INITIAL_TRAINING"}
        }
        for latest in self.storage.base_dir.glob("latest_*.pkl"):
            symbol = latest.stem.removeprefix("latest_")
            latest_hash = self.storage.checksum(latest)
            if (symbol, latest_hash) not in certified_hashes:
                issues.append({
                    "run_id": None,
                    "symbol": symbol,
                    "code": "latest_without_provenance",
                })
                continue
            provenance = next(
                (
                    row for row in provenance_rows
                    if row["symbol"] == symbol
                    and row["artifact_sha256"] == latest_hash
                ),
                None,
            )
            if provenance and provenance["status"] == "INITIAL_TRAINING":
                audit = self.audit_pair_model(symbol)
                if not audit["eligible"]:
                    issues.append({
                        "run_id": provenance["retrain_run_id"],
                        "symbol": symbol,
                        "code": "initial_training_not_production_eligible",
                        "reason": audit["reason"],
                    })
        for temporary in self.storage.base_dir.glob(".*.tmp"):
            issues.append({
                "run_id": None,
                "symbol": None,
                "code": "orphan_temporary_artifact",
                "path": str(temporary),
            })
        return {"healthy": not issues, "issues": issues, "recovered": recovered}

    def trigger_retrain(
        self,
        pair: str,
        timeframe: str = "H1",
        trigger: RetrainTrigger = RetrainTrigger.MANUAL,
        retrain_func: Callable | None = None,
        old_model: str = "",
        old_win_rate: float = 0.0,
        old_accuracy: float = 0.0,
    ) -> RetrainRecord:
        """Persistently reject the legacy path that cannot provide provenance."""
        started = time.monotonic()
        timestamp = _now()
        evidence_key = hashlib.sha256(
            f"legacy|{pair.upper()}|{timeframe.upper()}|{trigger.value}|{timestamp}".encode()
        ).hexdigest()
        run_id = "retrain_" + evidence_key[:24]
        record = RetrainRecord(
            pair=pair,
            timeframe=timeframe,
            trigger=trigger.value,
            old_model=old_model,
            old_win_rate=old_win_rate,
            old_accuracy=old_accuracy,
            timestamp=timestamp,
            run_id=run_id,
        )
        record.error = (
            "Legacy trigger lacks outcome/dataset provenance; create a pending run "
            "and use execute_retrain()"
        )
        self.database.create_retrain_run({
            "run_id": run_id,
            "evidence_key": evidence_key,
            "symbol": pair.upper(),
            "timeframe": timeframe.upper(),
            "trigger": trigger.value,
            "status": "PENDING",
            "source_model_path": old_model or None,
            "source_model_sha256": None,
            "dataset_provenance": {"legacy_trigger": True, "complete": False},
            "outcome_ids": [],
            "last_outcome_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        self.database.update_retrain_run(run_id, {
            "status": "FAILED",
            "error": record.error,
            "updated_at": _now(),
        })
        record.duration_sec = time.monotonic() - started
        return record

    def manual_retrain(
        self, pair: str, timeframe: str = "H1", retrain_func: Callable | None = None
    ) -> RetrainRecord:
        return self.trigger_retrain(pair, timeframe, RetrainTrigger.MANUAL, retrain_func)

    def get_history(self, pair: str = "", limit: int = 20) -> list[dict]:
        return self.database.get_retrain_runs(pair or None, limit=limit)


def _clean_pair(pair: str) -> str:
    clean = "".join(character for character in str(pair).upper() if character.isalnum())
    if not clean:
        raise ValueError("model pair is empty or invalid")
    return clean


def cmd_retrain_check(args: str = "") -> str:
    parts = args.strip().split()
    if not parts:
        return "Uso: retrain_check <pair> [current_win_rate] [model_name]"
    pair = parts[0].upper()
    win_rate = float(parts[1]) if len(parts) > 1 else None
    model_name = parts[2] if len(parts) > 2 else ""
    decision = RetrainManager().check_retrain_needed(
        pair=pair, current_win_rate=win_rate, model_name=model_name
    )
    return (
        f"Reentrenamiento necesario — {decision.reason}"
        if decision.needed
        else f"No necesita reentrenamiento — {pair}"
    )


def cmd_retrain_history(args: str = "") -> str:
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    limit = int(parts[1]) if len(parts) > 1 else 20
    history = RetrainManager().get_history(pair, limit)
    if not history:
        return "Sin historial de reentrenamientos"
    return "\n".join(
        [f"Historial de Reentrenamientos ({len(history)})"]
        + [f"  {row['status']} {row['symbol']} {row['timeframe']} {row['run_id']}" for row in history]
    )
