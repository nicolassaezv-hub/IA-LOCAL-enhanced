"""Fail-closed candidate qualification and activation orchestration."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from forex.data.data_router import DataRouter
from forex.data.rolling_dataset import ROLLING_WINDOW, RollingDataset
from forex.data.indicator_delta import recalculate_tail_indicators
from forex.data.symbol_catalog import (
    CATALOG_VERSION,
    SUPPORTED_TIMEFRAMES,
    get_symbol_spec,
    route_for_provider,
)
from infra.db.database import (
    DatabaseAdapter,
    PersistenceConflictError,
)
from runtime_paths import (
    forex_dataset_path,
    forex_model_root,
    symbol_qualification_path,
    symbol_qualification_root,
)
from scripts.validate_symbol_universe import (
    PROBE_BARS,
    _match_provider_frame,
    _normalize_probe_frame,
    sha256_file,
    validate_cross_timeframes,
    validate_dataset_frame,
    write_json_report,
)


DEFAULT_QUALIFICATION_MAX_AGE_SECONDS = 24 * 60 * 60


def _utc_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise PersistenceConflictError("Qualification timestamp is invalid")
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _qualification_max_age_seconds() -> int | None:
    raw = os.environ.get("ASTRA_QUALIFICATION_MAX_AGE_SECONDS")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise PersistenceConflictError(
            "ASTRA_QUALIFICATION_MAX_AGE_SECONDS must be an integer"
        ) from exc
    if value <= 0:
        raise PersistenceConflictError(
            "ASTRA_QUALIFICATION_MAX_AGE_SECONDS must be positive"
        )
    return value


def register_candidate(database: DatabaseAdapter, symbol: str) -> dict:
    spec = get_symbol_spec(symbol)
    return database.register_candidate(
        spec.symbol_code,
        spec.display_name,
        spec.asset_class,
        spec.pip_value,
    )


def _evidence_path(symbol: str, project_root: Path | str) -> Path:
    return symbol_qualification_root(project_root) / symbol / "evidence.json"


def _timeframe_diagnostics(
    *,
    route: Any,
    source_fetched_at: str | None,
    acquisition_metadata: dict | None,
    stored: dict | None,
    physical_frame: pd.DataFrame | None,
    validation: dict | None,
) -> dict[str, Any]:
    """Preserve diagnostics already produced before a fail-closed rejection."""
    diagnostics: dict[str, Any] = {
        "source_fetched_at": source_fetched_at,
        "acquisition_metadata": acquisition_metadata,
        "validation": validation,
        "warnings": list((validation or {}).get("warnings", [])),
        "errors": list((validation or {}).get("errors", [])),
    }
    if route is not None:
        route_evidence = {
            "provider": route.provider,
            "external_ticker": route.external_ticker,
            "provider_class": route.provider_class,
        }
        diagnostics["route"] = route_evidence
        diagnostics.update(route_evidence)
    if acquisition_metadata is not None:
        for field in (
            "requested_bars",
            "raw_closed_rows",
            "invalid_rows_dropped",
            "valid_rows_before_tail",
            "returned_rows",
            "dropped_rows",
            "resample_provenance",
        ):
            if field in acquisition_metadata:
                diagnostics[field] = acquisition_metadata[field]
        diagnostics["drop_reasons"] = sorted({
            str(item.get("reason"))
            for item in acquisition_metadata.get("dropped_rows", [])
            if isinstance(item, dict) and item.get("reason")
        })
    if stored is not None and stored.get("path"):
        resolved_path = Path(stored["path"]).resolve()
        diagnostics["csv_path"] = str(resolved_path)
        diagnostics["candidate_path"] = str(resolved_path)
        if resolved_path.is_file():
            candidate_sha256 = sha256_file(resolved_path)
            diagnostics["csv_sha256"] = candidate_sha256
            diagnostics["candidate_sha256"] = candidate_sha256
    if physical_frame is not None:
        diagnostics["physical_rows"] = int(len(physical_frame))
    return diagnostics


def qualify_candidate(
    database: DatabaseAdapter,
    symbol: str,
    *,
    project_root: Path | str,
    router_factory: Callable[[str, str], DataRouter] = DataRouter,
    now: Any = None,
) -> dict:
    """Fetch and validate a candidate without touching production paths/registry."""
    spec = get_symbol_spec(symbol)
    row = database.get_symbol(spec.symbol_code)
    if row is None or row.get("status") not in {"candidate", "qualified"}:
        raise PersistenceConflictError(
            f"{spec.symbol_code} must be candidate or qualified before qualification"
        )

    qualification_time = _utc_timestamp(
        pd.Timestamp.now(tz="UTC") if now is None else now
    )
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "catalog_version": CATALOG_VERSION,
        "symbol": spec.symbol_code,
        "asset_class": spec.asset_class,
        "qualification_timestamp": qualification_time.isoformat(),
        "result": "PASS",
        "timeframes": {},
        "cross_timeframe": None,
        "errors": [],
    }
    frames: dict[str, pd.DataFrame] = {}

    for timeframe in SUPPORTED_TIMEFRAMES:
        router = router_factory(spec.symbol_code, timeframe)
        timeframe_evidence: dict[str, Any] = {"timeframe": timeframe}
        acquisition_metadata = None
        stored = None
        frame = None
        stage = None
        route = None
        source_fetched_at = None
        try:
            fetched = router.fetch(bars=PROBE_BARS, raise_on_failure=True)
            source_fetched_at = qualification_time.isoformat()
            acquisition_metadata = getattr(
                router, "last_acquisition_metadata", None
            )
            route = router.route_used
            normalized = _normalize_probe_frame(
                fetched, spec.symbol_code, timeframe
            )
            candidate_path = symbol_qualification_path(
                spec.symbol_code,
                timeframe,
                project_root=project_root,
            )
            dataset = RollingDataset(
                spec.symbol_code,
                timeframe,
                max_rows=ROLLING_WINDOW,
                csv_path=candidate_path,
            )
            stored = dataset.apply(
                normalized,
                include_existing=False,
                now=qualification_time,
            )
            frame = pd.read_csv(stored["path"], encoding="utf-8")
            stage, validated = validate_dataset_frame(
                frame,
                spec.symbol_code,
                timeframe,
                now=qualification_time,
                acquisition_metadata=acquisition_metadata,
                provider=route.provider if route is not None else None,
            )
            if route is None:
                raise PersistenceConflictError(
                    f"{timeframe}: provider route used is unknown"
                )
            if stage["status"] == "FAIL" or stage["blocking"]:
                raise PersistenceConflictError(
                    f"{timeframe}: candidate contract failed: "
                    f"{stage['errors'] or stage['warnings']}"
                )
            if validated is None or len(validated) != ROLLING_WINDOW:
                raise PersistenceConflictError(
                    f"{timeframe}: candidate is not exactly {ROLLING_WINDOW} rows"
                )
            frames[timeframe] = validated
            timeframe_evidence.update(_timeframe_diagnostics(
                route=route,
                source_fetched_at=source_fetched_at,
                acquisition_metadata=acquisition_metadata,
                stored=stored,
                physical_frame=frame,
                validation=stage,
            ))
            timeframe_evidence.update({
                "result": "PASS",
                "row_count": int(len(validated)),
                "closed_count": int(stage["details"]["closed_rows"]),
                "first_timestamp": str(validated["timestamp"].iloc[0]),
                "last_timestamp": str(validated["timestamp"].iloc[-1]),
                "attempt_errors": list(router.attempt_errors),
            })
        except Exception as exc:
            if route is None:
                route = getattr(router, "route_used", None)
            timeframe_evidence.update(_timeframe_diagnostics(
                route=route,
                source_fetched_at=source_fetched_at,
                acquisition_metadata=acquisition_metadata,
                stored=stored,
                physical_frame=frame,
                validation=stage,
            ))
            timeframe_evidence.update({
                "result": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
                "attempt_errors": list(getattr(router, "attempt_errors", ())),
            })
            evidence["result"] = "FAIL"
            evidence["errors"].append(
                f"{timeframe}: {type(exc).__name__}: {exc}"
            )
        evidence["timeframes"][timeframe] = timeframe_evidence

    cross = validate_cross_timeframes(frames)
    evidence["cross_timeframe"] = cross
    if cross["status"] == "FAIL" or cross["blocking"]:
        evidence["result"] = "FAIL"
        evidence["errors"].extend(cross["errors"] or cross["warnings"])

    evidence_path = Path(
        write_json_report(
            evidence,
            _evidence_path(spec.symbol_code, project_root),
        )
    )
    evidence_record = {
        **evidence,
        "evidence_path": str(evidence_path),
        "evidence_sha256": sha256_file(evidence_path),
    }
    if evidence["result"] == "PASS":
        evidence_record["symbol_record"] = database.mark_qualified(
            spec.symbol_code, evidence_record
        )
    return evidence_record


def load_current_evidence(
    database: DatabaseAdapter,
    symbol: str,
    *,
    now: Any = None,
    max_age_seconds: int | None = None,
) -> tuple[dict, dict, str]:
    spec = get_symbol_spec(symbol)
    row = database.get_symbol(spec.symbol_code)
    if row is None or row.get("status") not in {"qualified", "active"}:
        raise PersistenceConflictError(
            f"{spec.symbol_code} must be qualified before activation"
        )
    path_value = row.get("qualification_evidence_path")
    expected_sha256 = row.get("qualification_sha256")
    if not path_value or not expected_sha256:
        raise PersistenceConflictError("Qualified symbol has no durable evidence")
    path = Path(path_value).resolve()
    if not path.is_file() or sha256_file(path) != expected_sha256:
        raise PersistenceConflictError("Qualification evidence file/hash mismatch")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if (
        evidence.get("result") != "PASS"
        or evidence.get("symbol") != spec.symbol_code
        or evidence.get("catalog_version") != CATALOG_VERSION
        or row.get("qualification_catalog_version") != CATALOG_VERSION
    ):
        raise PersistenceConflictError("Qualification evidence is not current PASS evidence")
    cutoff_now = _utc_timestamp(pd.Timestamp.now(tz="UTC") if now is None else now)
    qualified_at = _utc_timestamp(evidence.get("qualification_timestamp"))
    maximum_age = (
        _qualification_max_age_seconds() if max_age_seconds is None
        else int(max_age_seconds)
    )
    age_seconds = (cutoff_now - qualified_at).total_seconds()
    if age_seconds < 0:
        raise PersistenceConflictError(
            f"Qualification evidence is from the future: age_seconds={age_seconds:.0f}"
        )
    if maximum_age is not None and age_seconds > maximum_age:
        raise PersistenceConflictError(
            f"Qualification evidence is stale: age_seconds={age_seconds:.0f}"
        )
    return row, evidence, expected_sha256


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with source.open("rb") as input_file, tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            for block in iter(lambda: input_file.read(1024 * 1024), b""):
                output_file.write(block)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _activate_qualified_symbol_impl(
    database: DatabaseAdapter,
    symbol: str,
    *,
    project_root: Path | str,
    now: Any = None,
    max_age_seconds: int | None = None,
    router_factory: Callable[[str, str], DataRouter] = DataRouter,
    model_manager=None,
    _issue_authorization,
) -> dict:
    """Activate only current canonical data with an eligible production model."""
    spec = get_symbol_spec(symbol)
    existing = database.get_symbol(spec.symbol_code)
    if existing is not None and existing.get("status") == "active":
        if existing.get("activation_origin") == "legacy":
            return {
                **existing,
                "activation_result": "LEGACY_ACTIVE_GRANDFATHERED",
            }
        return existing
    _row, evidence, evidence_sha256 = load_current_evidence(
        database,
        spec.symbol_code,
        now=now,
        max_age_seconds=max_age_seconds,
    )

    from forex.prediction.dataset_builder import require_ml_config

    require_ml_config(spec.symbol_code)
    if model_manager is None:
        from forex.prediction.model_storage import ModelStorage
        from forex.prediction.retrain_manager import RetrainManager

        model_manager = RetrainManager(
            database=database,
            storage=ModelStorage(forex_model_root(project_root)),
        )
    model_audit = model_manager.audit_pair_model(spec.symbol_code)
    if model_audit.get("eligible") is not True:
        raise PersistenceConflictError(
            str(model_audit.get("reason") or "MODEL_NOT_PRODUCTION_ELIGIBLE")
        )

    cutoff_now = _utc_timestamp(pd.Timestamp.now(tz="UTC") if now is None else now)
    canonical_frames: dict[str, pd.DataFrame] = {}
    provider_frames: dict[str, pd.DataFrame] = {}
    freshness: dict[str, dict[str, Any]] = {}
    for timeframe in SUPPORTED_TIMEFRAMES:
        entries = database.get_dataset_registry(spec.symbol_code, timeframe)
        if len(entries) != 1:
            raise PersistenceConflictError(
                f"{timeframe}: canonical registry row is missing"
            )
        entry = entries[0]
        target = forex_dataset_path(
            spec.symbol_code, timeframe, project_root=project_root
        ).resolve()
        if Path(entry.get("blob_path") or "").resolve() != target or not target.is_file():
            raise PersistenceConflictError(
                f"{timeframe}: canonical dataset path is missing or differs"
            )
        if (
            entry.get("status") != "ready"
            or entry.get("candle_count") != ROLLING_WINDOW
            or entry.get("rolling_window_size") != ROLLING_WINDOW
            or entry.get("legacy_provenance_pending") not in (0, False)
            or any(
                not entry.get(field)
                for field in (
                    "provider_used", "external_ticker", "provider_class",
                    "source_fetched_at", "source_sha256",
                )
            )
            or entry.get("source_sha256") != sha256_file(target)
        ):
            raise PersistenceConflictError(
                f"{timeframe}: canonical registry contract is not READY"
            )
        registered_route = route_for_provider(
            spec.symbol_code, entry["provider_used"]
        )
        if (
            registered_route is None
            or registered_route.external_ticker != entry["external_ticker"]
            or registered_route.provider_class != entry["provider_class"]
        ):
            raise PersistenceConflictError(
                f"{timeframe}: canonical registry provider route is invalid"
            )
        local_stage, local = validate_dataset_frame(
            pd.read_csv(target, encoding="utf-8"),
            spec.symbol_code,
            timeframe,
            now=cutoff_now,
            acquisition_metadata=entry.get("acquisition_metadata"),
            provider=entry.get("provider"),
        )
        if local_stage["status"] == "FAIL" or local_stage["blocking"] or local is None:
            raise PersistenceConflictError(
                f"{timeframe}: canonical rolling2000 validation failed"
            )

        router = router_factory(spec.symbol_code, timeframe)
        try:
            fetched = router.fetch(bars=PROBE_BARS, raise_on_failure=True)
            provider = _normalize_probe_frame(
                fetched,
                spec.symbol_code,
                timeframe,
                now=cutoff_now,
            )
            provider = provider.tail(ROLLING_WINDOW).reset_index(drop=True)
            provider = recalculate_tail_indicators(provider, k=len(provider))
            provider_stage, provider_validated = validate_dataset_frame(
                provider,
                spec.symbol_code,
                timeframe,
                now=cutoff_now,
                acquisition_metadata=getattr(
                    router, "last_acquisition_metadata", None
                ),
                provider=getattr(router, "source_used", None),
            )
        except Exception as exc:
            raise PersistenceConflictError(
                f"PROVIDER_FRESHNESS_UNCONFIRMED: {timeframe}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if (
            router.route_used is None
            or provider_stage["status"] == "FAIL"
            or provider_stage["blocking"]
            or provider_validated is None
            or len(provider_validated) != ROLLING_WINDOW
        ):
            raise PersistenceConflictError(
                f"PROVIDER_FRESHNESS_UNCONFIRMED: {timeframe}"
            )
        comparison = _match_provider_frame(local, provider_validated)
        local_latest = pd.Timestamp(local["timestamp"].iloc[-1])
        provider_latest = pd.Timestamp(provider_validated["timestamp"].iloc[-1])
        if local_latest != provider_latest or comparison["status"] != "MATCH":
            raise PersistenceConflictError(
                f"DATASET_NOT_PROVIDER_CURRENT: {timeframe}: "
                f"local={local_latest} provider={provider_latest} "
                f"overlap={comparison['status']}"
            )
        canonical_frames[timeframe] = local
        provider_frames[timeframe] = provider_validated
        freshness[timeframe] = {
            "provider": router.route_used.provider,
            "external_ticker": router.route_used.external_ticker,
            "latest_closed": str(provider_latest),
            "source_sha256": entry["source_sha256"],
        }

    for label, frames in (
        ("canonical", canonical_frames),
        ("provider", provider_frames),
    ):
        cross = validate_cross_timeframes(frames)
        if cross["status"] == "FAIL" or cross["blocking"]:
            raise PersistenceConflictError(
                f"Cross-timeframe {label} validation failed"
            )

    freshness_sha256 = __import__("hashlib").sha256(
        json.dumps(freshness, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    authorization = _issue_authorization(
        spec.symbol_code,
        evidence_sha256=evidence_sha256,
        model_reason=str(model_audit.get("reason")),
        freshness_sha256=freshness_sha256,
    )
    return database._persist_authorized_activation(authorization)


def _build_activation_contract():
    """Keep issuance private while exposing validation to the persistence layer."""
    authority = object()

    class _CompletedLifecycleAuthorization:
        __slots__ = (
            "symbol",
            "evidence_sha256",
            "model_reason",
            "freshness_sha256",
            "_authority",
        )

        def __init__(self, *_args, **_kwargs):
            raise TypeError("Lifecycle authorizations cannot be constructed directly")

    def issue(
        symbol: str,
        *,
        evidence_sha256: str,
        model_reason: str,
        freshness_sha256: str,
    ):
        if (
            model_reason != "PRODUCTION_ELIGIBLE"
            or not evidence_sha256
            or not freshness_sha256
        ):
            raise PersistenceConflictError("Activation authorization is incomplete")
        authorization = object.__new__(_CompletedLifecycleAuthorization)
        authorization.symbol = str(symbol).upper()
        authorization.evidence_sha256 = evidence_sha256
        authorization.model_reason = model_reason
        authorization.freshness_sha256 = freshness_sha256
        authorization._authority = authority
        return authorization

    def validate(value: object) -> bool:
        return (
            isinstance(value, _CompletedLifecycleAuthorization)
            and getattr(value, "_authority", None) is authority
            and getattr(value, "model_reason", None) == "PRODUCTION_ELIGIBLE"
            and bool(getattr(value, "evidence_sha256", None))
            and bool(getattr(value, "freshness_sha256", None))
        )

    def activate_qualified_symbol(
        database: DatabaseAdapter,
        symbol: str,
        *,
        project_root: Path | str,
        now: Any = None,
        max_age_seconds: int | None = None,
        router_factory: Callable[[str, str], DataRouter] = DataRouter,
        model_manager=None,
    ) -> dict:
        return _activate_qualified_symbol_impl(
            database,
            symbol,
            project_root=project_root,
            now=now,
            max_age_seconds=max_age_seconds,
            router_factory=router_factory,
            model_manager=model_manager,
            _issue_authorization=issue,
        )

    return activate_qualified_symbol, validate


activate_qualified_symbol, is_activation_authorization = _build_activation_contract()


def migrate_legacy_active_to_candidate(
    database: DatabaseAdapter,
    symbol: str,
    *,
    expected_state: dict | None = None,
) -> dict:
    """Expose the one-way legacy retirement transition without qualification."""
    return database.migrate_legacy_active_to_candidate(
        get_symbol_spec(symbol).symbol_code,
        expected_state=expected_state,
    )


def disable_symbol(
    database: DatabaseAdapter,
    symbol: str,
    *,
    expected_state: dict | None = None,
) -> dict:
    return database.disable_symbol(
        get_symbol_spec(symbol).symbol_code,
        expected_state=expected_state,
    )


__all__ = [
    "DEFAULT_QUALIFICATION_MAX_AGE_SECONDS",
    "activate_qualified_symbol",
    "disable_symbol",
    "load_current_evidence",
    "migrate_legacy_active_to_candidate",
    "qualify_candidate",
    "register_candidate",
]
