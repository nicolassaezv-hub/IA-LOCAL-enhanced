"""
prediction_lab/report_generator.py — Fase 5.7 (Prediction Lab)

Orquesta el flujo completo: Prompt Analyzer (5.1) -> Dataset Analyzer (5.2)
-> Feasibility Engine (5.3) -> Model Planner (5.4) -> Pipeline Generator (5.5)
-> Validation Engine (5.6), y compila todo en un único LabReport.

Reutiliza las variantes "_from" de cada módulo para no recalcular ProblemSpec /
DatasetReport / FeasibilityReport más de una vez (evita, por ejemplo, correr
analyze_prompt() dos veces con resultados potencialmente distintos si el LLM
está de por medio).

Patrón "graceful fail" (igual que Feasibility/Model Planner): si la viabilidad
es insuficiente, el reporte se detiene ahí y explica por qué, sin intentar
generar pipeline ni entrenar nada.

Persistencia: cada 'lab reporte' ejecutado se guarda como JSON en
lab_reports/<slug>_<timestamp>.json (sin objetos no serializables — el
sklearn Pipeline entrenado y el snapshot de datos quedan fuera del JSON,
pero el code_snippet sí se preserva). Esto habilita 'lab proyectos' y
'lab info proyecto <nombre>' sin depender de una sesión en memoria.

API pública:
  run_full_lab(csv_path, idea, target_variable=None) -> LabReport
  cmd_lab_reporte(csv_path, idea)                    -> str
  cmd_lab_proyectos()                                -> str
  cmd_lab_info_proyecto(nombre_o_indice)              -> str
"""

from __future__ import annotations

import json
import os
import re
import numpy as np
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompt_analyzer import analyze_prompt, ProblemSpec
from .dataset_analyzer import analyze_dataset, DatasetReport
from .feasibility_engine import assess_feasibility_from, FeasibilityReport
from .model_planner import plan_models_from, ModelPlan
from .pipeline_generator import generate_pipeline_from_csv, GeneratedPipeline
from .validation_engine import validate_from_csv, ValidationResult

LAB_REPORTS_DIR = "lab_reports"


# ══════════════════════════════════════════════════════════
#  ESTRUCTURA DEL REPORTE
# ══════════════════════════════════════════════════════════

