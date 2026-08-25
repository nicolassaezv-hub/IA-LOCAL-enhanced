"""
robustness/first_run_wizard.py — Guided First-Run Wizard for ASTRA.

Simplifies initial setup by executing 10 ordered verification and initialization steps:
Step 1: Check Python environment (version >= 3.10)
Step 2: Install/verify dependencies
Step 3: Create directory structure (CSVs/, models/, memory_db/, logs/, reports/)
Step 4: Create astra.env from example if not exists
Step 5: Initialize database (create tables, seed default symbols)
Step 6: Generate initial CSVs for H1, H4, D1
Step 7: Train initial models
Step 8: Run first prediction
Step 9: Start workspace server check
Step 10: Run deployment validation
"""

from __future__ import annotations

import os
import sys
import shutil
import sqlite3
import importlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class WizardStep:
    """Dataclass holding status and details for a setup wizard step."""
    name: str
    description: str
    status: str = "PENDING"  # PASS, PENDING, FAIL, SKIPPED
    detail: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "detail": self.detail,
            "recommendation": self.recommendation,
        }


class FirstRunWizard:
    """Guided initial setup wizard for ASTRA environment initialization."""

    def __init__(self, project_root: Optional[Path] = None):
        self.root = Path(project_root) if project_root else _PROJECT_ROOT
        self.steps_history: List[WizardStep] = []

    def _print_step_header(self, step_idx: int, total_steps: int, step: WizardStep):
        print(f"[{step_idx}/{total_steps}] {step.name}")
        print(f"      Description: {step.description}")

    def _print_step_result(self, step: WizardStep):
        status_icon = step.status
        print(f"      Result     : {status_icon}")
        if step.detail:
            print(f"      Detail     : {step.detail}")
        if step.status == "FAIL" and step.recommendation:
            print(f"      Error/Rec  : {step.recommendation}")
        print()

    def step_1_check_python_environment(self) -> WizardStep:
        step = WizardStep(
            name="Step 1: Check Python environment",
            description="Check Python version >= 3.10",
        )
        v = sys.version_info
        current_version = f"{v.major}.{v.minor}.{v.micro}"
        if v >= (3, 10):
            step.status = "PASS"
            step.detail = f"Python {current_version} detected (meets >= 3.10 requirement)"
        else:
            step.status = "FAIL"
            step.detail = f"Python {current_version} is lower than required 3.10"
            step.recommendation = "Upgrade Python to version 3.10 or higher"
        return step

    def step_2_verify_dependencies(self) -> WizardStep:
        step = WizardStep(
            name="Step 2: Install/verify dependencies",
            description="Verify core Python libraries are available",
        )
        required_pkgs = ["pandas", "numpy", "sklearn", "requests", "sqlite3"]
        missing = []
        for pkg in required_pkgs:
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append(pkg)

        if not missing:
            step.status = "PASS"
            step.detail = f"All core dependencies verified: {', '.join(required_pkgs)}"
        else:
            step.status = "FAIL"
            step.detail = f"Missing dependency packages: {', '.join(missing)}"
            step.recommendation = f"Run 'pip install -r requirements.txt' or install missing packages: {', '.join(missing)}"
        return step

    def step_3_create_directory_structure(self) -> WizardStep:
        step = WizardStep(
            name="Step 3: Create directory structure",
            description="Create CSVs/, models/, memory_db/, logs/, reports/",
        )
        required_dirs = [
            self.root / "CSVs",
            self.root / "CSVs" / "H1",
            self.root / "CSVs" / "H4",
            self.root / "CSVs" / "D1",
            self.root / "models",
            self.root / "memory_db",
            self.root / "logs",
            self.root / "reports",
            self.root / "reports" / "deployment",
        ]
        try:
            for d in required_dirs:
                d.mkdir(parents=True, exist_ok=True)
            step.status = "PASS"
            step.detail = "Directories verified and created: CSVs/, models/, memory_db/, logs/, reports/"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Failed creating directory structure: {e}"
            step.recommendation = "Check workspace filesystem write permissions"
        return step

    def step_4_create_env_file(self) -> WizardStep:
        step = WizardStep(
            name="Step 4: Create astra.env from example if not exists",
            description="Create or verify astra.env environment file",
        )
        astra_env = self.root / "astra.env"
        env_example = self.root / "infra" / "config" / "astra.env.example"
        dot_env = self.root / ".env"

        try:
            if astra_env.exists():
                step.status = "PASS"
                step.detail = "astra.env already exists"
            elif env_example.exists():
                shutil.copy(env_example, astra_env)
                if not dot_env.exists():
                    shutil.copy(env_example, dot_env)
                step.status = "PASS"
                step.detail = "Created astra.env from .env.example"
            else:
                default_env = (
                    "# ASTRA Environment Configuration\n"
                    "ASTRA_ENV=development\n"
                    "ASTRA_PORT=8000\n"
                )
                astra_env.write_text(default_env, encoding="utf-8")
                step.status = "PASS"
                step.detail = "Created default astra.env file"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Failed creating astra.env: {e}"
            step.recommendation = "Ensure write permissions or manually copy .env.example to astra.env"
        return step

    def step_5_initialize_database(self) -> WizardStep:
        step = WizardStep(
            name="Step 5: Initialize database",
            description="Create tables and seed default symbols",
        )
        try:
            from infra.db.database import get_database
            from forex.data.symbol_catalog import get_symbol_spec

            db = get_database()

            default_symbols = [
                "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
                "AUDUSD", "NZDUSD", "USDCAD", "EURGBP",
                "EURJPY", "GBPJPY", "XAUUSD"
            ]
            for sym in default_symbols:
                spec = get_symbol_spec(sym)
                db.add_symbol(
                    code=spec.symbol_code,
                    name=spec.display_name,
                    pip=spec.pip_value,
                )

            step.status = "PASS"
            backend = getattr(db, "db_path", type(db).__name__)
            step.detail = (
                f"Canonical database initialized at {backend} with "
                f"{len(default_symbols)} catalogued symbols seeded by lifecycle"
            )
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Database initialization failed: {e}"
            step.recommendation = "Verify SQLite3 driver availability and memory_db/ folder permissions"
        return step

    def step_6_generate_initial_csvs(self) -> WizardStep:
        step = WizardStep(
            name="Step 6: Generate initial CSVs for H1, H4, D1",
            description="Generate baseline CSV data for timeframes H1, H4, D1",
        )
        try:
            from infra.db.database import get_database
            from scheduler.autonomous_scheduler import run_init

            db = get_database()
            results = run_init(db)
            ready_actions = {"generated", "updated", "skip"}
            ready_count = sum(
                result.get("action") in ready_actions for result in results
            )
            if results and ready_count == len(results):
                step.status = "PASS"
                step.detail = (
                    f"Canonical scheduler initialized {ready_count} real rolling datasets"
                )
            else:
                step.status = "PENDING"
                step.detail = (
                    f"Only {ready_count}/{len(results)} datasets satisfy initialization; "
                    "no synthetic fallback was used"
                )
                step.recommendation = "Restore a real provider and rerun initialization"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"CSV generation failed: {e}"
            step.recommendation = "Check the canonical DataRouter and scheduler initialization"
        return step

    def step_7_train_initial_models(self) -> WizardStep:
        step = WizardStep(
            name="Step 7: Train initial models",
            description="Train baseline prediction models on generated CSV datasets",
        )
        try:
            eurusd_h1 = self.root / "CSVs" / "H1" / "EURUSD.csv"
            if not eurusd_h1.exists():
                eurusd_h1 = self.root / "forex" / "data" / "EURUSD_H1.csv"

            if eurusd_h1.exists():
                from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
                pipeline = ForexIntegratedPipeline()
                res = pipeline.train(str(eurusd_h1), pair="EURUSD")
                training_complete = (
                    isinstance(res, dict)
                    and res.get("type") == "training_complete"
                    and res.get("model_valid") is True
                    and res.get("model") == "guardado"
                )
                if training_complete:
                    step.status = "PASS"
                    step.detail = (
                        "Training completed and the pipeline explicitly reported "
                        f"a persisted valid model (accuracy: {res['accuracy']:.2f})"
                    )
                else:
                    step.status = "PENDING"
                    step.detail = f"Training did not produce a required valid model: {res}"
                    step.recommendation = "Resolve the quality/model gate before readiness"
            else:
                step.status = "PENDING"
                step.detail = "A canonical EURUSD/H1 dataset is not available; no placeholder model was created"
                step.recommendation = "Complete the real dataset initialization first"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Model training failed: {e}"
            step.recommendation = "Ensure scikit-learn / xgboost and feature engineering dependencies are loaded"
        return step

    def step_8_run_first_prediction(self) -> WizardStep:
        step = WizardStep(
            name="Step 8: Run first prediction",
            description="Execute test prediction using trained pipeline",
        )
        try:
            eurusd_h1 = self.root / "CSVs" / "H1" / "EURUSD.csv"
            if not eurusd_h1.exists():
                eurusd_h1 = self.root / "forex" / "data" / "EURUSD_H1.csv"

            if eurusd_h1.exists():
                from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
                pipeline = ForexIntegratedPipeline()
                pred = pipeline.predict(str(eurusd_h1), pair="EURUSD")
                if isinstance(pred, dict) and pred.get("type") == "prediction" and "action" in pred:
                    step.status = "PASS"
                    step.detail = (
                        "First prediction executed with explicit pipeline evidence: "
                        f"action={pred['action']}, confidence={pred.get('confidence')}"
                    )
                else:
                    step.status = "FAIL"
                    step.detail = f"Prediction returned no valid evidence: {pred}"
                    step.recommendation = "Check model and prediction safeguards"
            else:
                step.status = "PENDING"
                step.detail = "Prediction was not executed because the canonical dataset is missing"
                step.recommendation = "Complete dataset and model initialization"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"First prediction failed: {e}"
            step.recommendation = "Check predictor feature pipeline compatibility"
        return step

    def step_9_start_workspace_server_check(self) -> WizardStep:
        step = WizardStep(
            name="Step 9: Start workspace server check",
            description="Verify workspace server endpoints and startup status",
        )
        try:
            from infra.monitor.supervisor import check_api_health
            api_ok = check_api_health()
            if api_ok:
                step.status = "PASS"
                step.detail = "Workspace server API responding on health endpoint"
            else:
                step.status = "PENDING"
                step.detail = "Workspace module may exist, but no operational health response was verified"
                step.recommendation = "Start Workplace and verify its health endpoint"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Workspace server check failed: {e}"
            step.recommendation = "Run 'python workspace/server.py' to debug API startup"
        return step

    def step_10_run_deployment_validation(self) -> WizardStep:
        step = WizardStep(
            name="Step 10: Run deployment validation",
            description="Run deployment readiness and validation suite",
        )
        try:
            from deployment.first_run_validator import run_first_deployment_check
            result = run_first_deployment_check(
                symbols=["EURUSD"],
                timeframe="H1",
                force=True,
                probe_providers=True,
            )
            dep_status = result.get("deployment_status", "UNKNOWN")
            readiness_status = result.get("readiness_status", "UNKNOWN")
            if result.get("ready") is True:
                step.status = "PASS"
                step.detail = f"Readiness verified: deployment={dep_status}, readiness={readiness_status}"
            else:
                step.status = "PENDING" if result.get("status") == "pending" else "FAIL"
                step.detail = (
                    f"Readiness is not complete: deployment={dep_status}, "
                    f"readiness={readiness_status}; blockers={result.get('blocking_reasons', [])}"
                )
                step.recommendation = "Resolve every blocking readiness reason"
        except Exception as e:
            step.status = "FAIL"
            step.detail = f"Deployment validation failed: {e}"
            step.recommendation = "Execute 'python -m deployment.first_run_validator' for diagnostic report"
        return step

    def run(self, auto_continue: bool = False) -> dict:
        """
        Executes all 10 setup steps sequentially.
        
        Args:
            auto_continue: If True, continues executing subsequent steps even if a step fails.
                           If False, halts execution upon encountering a step failure.
                           
        Returns:
            dict containing overall status, step details, and execution counters.
        """
        print(f"\n{'='*65}")
        print(f"  ASTRA — Guided First-Run Setup Wizard")
        print(f"  auto_continue = {auto_continue}")
        print(f"{'='*65}\n")

        methods = [
            self.step_1_check_python_environment,
            self.step_2_verify_dependencies,
            self.step_3_create_directory_structure,
            self.step_4_create_env_file,
            self.step_5_initialize_database,
            self.step_6_generate_initial_csvs,
            self.step_7_train_initial_models,
            self.step_8_run_first_prediction,
            self.step_9_start_workspace_server_check,
            self.step_10_run_deployment_validation,
        ]

        self.steps_history = []
        has_failed = False
        total_count = len(methods)

        for i, method in enumerate(methods, 1):
            if has_failed and not auto_continue:
                step_obj = WizardStep(
                    name=f"Step {i}",
                    description="Step skipped due to previous step failure",
                    status="SKIPPED",
                    detail="Execution halted because auto_continue is False",
                )
                self.steps_history.append(step_obj)
                self._print_step_header(i, total_count, step_obj)
                self._print_step_result(step_obj)
                continue

            # Instantiate and execute step method
            step_obj = method()
            self._print_step_header(i, total_count, step_obj)

            if step_obj.status in {"FAIL", "PENDING"}:
                has_failed = True

            self.steps_history.append(step_obj)
            self._print_step_result(step_obj)

        passed_count = sum(1 for s in self.steps_history if s.status == "PASS")
        failed_count = sum(1 for s in self.steps_history if s.status == "FAIL")
        pending_count = sum(1 for s in self.steps_history if s.status == "PENDING")
        skipped_count = sum(1 for s in self.steps_history if s.status == "SKIPPED")
        if failed_count:
            overall_status = "ERROR"
        elif pending_count or skipped_count:
            overall_status = "PENDING"
        else:
            overall_status = "READY"

        print(f"{'='*65}")
        print(f"  WIZARD COMPLETE — Status: {overall_status}")
        print(
            f"  Passed: {passed_count}/{total_count} | Pending: {pending_count} | "
            f"Failed: {failed_count} | Skipped: {skipped_count}"
        )
        print(f"{'='*65}\n")

        return {
            "status": overall_status,
            "ready": overall_status == "READY",
            "passed": passed_count,
            "failed": failed_count,
            "pending": pending_count,
            "skipped": skipped_count,
            "total_steps": total_count,
            "summary": f"Wizard finished with status {overall_status} ({passed_count}/{total_count} passed)",
            "steps": [s.to_dict() for s in self.steps_history],
        }


def run_wizard(auto_continue: bool = False) -> dict:
    """Convenience function to run FirstRunWizard."""
    wizard = FirstRunWizard()
    return wizard.run(auto_continue=auto_continue)


if __name__ == "__main__":
    auto = "--auto" in sys.argv or "-y" in sys.argv
    run_wizard(auto_continue=auto)
