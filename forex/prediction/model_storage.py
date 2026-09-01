"""Atomic, versioned storage for Forex model bundles."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import joblib
from filelock import FileLock

from runtime_paths import forex_model_root

# Pair-specific aliases are executable production state.  Only the canonical
# promotion coordinator imports this capability; public storage helpers may
# stage artifacts or maintain the explicit no-pair legacy alias, but cannot
# publish a symbol model by themselves.
_PROMOTION_AUTHORITY = object()


class ModelStorage:
    """Store immutable artifacts before atomically updating a latest alias."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = (
            forex_model_root()
            if base_dir is None
            else Path(base_dir).resolve()
        )
        self.latest_path = self.base_dir / "latest_model.pkl"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def checksum(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def validate_artifact(
        path: str | Path,
        validator: Callable[[object], bool] | None = None,
    ) -> object:
        artifact = Path(path)
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise ValueError(f"model artifact is missing or empty: {artifact}")
        bundle = joblib.load(artifact)
        if isinstance(bundle, dict) and "model" not in bundle:
            raise ValueError(f"model bundle has no model payload: {artifact}")
        model = bundle.get("model") if isinstance(bundle, dict) else bundle
        if model is None:
            raise ValueError(f"model payload is empty: {artifact}")
        if isinstance(bundle, dict):
            metadata = bundle.get("metadata") or {}
            model_contract = getattr(model, "model_contract", None)
            if (
                model_contract == "h1_direction_rf_v1"
                or metadata.get("model_contract") == "h1_direction_rf_v1"
            ):
                from .h1_directional import validate_h1_artifact_bundle

                validate_h1_artifact_bundle(bundle)
        if validator is not None and validator(model) is not True:
            raise ValueError(f"model validation rejected artifact: {artifact}")
        return bundle

    def stage_model(
        self,
        model: object,
        *,
        name: str,
        version: str,
        feature_names: list | None = None,
        metadata: dict | None = None,
    ) -> Path:
        filename = f"{_clean_name(name)}_{_clean_name(version)}.pkl"
        target = self.base_dir / filename
        if target.exists():
            existing = self.validate_artifact(target)
            existing_metadata = existing.get("metadata", {}) if isinstance(existing, dict) else {}
            if (
                metadata
                and metadata.get("run_id")
                and existing_metadata.get("run_id") == metadata.get("run_id")
            ):
                return target
            raise FileExistsError(f"immutable model artifact already exists: {target}")
        bundle = {
            "model": model,
            "feature_names": feature_names,
            "metadata": metadata or {},
        }
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.base_dir,
                prefix=f".{filename}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
            joblib.dump(bundle, temporary)
            with temporary.open("r+b") as handle:
                os.fsync(handle.fileno())
            self.validate_artifact(temporary)
            os.replace(temporary, target)
            temporary = None
            return target
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def promote_artifact(
        self,
        artifact_path: str | Path,
        *,
        pair: str,
        validator: Callable[[object], bool] | None = None,
        expected_latest_path: str | Path | None = None,
        expected_latest_sha256: str | None = None,
        require_latest_absent: bool = False,
        rollback_path: str | Path | None = None,
        _authority: object | None = None,
    ) -> Path:
        if _authority is not _PROMOTION_AUTHORITY:
            raise RuntimeError(
                "pair-specific promotion requires RetrainManager provenance"
            )
        source = Path(artifact_path)
        self.validate_artifact(source, validator)
        latest = self.base_dir / f"latest_{_clean_pair(pair)}.pkl"
        if expected_latest_sha256 and require_latest_absent:
            raise ValueError("latest alias cannot be both expected and absent")
        if expected_latest_path is not None:
            expected = Path(expected_latest_path).resolve()
            if expected != latest.resolve():
                raise ValueError("SOURCE_ALIAS_CONFLICT: source path is not current alias")
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.base_dir,
                prefix=f".{latest.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
            shutil.copyfile(source, temporary)
            with temporary.open("r+b") as handle:
                os.fsync(handle.fileno())
            self.validate_artifact(temporary, validator)
            if self.checksum(temporary) != self.checksum(source):
                raise ValueError("promoted model copy does not match staged artifact")
            lock = FileLock(str(latest.with_suffix(latest.suffix + ".promotion.lock")))
            with lock:
                if require_latest_absent and latest.exists():
                    raise ValueError(
                        "SOURCE_ALIAS_CONFLICT: initial alias appeared before promotion"
                    )
                if expected_latest_sha256:
                    if (
                        not latest.is_file()
                        or self.checksum(latest) != expected_latest_sha256
                    ):
                        raise ValueError(
                            "SOURCE_ALIAS_CONFLICT: alias changed before promotion"
                        )
                if rollback_path is not None:
                    rollback = Path(rollback_path)
                    shutil.copyfile(latest, rollback)
                    with rollback.open("r+b") as handle:
                        os.fsync(handle.fileno())
                    if self.checksum(rollback) != expected_latest_sha256:
                        raise ValueError(
                            "SOURCE_ALIAS_CONFLICT: rollback copy does not match source"
                        )
                os.replace(temporary, latest)
                temporary = None
            return latest
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def rollback_promotion(
        self,
        rollback_path: str | Path | None,
        *,
        pair: str,
        promoted_sha256: str,
        _authority: object | None = None,
    ) -> bool:
        """Restore/remove only the alias still owned by the failed promotion."""
        if _authority is not _PROMOTION_AUTHORITY:
            raise RuntimeError("alias rollback requires RetrainManager authority")
        latest = self.base_dir / f"latest_{_clean_pair(pair)}.pkl"
        rollback = Path(rollback_path) if rollback_path is not None else None
        lock = FileLock(str(latest.with_suffix(latest.suffix + ".promotion.lock")))
        with lock:
            if not latest.is_file() or self.checksum(latest) != promoted_sha256:
                return False
            if rollback is None:
                latest.unlink()
            else:
                os.replace(rollback, latest)
            return True

    def save_model(
        self,
        model,
        name: str = "ensemble_forex",
        pair: str | None = None,
        version: str | None = None,
        feature_names: list | None = None,
    ) -> str:
        if pair is not None:
            raise RuntimeError(
                "save_model(pair=...) cannot publish production aliases; "
                "use RetrainManager initial-training or retrain promotion"
            )
        version = version or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        artifact = self.stage_model(
            model,
            name=name,
            version=version,
            feature_names=feature_names,
        )
        self._promote_generic(artifact)
        return str(artifact)

    def _promote_generic(self, artifact: Path) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.base_dir,
                prefix=f".{self.latest_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
            shutil.copyfile(artifact, temporary)
            with temporary.open("r+b") as handle:
                os.fsync(handle.fileno())
            self.validate_artifact(temporary)
            os.replace(temporary, self.latest_path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load_model(self, pair: str | None = None):
        if pair is None:
            return self.load_latest()
        clean = _clean_pair(pair)
        path = self.base_dir / f"latest_{clean}.pkl"
        if not path.is_file():
            raise FileNotFoundError(f"No hay modelo entrenado para {clean}: {path}")
        return self._unwrap(joblib.load(path))

    def load_model_with_features(self, pair: str | None = None):
        path = (
            self.base_dir / f"latest_{_clean_pair(pair)}.pkl"
            if pair is not None
            else self.latest_path
        )
        if not path.is_file():
            if pair is not None:
                raise FileNotFoundError(
                    f"No hay modelo entrenado para {_clean_pair(pair)}: {path}"
                )
            raise FileNotFoundError("No hay modelo entrenado.")
        bundle = joblib.load(path)
        if isinstance(bundle, dict):
            return bundle["model"], bundle.get("feature_names")
        return bundle, None

    @staticmethod
    def _unwrap(bundle):
        return bundle["model"] if isinstance(bundle, dict) and "model" in bundle else bundle

    def load_latest(self):
        if not self.latest_path.exists():
            raise FileNotFoundError(
                "No hay modelo entrenado. Ejecuta primero: pipeline.train('archivo.csv')"
            )
        return self._unwrap(joblib.load(self.latest_path))

    def load_version(self, filename: str):
        path = self.base_dir / Path(filename).name
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {filename}")
        return self._unwrap(joblib.load(path))

    def list_models(self) -> list[str]:
        return sorted(path.name for path in self.base_dir.glob("*.pkl"))

    def latest_exists(self, pair: str | None = None) -> bool:
        if pair is None:
            return self.latest_path.is_file()
        return (self.base_dir / f"latest_{_clean_pair(pair)}.pkl").is_file()


def _clean_pair(pair: str) -> str:
    clean = "".join(character for character in str(pair).upper() if character.isalnum())
    if not clean:
        raise ValueError("model pair is empty or invalid")
    return clean


def _clean_name(value: str) -> str:
    clean = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in str(value)
    ).strip("_")
    if not clean:
        raise ValueError("model artifact name is empty or invalid")
    return clean
