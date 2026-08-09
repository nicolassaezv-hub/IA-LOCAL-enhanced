"""
Robustness Module: Model Integrity Checker
Checks that all ML models are valid before the scheduler starts a new cycle.

Checks performed per model:
1. File exists and can be loaded (pickle.load / joblib.load)
2. Model is not corrupt (can call predict or has required attributes)
3. Model corresponds to the correct symbol (check filename)
4. Model has train_columns attribute (feature list)
5. Model file size is reasonable (> 1KB, not empty)
6. Model was created recently (within last 30 days - warning if older)

Automatic Recovery:
- Retrains missing, broken, or corrupt models using CSVs/H4/{symbol}.csv via ForexIntegratedPipeline.
- Marks model as BLOCKED if retraining fails.
"""

from dataclasses import dataclass, field
from datetime import datetime
import glob
import os
import pickle
import re
from typing import List, Optional
import joblib


@dataclass
class ModelCheck:
    symbol: str
    model_path: str
    status: str  # ok | fail | recovered | blocked
    issues: List[str] = field(default_factory=list)
    recovery_action: str = ""
    recommendation: str = ""


@dataclass
class ModelIntegrityReport:
    checks: List[ModelCheck] = field(default_factory=list)
    total_models: int = 0
    ok_count: int = 0
    recovered_count: int = 0
    blocked_count: int = 0

    def to_markdown(self) -> str:
        lines = []
        lines.append("# 🛡️ Reporte de Integridad de Modelos ML")
        lines.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("## 📊 Resumen Ejecutivo")
        lines.append(f"- **Total de modelos evaluados:** {self.total_models}")
        lines.append(f"- **OK (Válidos):** {self.ok_count} ✅")
        lines.append(f"- **Recuperados:** {self.recovered_count} 🔄")
        lines.append(f"- **Bloqueados:** {self.blocked_count} ❌\n")

        lines.append("## 🔍 Detalle por Modelo")
        lines.append("| Símbolo | Ruta del Modelo | Estado | Problemas Detectados | Acción de Recuperación | Recomendación |")
        lines.append("|---|---|---|---|---|---|")

        status_emoji = {
            "ok": "✅ OK",
            "fail": "⚠️ FAIL",
            "recovered": "🔄 RECOVERED",
            "blocked": "❌ BLOCKED"
        }

        for c in self.checks:
            st = status_emoji.get(c.status, c.status.upper())
            issues_str = "<br>".join(c.issues) if c.issues else "Ninguno"
            rec_act = c.recovery_action if c.recovery_action else "N/A"
            recom = c.recommendation if c.recommendation else "N/A"
            lines.append(f"| `{c.symbol}` | `{c.model_path}` | {st} | {issues_str} | {rec_act} | {recom} |")

        lines.append("\n---")
        if self.blocked_count > 0:
            lines.append(f"⚠️ **ADVERTENCIA:** Hay {self.blocked_count} modelo(s) bloqueado(s). El scheduler NO debe utilizarlos.")
        else:
            lines.append("✅ **ESTADO GENERAL:** Todos los modelos están operativos o han sido recuperados.")

        return "\n".join(lines)


