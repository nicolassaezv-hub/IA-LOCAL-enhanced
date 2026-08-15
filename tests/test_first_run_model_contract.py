"""Regression coverage for canonical model paths and executable H1 first-run."""
from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

import runtime_paths
from deployment.first_run_validator import run_first_deployment_check
from deployment.pipeline_report import PipelineReport, run_pipeline_report
from deployment.production_readiness import _find_model_path
from forex.prediction.integrated_pipeline import _autoresolve_mtf
from forex.prediction.model_storage import ModelStorage


def _patch_data_stages(monkeypatch, frame: pd.DataFrame) -> None:
    from forex.prediction import csv_adapter, dataset_builder, feature_engineering
    from forex.prediction import roadmap_v_integration

    monkeypatch.setattr(csv_adapter, "adapt_csv", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(feature_engineering, "build_features", lambda value: value)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return pd.DataFrame({"close": range(100)}), pd.Series([0] * 100)

    class QualityReport:
        global_score = 83.0
        critical_count = 0

    monkeypatch.setattr(dataset_builder, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_args, **_kwargs: (True, QualityReport()),
    )


def _write_minimal_csv(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=2, freq="h"),
        "open": [1.0, 1.1],
        "high": [1.1, 1.2],
        "low": [0.9, 1.0],
        "close": [1.05, 1.15],
        "volume": [100.0, 100.0],
        "pair": ["EURUSD", "EURUSD"],
    })
    frame.to_csv(path, index=False)
    return frame


def test_default_model_storage_is_project_rooted_across_external_cwd(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "opt" / "astra"
    external_cwd = tmp_path / "home" / "ubuntu" / "astra-source"
    external_cwd.mkdir(parents=True)
    monkeypatch.setattr(runtime_paths, "PROJECT_ROOT", project_root)
    monkeypatch.chdir(external_cwd)

    storage = ModelStorage()

    assert runtime_paths.FOREX_MODEL_RELATIVE_ROOT == Path("models") / "forex"
    assert storage.base_dir == project_root / "models" / "forex"
    assert storage.base_dir.is_dir()
    assert not (external_cwd / "models").exists()


def test_explicit_model_storage_directory_remains_caller_owned(
    monkeypatch, tmp_path
):
    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()
    monkeypatch.chdir(caller_cwd)

    relative = ModelStorage(base_dir="advanced/models")
    absolute_root = tmp_path / "explicit-models"
    absolute = ModelStorage(base_dir=absolute_root)

    assert relative.base_dir == (caller_cwd / "advanced" / "models").resolve()
    assert absolute.base_dir == absolute_root.resolve()


def test_first_run_and_pipeline_report_defaults_are_h1():
    first_run_default = inspect.signature(
        run_first_deployment_check
    ).parameters["timeframe"].default
    pipeline_default = inspect.signature(
        run_pipeline_report
    ).parameters["timeframe"].default

    assert first_run_default == "H1"
    assert pipeline_default == "H1"
    assert PipelineReport("EURUSD").timeframe == "H1"


@pytest.mark.parametrize("timeframe", ["H4", "D1"])
def test_context_pipeline_report_never_trains_or_predicts(
    monkeypatch, tmp_path, timeframe
):
    from forex.prediction import integrated_pipeline

    csv_path = tmp_path / f"EURUSD_{timeframe}.csv"
    frame = _write_minimal_csv(csv_path)
    _patch_data_stages(monkeypatch, frame)

    def forbidden(*_args, **_kwargs):
        raise AssertionError(f"{timeframe} must not enter executable pipeline stages")

    monkeypatch.setattr(integrated_pipeline.ForexIntegratedPipeline, "train", forbidden)
    monkeypatch.setattr(integrated_pipeline.ForexIntegratedPipeline, "predict", forbidden)

    report = run_pipeline_report(
        symbol="EURUSD",
        timeframe=timeframe,
        csv_path=str(csv_path),
    )

    assert len(report.stages) == 12
    assert report.stages[4].status == "skip"
    assert report.stages[5].status == "skip"
    assert "contexto MTF" in report.stages[4].detail
    assert "no genera predicciones ejecutables" in report.stages[5].detail


def test_h1_report_uses_canonical_csv_and_autoresolves_mtf_context(
    monkeypatch, tmp_path
):
    from forex.prediction import integrated_pipeline, model_storage

    project_root = tmp_path / "opt" / "astra"
    data_root = project_root / "data" / "forex"
    h1 = data_root / "EURUSD_H1.csv"
    h4 = data_root / "EURUSD_H4.csv"
    d1 = data_root / "EURUSD_D1.csv"
    frame = _write_minimal_csv(h1)
    _write_minimal_csv(h4)
    _write_minimal_csv(d1)
    _patch_data_stages(monkeypatch, frame)
    monkeypatch.setattr(runtime_paths, "PROJECT_ROOT", project_root)

    class EmptyStorage:
        def latest_exists(self, pair=None):
            return False

    monkeypatch.setattr(model_storage, "ModelStorage", EmptyStorage)
    calls = []

    class Pipeline:
        def train(self, filepath, **kwargs):
            path_h4, path_d1 = _autoresolve_mtf(filepath)
            calls.append(("train", filepath, path_h4, path_d1, self.closed_loop_database))
            return {"precision": 0.7, "accuracy": 0.8}

        def predict(self, filepath, **kwargs):
            calls.append(("predict", filepath, self.closed_loop_database))
            return {"error": "stop after executable-stage contract assertions"}

    monkeypatch.setattr(integrated_pipeline, "ForexIntegratedPipeline", Pipeline)
    database = object()

    report = run_pipeline_report(symbol="EURUSD", db=database)

    assert report.stages[0].data == {}
    assert report.stages[1].data["path"] == str(h1)
    assert calls[0] == ("train", str(h1), str(h4), str(d1), database)
    assert calls[1] == ("predict", str(h1), database)


def test_readiness_model_lookup_uses_project_model_root(tmp_path):
    model_root = runtime_paths.forex_model_root(tmp_path)
    model_root.mkdir(parents=True)
    artifact = model_root / "latest_EURUSD.pkl"
    artifact.write_bytes(b"model-boundary")

    assert _find_model_path(runtime_paths.forex_model_root(tmp_path), "EURUSD") == artifact
    assert _find_model_path(tmp_path / "models", "EURUSD") is None