def _to_jsonable(obj: Any) -> Any:
    """Convierte recursivamente tipos numpy (bool_, int64, float64, ndarray)
    a tipos nativos de Python — necesario porque numpy.bool_ NO es
    JSON-serializable de forma nativa y json.dump() con default=str lo
    convertiría a la STRING "False", que es truthy en Python (bug real
    detectado: causaba que reportes NO_PASA se listaran como PASA)."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    return obj


@dataclass
class LabReport:
    ok:            bool = True
    error:         Optional[str] = None
    stage_reached: str = "none"   # "prompt" | "dataset" | "feasibility" | "plan" | "pipeline" | "validation"

    timestamp:  str = ""
    csv_path:   str = ""
    idea:       str = ""
    name:       str = ""   # slug derivado de csv_path, usado como identificador del "proyecto"

    problem_spec:       Optional[ProblemSpec] = None
    dataset_report:      Optional[DatasetReport] = None
    feasibility:         Optional[FeasibilityReport] = None
    model_plan:          Optional[ModelPlan] = None
    generated_pipeline:  Optional[GeneratedPipeline] = None
    validation:          Optional[ValidationResult] = None

    notes: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── serialización ──────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """Versión JSON-serializable — omite objetos no serializables
        (sklearn Pipeline entrenado, DataFrames) pero conserva todo lo
        demás (métricas, código generado, notas, viabilidad, etc.)."""
        d: Dict[str, Any] = {
            "ok": self.ok, "error": self.error, "stage_reached": self.stage_reached,
            "timestamp": self.timestamp, "csv_path": self.csv_path,
            "idea": self.idea, "name": self.name, "notes": self.notes,
        }
        if self.problem_spec is not None:
            d["problem_spec"] = asdict(self.problem_spec)
        if self.dataset_report is not None:
            d["dataset_report"] = asdict(self.dataset_report)
        if self.feasibility is not None:
            d["feasibility"] = asdict(self.feasibility)
        if self.model_plan is not None:
            d["model_plan"] = asdict(self.model_plan)
        if self.generated_pipeline is not None:
            gp = asdict(self.generated_pipeline)
            gp.pop("pipeline", None)  # sklearn Pipeline no serializable
            d["generated_pipeline"] = gp
        if self.validation is not None:
            v = asdict(self.validation)
            v.pop("trained_pipeline", None)  # sklearn Pipeline entrenado no serializable
            d["validation"] = v
        return d

    def save(self, out_dir: str = LAB_REPORTS_DIR) -> str:
        """Persiste el reporte como JSON. Devuelve la ruta del archivo."""
        os.makedirs(out_dir, exist_ok=True)
        ts_slug = self.timestamp.replace(" ", "_").replace(":", "-")
        fname = f"{self.name or 'proyecto'}_{ts_slug}.json"
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(_to_jsonable(self.to_dict()), f, ensure_ascii=False, indent=2, default=str)
        return fpath

    # ── presentación ───────────────────────────────────────
    def summary(self, include_code: bool = False) -> str:
        sep = "═" * 64
        thin = "─" * 64

        def bar(v: float, mx: float = 100.0) -> str:
            v = max(0.0, min(mx, v))
            filled = int(v / mx * 20)
            return "[" + "█" * filled + "░" * (20 - filled) + "]"

        lines = [
            "", sep,
            " ASTRA PREDICTION LAB — REPORTE COMPLETO (Fase 5.7)",
            sep,
            f" Proyecto : {self.name}",
            f" Archivo  : {self.csv_path}",
            f" Idea     : {self.idea or '(no especificada)'}",
            f" Fecha    : {self.timestamp}",
            thin,
        ]

        if not self.ok:
            lines.append(f" ✘ Reporte incompleto — se detuvo en etapa '{self.stage_reached}'.")
            lines.append(f"   Motivo: {self.error}")
            lines.append(sep)
            return "\n".join(lines)

        # 1. Viabilidad
        if self.feasibility is not None:
            f_ = self.feasibility
            lines += [
                " 1. VIABILIDAD",
                f"    Índice  : {f_.viability_index:.1f}/100  {bar(f_.viability_index)}",
                f"    Veredicto: {f_.verdict}",
            ]
            if f_.blocking_issues:
                lines.append("    Bloqueos:")
                lines += [f"      - {b}" for b in f_.blocking_issues]
            lines.append(thin)

        # Si no es viable, el flujo se detiene aquí — no hay plan/pipeline/validación.
        if self.feasibility is not None and not self.feasibility.is_viable:
            lines.append(" ⚠ Viabilidad insuficiente — no se generó plan de modelo ni se entrenó nada.")
            if self.feasibility.suggestions:
                lines.append(" Sugerencias:")
                lines += [f"   - {s}" for s in self.feasibility.suggestions]
            lines += [sep]
            return "\n".join(lines)

        # 2. Plan de modelo
        if self.model_plan is not None and self.model_plan.ok:
            mp = self.model_plan
            lines += [
                " 2. PLAN DE MODELO",
                f"    Target      : {mp.target_variable}",
                f"    Tipo        : {mp.problem_type}   Dominio: {mp.domain}",
                f"    Validación  : {mp.validation.method if mp.validation else '?'}",
                f"    Métrica     : {mp.validation.metric if mp.validation else '?'}"
                f"  (mínimo esperado: {mp.expected_min_metric})",
                "    Algoritmos  : " + ", ".join(f"{a.name}[{a.role}]" for a in mp.algorithms),
            ]
            if mp.reuse_existing:
                lines.append(f"    ⚑ Reutilización sugerida: {mp.reuse_existing}")
            lines.append(thin)

        # 3. Pipeline generado
        if self.generated_pipeline is not None and self.generated_pipeline.ok:
            gp = self.generated_pipeline
            lines += [
                " 3. PIPELINE",
                f"    Features : {len(gp.feature_names)}  ({', '.join(gp.feature_names[:8])}"
                f"{' ...' if len(gp.feature_names) > 8 else ''})",
                f"    Estimador: {gp.meta.get('estimator_repr', '?')}",
                thin,
            ]

        # 4. Validación
        if self.validation is not None and self.validation.ok:
            v = self.validation
            verdict = "PASA ✔" if v.passes else "NO PASA ✘"
            lines += [
                " 4. VALIDACIÓN (entrenamiento real)",
                f"    Método    : {v.method}",
                f"    Score     : {v.mean_score:.4f} ± {v.std_score:.4f}  "
                f"(mínimo: {v.min_expected:.4f})  {bar(v.mean_score * 100)}",
                f"    Veredicto : {verdict}",
            ]
            if v.feature_importance:
                lines.append("    Top features:")
                top = sorted(v.feature_importance.items(), key=lambda x: -x[1])[:5]
                for feat, imp in top:
                    lines.append(f"      {feat:<28}: {imp:.4f}")
            if v.warnings_list:
                lines.append("    Avisos:")
                lines += [f"      ! {w}" for w in v.warnings_list]
            lines.append(thin)

        if self.notes:
            lines.append(" NOTAS ADICIONALES:")
            lines += [f"   * {n}" for n in self.notes]
            lines.append(thin)

        if include_code and self.generated_pipeline is not None and self.generated_pipeline.code_snippet:
            lines += [" CÓDIGO GENERADO:", thin, self.generated_pipeline.code_snippet, thin]

        lines.append(sep)
        return "\n".join(lines)

    def to_compact_dict(self) -> Dict[str, Any]:
        """Resumen corto — usado por 'lab proyectos' para listar sin abrir cada JSON completo."""
        viability = self.feasibility.viability_index if self.feasibility else None
        score = self.validation.mean_score if self.validation else None
        passes = self.validation.passes if self.validation else None
        return {
            "name": self.name, "timestamp": self.timestamp, "csv_path": self.csv_path,
            "idea": self.idea, "ok": self.ok, "viability_index": viability,
            "mean_score": score, "passes": passes,
            "target_variable": self.model_plan.target_variable if self.model_plan else None,
        }


# ══════════════════════════════════════════════════════════
#  ORQUESTADOR
# ══════════════════════════════════════════════════════════

def _slug_from_csv(csv_path: str) -> str:
    base = os.path.splitext(os.path.basename(csv_path))[0]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_").lower()
    return slug or "proyecto"


def run_full_lab(csv_path: str, idea: str, target_variable: Optional[str] = None) -> LabReport:
    """
    Corre la cadena completa 5.1 -> 5.6 una sola vez y compila el resultado.
    Se detiene apenas una etapa reporta ok=False o viabilidad insuficiente,
    devolviendo un LabReport parcial que explica en qué etapa y por qué.
    """
    name = _slug_from_csv(csv_path)
    report = LabReport(csv_path=csv_path, idea=idea, name=name)

    # 5.1 Prompt Analyzer
    try:
        problem_spec = analyze_prompt(idea)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Prompt Analyzer falló: {e}", "prompt"
        return report
    report.problem_spec = problem_spec

    # 5.2 Dataset Analyzer
    try:
        dataset_report = analyze_dataset(csv_path, target_variable=target_variable, problem_spec=problem_spec)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Dataset Analyzer falló: {e}", "dataset"
        return report
    report.dataset_report = dataset_report
    if not dataset_report.ok:
        report.ok, report.error, report.stage_reached = False, dataset_report.error, "dataset"
        return report

    # 5.3 Feasibility Engine
    try:
        feasibility = assess_feasibility_from(problem_spec, dataset_report)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Feasibility Engine falló: {e}", "feasibility"
        return report
    report.feasibility = feasibility
    if not feasibility.ok:
        report.ok, report.error, report.stage_reached = False, feasibility.error, "feasibility"
        return report
    report.stage_reached = "feasibility"

    if not feasibility.is_viable:
        # Graceful fail: reporte válido, pero no viable — no seguimos a plan/pipeline/validación.
        report.notes.append(
            f"Índice de viabilidad {feasibility.viability_index:.1f}/100 (< 40) — "
            "no se generó plan de modelo ni se entrenó nada."
        )
        return report

    # 5.4 Model Planner
    try:
        model_plan = plan_models_from(problem_spec, dataset_report, feasibility)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Model Planner falló: {e}", "plan"
        return report
    report.model_plan = model_plan
    report.stage_reached = "plan"
    if not model_plan.ok:
        report.ok, report.error = False, model_plan.error
        return report

    # 5.5 Pipeline Generator
    try:
        generated = generate_pipeline_from_csv(model_plan, csv_path)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Pipeline Generator falló: {e}", "pipeline"
        return report
    report.generated_pipeline = generated
    report.stage_reached = "pipeline"
    if not generated.ok:
        report.ok, report.error = False, generated.error
        return report

    # 5.6 Validation Engine
    try:
        validation = validate_from_csv(generated, model_plan, csv_path)
    except Exception as e:
        report.ok, report.error, report.stage_reached = False, f"Validation Engine falló: {e}", "validation"
        return report
    report.validation = validation
    report.stage_reached = "validation"
    if not validation.ok:
        report.ok, report.error = False, validation.error
        return report

    if validation.passes:
        report.notes.append("El modelo superó la métrica mínima esperada — candidato a producción con más validación.")
    else:
        report.notes.append("El modelo NO superó la métrica mínima — tratar como baseline exploratorio, no usar en real.")

    return report


# ══════════════════════════════════════════════════════════
#  LISTADO / CONSULTA DE PROYECTOS GUARDADOS
# ══════════════════════════════════════════════════════════

def list_lab_reports(reports_dir: str = LAB_REPORTS_DIR) -> List[Dict[str, Any]]:
    if not os.path.isdir(reports_dir):
        return []
    entries = []
    for fname in sorted(os.listdir(reports_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(reports_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            entries.append({
                "file": fname,
                "name": data.get("name"),
                "timestamp": data.get("timestamp"),
                "csv_path": data.get("csv_path"),
                "ok": data.get("ok"),
                "viability_index": (data.get("feasibility") or {}).get("viability_index"),
                "mean_score": (data.get("validation") or {}).get("mean_score"),
                "passes": (data.get("validation") or {}).get("passes"),
            })
        except Exception:
            continue
    return entries


def _load_lab_report_raw(identifier: str, reports_dir: str = LAB_REPORTS_DIR) -> Optional[Dict[str, Any]]:
    """Busca por índice (1-based, más reciente primero), nombre de proyecto o nombre de archivo."""
    entries = list_lab_reports(reports_dir)
    if not entries:
        return None

    entries_sorted = sorted(entries, key=lambda e: e["timestamp"] or "", reverse=True)

    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(entries_sorted):
            fpath = os.path.join(reports_dir, entries_sorted[idx]["file"])
            with open(fpath, encoding="utf-8") as f:
                return json.load(f)
        return None

    matches = [e for e in entries_sorted if e["name"] == identifier or e["file"] == identifier]
    if not matches:
        matches = [e for e in entries_sorted if identifier.lower() in (e["name"] or "").lower()]
    if not matches:
        return None
    fpath = os.path.join(reports_dir, matches[0]["file"])
    with open(fpath, encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════
#  COMANDOS CLI
# ══════════════════════════════════════════════════════════

def cmd_lab_reporte(csv_path: str, idea: str, target_variable: Optional[str] = None) -> str:
    """Comando CLI: 'lab reporte <csv> "<idea>"' — corre 5.1->5.6 y compila+guarda el reporte."""
    if not csv_path or not idea:
        return 'Uso: lab reporte <archivo.csv> "<describe tu idea>"'
    report = run_full_lab(csv_path, idea, target_variable=target_variable)
    try:
        fpath = report.save()
        footer = f"\n[Guardado en: {fpath}]"
    except Exception as e:
        footer = f"\n[⚠ No se pudo guardar el reporte: {e}]"
    return report.summary() + footer


def cmd_lab_proyectos() -> str:
    """Comando CLI: 'lab proyectos' — lista todos los reportes del Prediction Lab guardados."""
    entries = list_lab_reports()
    if not entries:
        return "No hay proyectos del Prediction Lab guardados todavía. Usa 'lab reporte <csv> \"<idea>\"' para crear uno."
    entries_sorted = sorted(entries, key=lambda e: e["timestamp"] or "", reverse=True)
    lines = [f"Proyectos del Prediction Lab ({len(entries_sorted)}):", "-" * 60]
    for i, e in enumerate(entries_sorted, start=1):
        estado = "✔ PASA" if e.get("passes") else ("✘ NO PASA" if e.get("passes") is not None else "—")
        viab = e.get("viability_index")
        viab_s = f"{viab:.0f}/100" if viab is not None else "—"
        score = e.get("mean_score")
        score_s = f"{score:.3f}" if score is not None else "—"
        lines.append(f" {i}. {e['name']:<20} viab={viab_s:<8} score={score_s:<8} {estado}   ({e['timestamp']})")
    lines.append("-" * 60)
    lines.append("Usa 'lab info proyecto <numero|nombre>' para ver el detalle completo.")
    return "\n".join(lines)


def cmd_lab_info_proyecto(identifier: str) -> str:
    """Comando CLI: 'lab info proyecto <nombre|numero>' — detalle completo de un reporte guardado."""
    if not identifier:
        return "Uso: lab info proyecto <numero_de_lista|nombre>"
    data = _load_lab_report_raw(identifier.strip())
    if data is None:
        return f"No se encontró ningún proyecto con el identificador '{identifier}'. Usa 'lab proyectos' para ver la lista."

    report = LabReport(
        ok=data.get("ok", True), error=data.get("error"),
        stage_reached=data.get("stage_reached", "?"),
        timestamp=data.get("timestamp", ""), csv_path=data.get("csv_path", ""),
        idea=data.get("idea", ""), name=data.get("name", ""),
        notes=data.get("notes", []),
    )
    if data.get("problem_spec"):
        report.problem_spec = ProblemSpec(**data["problem_spec"])
    if data.get("dataset_report"):
        report.dataset_report = DatasetReport(**data["dataset_report"])
    if data.get("feasibility"):
        report.feasibility = FeasibilityReport(**data["feasibility"])
    if data.get("model_plan"):
        mp = dict(data["model_plan"])
        from .model_planner import AlgorithmConfig, FeaturePlan, ValidationStrategy
        mp["algorithms"] = [AlgorithmConfig(**a) for a in mp.get("algorithms", [])]
        if mp.get("feature_plan"):
            mp["feature_plan"] = FeaturePlan(**mp["feature_plan"])
        if mp.get("validation"):
            mp["validation"] = ValidationStrategy(**mp["validation"])
        report.model_plan = ModelPlan(**mp)
    if data.get("generated_pipeline"):
        gp = dict(data["generated_pipeline"])
        gp.setdefault("pipeline", None)
        report.generated_pipeline = GeneratedPipeline(**gp)
    if data.get("validation"):
        v = dict(data["validation"])
        v.setdefault("trained_pipeline", None)
        report.validation = ValidationResult(**v)

    return report.summary()