def parse_symbol_from_path(filepath: str) -> str:
    """Extracts currency pair/symbol from model filepath."""
    filename = os.path.basename(filepath)
    # Check standard forex pairs
    m = re.search(r'(EURUSD|GBPUSD|USDJPY|AUDUSD|USDCAD|USDCHF|NZDUSD|EURGBP|EURJPY|GBPJPY)', filename, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    clean = re.sub(r'\.pkl$', '', filename)
    clean = re.sub(r'^(latest_|ensemble_)', '', clean)
    parts = clean.split('_')
    if parts and parts[0]:
        candidate = parts[0].upper()
        if candidate != "MODEL":
            return candidate
    return "UNKNOWN"


def _check_single_model(model_path: str, expected_symbol: Optional[str] = None, auto_recover: bool = True) -> ModelCheck:
    """Performs individual checks on a single model file and attempts recovery if needed."""
    issues = []
    recovery_action = ""
    recommendation = ""
    status = "ok"

    symbol = expected_symbol or parse_symbol_from_path(model_path)
    if not symbol or symbol == "UNKNOWN":
        symbol = "UNKNOWN"

    # Check 1 & 5: File existence and size
    if not os.path.exists(model_path):
        issues.append(f"El archivo no existe: {model_path}")
        status = "fail"
    else:
        size = os.path.getsize(model_path)
        if size <= 1024:
            issues.append(f"Tamaño de archivo demasiado pequeño ({size} bytes <= 1KB)")
            status = "fail"

    loaded_obj = None
    model_obj = None

    # Check 1: Unpickling load
    if os.path.exists(model_path) and status == "ok":
        try:
            with open(model_path, 'rb') as f:
                loaded_obj = pickle.load(f)
        except Exception as e_pickle:
            try:
                loaded_obj = joblib.load(model_path)
            except Exception as e_joblib:
                issues.append(f"Error al cargar el archivo pickle/joblib: {e_pickle}")
                status = "fail"

    # Check 2 & 4 & 6 if loaded
    if loaded_obj is not None:
        if isinstance(loaded_obj, dict):
            model_obj = loaded_obj.get("model", loaded_obj)
        else:
            model_obj = loaded_obj

        # Check 2: Model non-corrupt (predict or attributes)
        has_predict = hasattr(model_obj, "predict") and callable(getattr(model_obj, "predict"))
        has_essential_attrs = hasattr(model_obj, "predict_proba") or hasattr(model_obj, "fit")
        if not (has_predict or has_essential_attrs):
            issues.append("El objeto del modelo está corrupto o no tiene el método 'predict'")
            status = "fail"

        # Check 4: train_columns attribute (feature list)
        train_cols = None
        if isinstance(loaded_obj, dict):
            train_cols = loaded_obj.get("train_columns") or loaded_obj.get("feature_names")
        if not train_cols and model_obj is not None:
            train_cols = getattr(model_obj, "train_columns", None) or getattr(model_obj, "feature_names", None)

        if not train_cols or not isinstance(train_cols, (list, tuple, set, range)) or len(train_cols) == 0:
            issues.append("El modelo no tiene el atributo/lista de características 'train_columns'")
            status = "fail"
        else:
            # Attach train_columns attribute to model_obj if missing
            if model_obj is not None and not hasattr(model_obj, "train_columns"):
                try:
                    setattr(model_obj, "train_columns", list(train_cols))
                except Exception:
                    pass

        # Check 6: Created recently (within 30 days)
        mtime = os.path.getmtime(model_path)
        age_days = (datetime.now() - datetime.fromtimestamp(mtime)).days
        if age_days > 30:
            issues.append(f"El modelo fue creado hace {age_days} días (> 30 días, advertencia)")

    # Check 3: Symbol correspondence
    if expected_symbol and symbol != "UNKNOWN":
        if expected_symbol.upper() not in symbol.upper() and symbol.upper() not in expected_symbol.upper():
            issues.append(f"El símbolo del modelo '{symbol}' no coincide con el esperado '{expected_symbol}'")
            status = "fail"

    # Auto-recovery logic
    if status == "fail" and auto_recover:
        csv_candidates = [
            f"CSVs/H4/{symbol}.csv",
            f"CSVs/H4/{symbol.upper()}.csv",
            f"CSVs/H4/{symbol.lower()}.csv",
        ]
        csv_path = None
        for cand in csv_candidates:
            if os.path.exists(cand):
                csv_path = cand
                break

        if csv_path:
            recovery_action = f"Reentrenando modelo para {symbol} usando {csv_path}"
            try:
                from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
                pipe = ForexIntegratedPipeline()
                result = pipe.train(csv_path, pair=symbol, use_wfv=False, force=True)
                if isinstance(result, dict) and "error" in result:
                    status = "blocked"
                    issues.append(f"Falló el reentrenamiento automático: {result['error']}")
                    recommendation = f"Revisar datos en {csv_path}"
                else:
                    status = "recovered"
                    recommendation = "Modelo recuperado exitosamente mediante reentrenamiento automático"
            except Exception as ex:
                status = "blocked"
                issues.append(f"Excepción en reentrenamiento: {str(ex)}")
                recommendation = "Investigar error de reentrenamiento o proveer pickle válido"
        else:
            status = "blocked"
            recovery_action = f"Intento de recuperación para {symbol}"
            issues.append(f"No se encontró el dataset CSV en CSVs/H4/{symbol}.csv")
            recommendation = f"Proporcionar CSVs/H4/{symbol}.csv para permitir reentrenamiento"

    if status == "ok":
        if issues:
            recommendation = "Modelo válido con advertencias de antigüedad"
        else:
            recommendation = "Modelo válido y listo para operar"
    elif status == "fail":
        recommendation = "Falló la verificación de integridad (recuperación automática desactivada)"

    return ModelCheck(
        symbol=symbol,
        model_path=model_path,
        status=status,
        issues=issues,
        recovery_action=recovery_action,
        recommendation=recommendation
    )


def run_model_integrity_check(models_dir: str = "models/forex", auto_recover: bool = True) -> ModelIntegrityReport:
    """
    Checks all ML models in models_dir before the scheduler starts a new cycle.
    Attempts automatic recovery if auto_recover is True.
    Returns ModelIntegrityReport.
    """
    checks = []

    # Standard pairs to check from CSVs/H4 or models directory
    csv_pairs = set()
    if os.path.exists("CSVs/H4"):
        for csv_file in glob.glob("CSVs/H4/*.csv"):
            pair_name = os.path.basename(csv_file).replace(".csv", "").upper()
            csv_pairs.add(pair_name)

    # Find existing models
    scanned_files = set()
    if os.path.exists(models_dir):
        # Prioritize latest_{pair}.pkl
        latest_files = glob.glob(os.path.join(models_dir, "latest_*.pkl"))
        for lf in latest_files:
            if "latest_model.pkl" in lf:
                continue
            scanned_files.add(lf)
            sym = parse_symbol_from_path(lf)
            check = _check_single_model(lf, expected_symbol=sym if sym != "UNKNOWN" else None, auto_recover=auto_recover)
            checks.append(check)

    # Check for missing models where CSV dataset exists
    scanned_symbols = {c.symbol for c in checks}
    for csv_sym in csv_pairs:
        if csv_sym not in scanned_symbols and csv_sym != "UNKNOWN":
            target_path = os.path.join(models_dir, f"latest_{csv_sym}.pkl")
            check = _check_single_model(target_path, expected_symbol=csv_sym, auto_recover=auto_recover)
            checks.append(check)

    # If no files found so far, scan all *.pkl in models_dir
    if not checks and os.path.exists(models_dir):
        all_pkls = glob.glob(os.path.join(models_dir, "*.pkl"))
        for pkl in all_pkls:
            sym = parse_symbol_from_path(pkl)
            check = _check_single_model(pkl, expected_symbol=sym if sym != "UNKNOWN" else None, auto_recover=auto_recover)
            checks.append(check)

    total_models = len(checks)
    ok_count = sum(1 for c in checks if c.status == "ok")
    recovered_count = sum(1 for c in checks if c.status == "recovered")
    blocked_count = sum(1 for c in checks if c.status in ("blocked", "fail"))

    return ModelIntegrityReport(
        checks=checks,
        total_models=total_models,
        ok_count=ok_count,
        recovered_count=recovered_count,
        blocked_count=blocked_count
    )


def check_model_before_cycle(symbol: str, timeframe: str = "H4") -> bool:
    """
    Checks if a model for a specific symbol is valid before starting a cycle.
    Returns True if model is OK or successfully recovered; False if BLOCKED or failed.
    """
    models_dir = "models/forex"
    symbol_clean = symbol.upper()
    latest_path = os.path.join(models_dir, f"latest_{symbol_clean}.pkl")

    if not os.path.exists(latest_path):
        pattern = os.path.join(models_dir, f"*{symbol_clean}*.pkl")
        matches = glob.glob(pattern)
        if matches:
            latest_path = matches[0]

    check = _check_single_model(latest_path, expected_symbol=symbol_clean, auto_recover=True)
    return check.status in ("ok", "recovered")
