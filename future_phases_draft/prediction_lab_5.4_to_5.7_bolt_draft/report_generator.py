"""
prediction_lab/report_generator.py — ASTRA Phase 5.7

Compila todos los resultados del lab en un LabReport.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from .feasibility_engine import FeasibilityScore
from .model_planner import ModelPlan
from .pipeline_generator import GeneratedPipeline
from .validation_engine import ValidationResult


@dataclass
class LabReport:
    timestamp: str
    filepath: str
    prompt: str
    feasibility: FeasibilityScore
    model_plan: ModelPlan
    generated_pipeline: GeneratedPipeline
    validation: ValidationResult
    llm_interpretation: str = ""
    extra_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp, "filepath": self.filepath, "prompt": self.prompt,
            "viability_index": self.feasibility.viability_index, "is_viable": self.feasibility.is_viable,
            "target_col": self.model_plan.target_col,
            "algorithms": [a.name for a in self.model_plan.algorithms],
            "validation_method": self.validation.method, "metric": self.validation.metric,
            "mean_score": self.validation.mean_score, "passes": self.validation.passes,
            "n_features": len(self.generated_pipeline.feature_names),
            "top_features": list(self.validation.feature_importance.keys())[:5],
        }

    def render(self, include_code: bool = False) -> str:
        sep = "═" * 64
        thin = "─" * 64
        def bar(v, mx):
            return "[" + "█" * int(v/mx*20) + "░" * (20 - int(v/mx*20)) + "]"
        verdict = "PASA" if self.validation.passes else "NO PASA"
        lines = [
            "", sep,
            "  ASTRA PREDICTION LAB — REPORTE COMPLETO", sep,
            f"  Archivo  : {self.filepath}",
            f"  Fecha    : {self.timestamp}",
            f"  Problema : {self.prompt or '(no especificado)'}",
            thin, "",
            "1. VIABILIDAD",
            f"   Índice : {self.feasibility.viability_index:.1f}/100  {bar(self.feasibility.viability_index, 100)}",
            f"   Estado : {'VIABLE' if self.feasibility.is_viable else 'NO VIABLE'}",
        ]
        if self.feasibility.bottlenecks:
            lines.append("   Problemas:")
            lines += [f"     - {b}" for b in self.feasibility.bottlenecks]
        lines += [
            "", "2. PLAN DE MODELO",
            f"   Target     : {self.model_plan.target_col}",
            f"   Validación : {self.model_plan.validation.method}",
            f"   Métrica    : {self.model_plan.validation.metric}",
            "   Algoritmos :",
        ] + [f"     [{a.role}] {a.name}" for a in self.model_plan.algorithms] + [
            "", "3. PIPELINE",
            f"   Features : {self.generated_pipeline.meta.get('n_features', '?')}",
            f"   Estimador: {self.generated_pipeline.meta.get('estimator', '?')}",
            "", "4. VALIDACIÓN",
            f"   Score  : {self.validation.mean_score:.4f} ±{self.validation.std_score:.4f}  {bar(self.validation.mean_score*100, 100)}",
            f"   Veredicto: {verdict}",
        ]
        if self.validation.feature_importance:
            lines.append("   Top features:")
            for feat, imp in sorted(self.validation.feature_importance.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"     {feat:30s}: {imp:.4f}")
        if self.llm_interpretation:
            lines += ["", "5. INTERPRETACIÓN AI", thin, f"   {self.llm_interpretation}"]
        if include_code:
            lines += ["", "6. CÓDIGO GENERADO", thin, self.generated_pipeline.code_snippet]
        if self.extra_notes:
            lines += ["", "NOTAS:"] + [f"  * {n}" for n in self.extra_notes]
        lines += ["", sep]
        return "\n".join(lines)


class ReportGenerator:
    def generate(self, filepath, prompt, feasibility, model_plan, generated_pipeline, validation, ask_llm=True) -> LabReport:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        llm_text = ""
        if ask_llm:
            try:
                from ai_models import ask_openai
                summary_text = (
                    f"Viabilidad: {feasibility.viability_index:.1f}/100. "
                    f"Modelo: {', '.join(a.name for a in model_plan.algorithms[:2])}. "
                    f"Validación ({validation.method}): {validation.metric}={validation.mean_score:.4f} "
                    f"({'PASA' if validation.passes else 'NO PASA'}). "
                    f"Top features: {', '.join(list(validation.feature_importance.keys())[:3])}."
                )
                query = f"Eres ASTRA. Interpreta estos resultados del Prediction Lab en 3-4 oraciones claras y accionables: {summary_text}"
                llm_text = ask_openai(query)
            except Exception as e:
                llm_text = f"(Interpretación LLM no disponible: {e})"
        notes = []
        if validation.passes and feasibility.viability_index >= 70:
            notes.append("Modelo aprobado. Puedes guardarlo con ModelStorage.save_model().")
        elif not validation.passes:
            notes.append("Modelo no pasa validación. Revisa recomendaciones de viabilidad.")
        return LabReport(timestamp=ts, filepath=filepath, prompt=prompt, feasibility=feasibility,
            model_plan=model_plan, generated_pipeline=generated_pipeline, validation=validation,
            llm_interpretation=llm_text, extra_notes=notes)


_generator = ReportGenerator()


def generate_report(filepath, prompt, feasibility, model_plan, generated_pipeline, validation, ask_llm=True) -> LabReport:
    return _generator.generate(filepath, prompt, feasibility, model_plan, generated_pipeline, validation, ask_llm)


def cmd_lab_reporte(filepath: str, prompt: str = "", include_code: bool = False) -> str:
    if not filepath:
        return "Uso: lab reporte <archivo.csv> [descripción]"
    try:
        import pandas as pd
        from .prompt_analyzer import analyze_prompt
        from .dataset_analyzer import analyze_dataset
        from .feasibility_engine import check_feasibility
        from .model_planner import plan_models
        from .pipeline_generator import generate_pipeline
        from .validation_engine import validate_models
        df = pd.read_csv(filepath) if filepath.endswith(".csv") else pd.read_excel(filepath)
        spec = analyze_prompt(prompt) if prompt else None
        da = analyze_dataset(df)
        fs = check_feasibility(da, spec)
        if not fs.is_viable:
            return (f"Viabilidad insuficiente ({fs.viability_index:.1f}/100).\n"
                    + "\n".join(f"  - {b}" for b in fs.bottlenecks))
        plan = plan_models(fs, spec)
        gp = generate_pipeline(plan, df)
        val = validate_models(gp, df)
        report = generate_report(filepath, prompt or "", fs, plan, gp, val, ask_llm=True)
        return report.render(include_code=include_code)
    except Exception as e:
        return f"Error generando reporte: {e}"
