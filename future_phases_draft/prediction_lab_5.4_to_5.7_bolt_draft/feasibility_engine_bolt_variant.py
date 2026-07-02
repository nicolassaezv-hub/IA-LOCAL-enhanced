"""
prediction_lab/feasibility_engine.py — ASTRA Phase 5.3

Calcula Índice de Viabilidad (0-100):
  25% volumen · 20% calidad · 15% balance · 20% señal · 10% complejidad · 10% horizonte
Si viabilidad < 40 → explica qué falta y NO procede.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .dataset_analyzer import DatasetAnalysis, DatasetAnalyzer, analyze_dataset
from .prompt_analyzer import ProblemSpec


@dataclass
class FeasibilityScore:
    viability_index: float
    is_viable: bool
    problem_type: str
    dataset_analysis: DatasetAnalysis
    scores: Dict[str, float]
    bottlenecks: List[str]
    recommendations: List[str]
    estimated_effort: str

    def summary(self) -> str:
        bar_len = 30
        filled = int(self.viability_index / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        verdict = "VIABLE" if self.is_viable else "NO VIABLE"
        lines = [
            f"Índice de Viabilidad : {self.viability_index:.1f}/100  [{bar}]",
            f"Veredicto            : {verdict}",
            f"Esfuerzo estimado    : {self.estimated_effort}",
            "", "Sub-scores:",
        ]
        labels = {
            "data_volume": "  Volumen de datos", "data_quality": "  Calidad de datos",
            "target_balance": "  Balance de target", "predictive_signal": "  Señal predictiva",
            "structural_complexity": "  Complejidad", "horizon_fit": "  Ajuste de horizonte",
        }
        for k, label in labels.items():
            v = self.scores.get(k, 0)
            sub_bar = "█" * int(v / 10) + "░" * (10 - int(v / 10))
            lines.append(f"{label:30s}: {v:5.1f}/100  [{sub_bar}]")
        if self.bottlenecks:
            lines += ["", "Problemas detectados:"]
            lines += [f"  - {b}" for b in self.bottlenecks]
        if self.recommendations:
            lines += ["", "Recomendaciones:"]
            lines += [f"  + {r}" for r in self.recommendations]
        return "\n".join(lines)


_WEIGHTS = {
    "data_volume": 0.25, "data_quality": 0.20, "target_balance": 0.15,
    "predictive_signal": 0.20, "structural_complexity": 0.10, "horizon_fit": 0.10,
}


class FeasibilityEngine:
    def evaluate(self, dataset_analysis: DatasetAnalysis, problem_spec: Optional[ProblemSpec] = None) -> FeasibilityScore:
        scores = {
            "data_volume":           self._score_volume(dataset_analysis),
            "data_quality":          self._score_quality(dataset_analysis),
            "target_balance":        self._score_balance(dataset_analysis),
            "predictive_signal":     self._score_signal(dataset_analysis),
            "structural_complexity": self._score_complexity(dataset_analysis),
            "horizon_fit":           self._score_horizon(dataset_analysis, problem_spec),
        }
        index = round(sum(scores[k] * w for k, w in _WEIGHTS.items()), 2)
        is_viable = index >= 40.0
        bottlenecks = self._find_bottlenecks(scores, dataset_analysis)
        recommendations = self._build_recommendations(scores, dataset_analysis, problem_spec)
        effort = "low" if index >= 75 and dataset_analysis.rows >= 2000 else ("medium" if index >= 50 else "high")
        ptype = problem_spec.problem_type if problem_spec else "unknown"
        return FeasibilityScore(
            viability_index=index, is_viable=is_viable, problem_type=ptype,
            dataset_analysis=dataset_analysis, scores=scores, bottlenecks=bottlenecks,
            recommendations=recommendations, estimated_effort=effort,
        )

    def evaluate_from_file(self, filepath: str, problem_spec=None, target_col=None) -> FeasibilityScore:
        analysis = analyze_dataset(filepath, target_col)
        return self.evaluate(analysis, problem_spec)

    def _score_volume(self, da):
        r = da.rows
        if r >= 5000: return 100.0
        if r >= 2000: return 85.0
        if r >= 1000: return 70.0
        if r >= 500:  return 50.0
        if r >= 200:  return 30.0
        return 10.0

    def _score_quality(self, da):
        score = 100.0 - da.missing_pct_overall * 1.5
        avg_outlier = sum(p.outlier_pct for p in da.column_profiles if p.is_numeric) / max(1, len(da.numeric_cols))
        score -= avg_outlier * 0.8
        score -= (da.duplicate_rows / max(1, da.rows)) * 50
        return max(0.0, min(100.0, round(score, 2)))

    def _score_balance(self, da):
        if da.class_balance is None: return 60.0
        values = list(da.class_balance.values())
        if len(values) < 2: return 20.0
        minority = min(values)
        if minority >= 0.40: return 100.0
        if minority >= 0.25: return 75.0
        if minority >= 0.15: return 55.0
        if minority >= 0.05: return 35.0
        return 15.0

    def _score_signal(self, da): return round(da.predictive_signal * 100, 2)

    def _score_complexity(self, da):
        cols = da.columns
        if cols <= 10: return 100.0
        if cols <= 30: return 85.0
        if cols <= 60: return 65.0
        if cols <= 100: return 45.0
        return 30.0

    def _score_horizon(self, da, spec):
        if spec is None: return 70.0
        if spec.problem_type == "timeseries":
            if not da.is_timeseries: return 20.0
            h = spec.horizon or 1
            if h <= 5: return 90.0
            if h <= 20: return 70.0
            if h <= 50: return 50.0
            return 30.0
        return 80.0

    def _find_bottlenecks(self, scores, da):
        issues = []
        if scores["data_volume"] < 40:
            issues.append(f"Dataset muy pequeño ({da.rows} filas). Necesitas al menos 500.")
        if scores["data_quality"] < 40:
            issues.append(f"Calidad baja (faltantes: {da.missing_pct_overall:.1f}%, duplicados: {da.duplicate_rows}).")
        if scores["target_balance"] < 35:
            issues.append("Target muy desbalanceado (clase minoritaria < 5%).")
        if scores["predictive_signal"] < 25:
            issues.append("Señal predictiva muy baja — features pueden no ser informativas.")
        return issues

    def _build_recommendations(self, scores, da, spec):
        recs = []
        if scores["data_volume"] < 70: recs.append("Aumenta el dataset: descarga más datos históricos")
        if scores["data_quality"] < 60: recs.append("Imputa valores faltantes (media/mediana para numéricas)")
        if da.duplicate_rows > 0: recs.append(f"Elimina {da.duplicate_rows} filas duplicadas")
        if scores["target_balance"] < 55: recs.append("Aplica SMOTE o class_weight='balanced'")
        if scores["predictive_signal"] < 50: recs.append("Agrega features derivadas: lags, rolling stats")
        if not recs: recs.append("El dataset está en buen estado. Procede al planeamiento del modelo.")
        return recs


_engine = FeasibilityEngine()


def check_feasibility(dataset_analysis: DatasetAnalysis, problem_spec=None) -> FeasibilityScore:
    return _engine.evaluate(dataset_analysis, problem_spec)


def check_feasibility_from_file(filepath: str, problem_spec=None, target_col=None) -> FeasibilityScore:
    return _engine.evaluate_from_file(filepath, problem_spec, target_col)


def cmd_lab_viabilidad(filepath: str, prompt: str = "") -> str:
    if not filepath:
        return "Uso: lab viabilidad <archivo.csv> [descripción]"
    try:
        from .prompt_analyzer import analyze_prompt
        spec = analyze_prompt(prompt) if prompt else None
        fs = check_feasibility_from_file(filepath, spec)
        return (
            f"\n{'═' * 60}\n"
            f"  ASTRA Prediction Lab — Análisis de Viabilidad\n"
            f"{'═' * 60}\n"
            f"{fs.summary()}\n"
            f"{'═' * 60}"
        )
    except Exception as e:
        return f"Error en análisis de viabilidad: {e}"
