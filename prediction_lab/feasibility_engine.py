"""
prediction_lab/feasibility_engine.py — Fase 5.3 (Prediction Lab) ⭐

Componente central del Prediction Lab. Responde la pregunta que decide si
vale la pena seguir: "¿puede construirse un predictor útil con esto?"

Combina el ProblemSpec (5.1 — qué se quiere predecir) con el DatasetReport
(5.2 — qué tan bueno es el dataset disponible) y calcula un Índice de
Viabilidad 0-100 ponderado:

    cantidad de datos   25%
    calidad del dataset 20%
    balance del target  15%
    señal predictiva    20%
    complejidad         10%   (más simple el problema → más viable)
    horizonte           10%   (más claro/realista el horizonte → más viable)

Si viabilidad < 40 → NO procede: explica exactamente qué falta y cómo
mejorarlo, en vez de seguir generando un pipeline condenado a fallar.

API pública:
  assess_feasibility(csv_path, idea, target_variable=None) -> FeasibilityReport
  assess_feasibility_from(problem_spec, dataset_report)     -> FeasibilityReport
  cmd_lab_viabilidad(csv_path, idea)                        -> str
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict

from .prompt_analyzer   import analyze_prompt, ProblemSpec
from .dataset_analyzer  import analyze_dataset, DatasetReport


# ══════════════════════════════════════════════════════════
#  PESOS
# ══════════════════════════════════════════════════════════

WEIGHTS = {
    "datos":        0.25,
    "calidad":      0.20,
    "balance":      0.15,
    "senal":        0.20,
    "complejidad":  0.10,
    "horizonte":    0.10,
}

VIABILITY_THRESHOLD = 40.0


# ══════════════════════════════════════════════════════════
#  FEASIBILITY REPORT
# ══════════════════════════════════════════════════════════

@dataclass
class FeasibilityReport:
    ok:                 bool = True
    error:              Optional[str] = None

    problem_type:       str = "unknown"
    domain:             str = "general"
    target_variable:    Optional[str] = None

    dimension_scores:   Dict[str, float] = field(default_factory=dict)
    weights:            Dict[str, float] = field(default_factory=lambda: dict(WEIGHTS))
    viability_index:    float = 0.0
    is_viable:          bool = False
    verdict:            str = ""

    blocking_issues:    List[str] = field(default_factory=list)
    suggestions:        List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        if not self.ok:
            return f"[FEASIBILITY ENGINE] Error: {self.error}"

        lines = [
            "═" * 62,
            " FEASIBILITY ENGINE — ¿Se puede construir un predictor útil?",
            "═" * 62,
            f" Problema  : {self.problem_type}  |  Dominio: {self.domain}",
            f" Target    : {self.target_variable or '(no identificado)'}",
            "-" * 62,
            " Dimensiones (score x peso):",
        ]
        for dim, score in self.dimension_scores.items():
            w = self.weights.get(dim, 0.0)
            lines.append(f"   {dim:<12}: {score:5.1f}  x {w:.0%} = {score * w:5.1f}")

        lines.append("-" * 62)
        lines.append(f" ÍNDICE DE VIABILIDAD: {self.viability_index:5.1f} / 100")
        lines.append(f" Veredicto: {self.verdict}")

        if self.blocking_issues:
            lines.append("-" * 62)
            lines.append(" 🚫 Por qué NO procede todavía:")
            for issue in self.blocking_issues:
                lines.append(f"   - {issue}")

        if self.suggestions:
            lines.append("-" * 62)
            lines.append(" 💡 Sugerencias para mejorar:")
            for s in self.suggestions:
                lines.append(f"   - {s}")

        lines.append("═" * 62)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  SCORING POR DIMENSIÓN
# ══════════════════════════════════════════════════════════

def _score_datos(n_rows: int) -> float:
    if n_rows <= 0:
        return 0.0
    if n_rows < 100:
        return round(n_rows / 100 * 40, 1)
    if n_rows < 300:
        return round(40 + (n_rows - 100) / 200 * 30, 1)
    if n_rows < 1000:
        return round(70 + (n_rows - 300) / 700 * 20, 1)
    return round(min(90 + (n_rows - 1000) / 9000 * 10, 100.0), 1)


def _score_complejidad(problem_spec: ProblemSpec) -> float:
    base = {
        "classification": 90.0,
        "regression":      85.0,
        "clustering":      70.0,
        "timeseries":      65.0,
        "unknown":         50.0,
    }.get(problem_spec.problem_type, 50.0)

    if len(problem_spec.candidate_features) > 30:
        base -= 15
    elif len(problem_spec.candidate_features) > 15:
        base -= 7

    if problem_spec.domain == "forex":
        base -= 10   # series financieras: ruido alto, señal débil por naturaleza
    elif problem_spec.domain == "general":
        base -= 5

    return round(max(0.0, min(base, 100.0)), 1)


def _score_horizonte(problem_spec: ProblemSpec) -> float:
    if not problem_spec.horizon:
        return 50.0   # ambiguo — se puede asumir un default pero resta certeza

    horizon_lower = problem_spec.horizon.lower()
    long_term_words = ["mes", "meses", "trimestre", "año", "anio", "semestre"]
    short_term_words = ["vela", "velas", "hora", "horas", "día", "dia", "días", "dias"]

    score = 85.0
    if problem_spec.domain == "forex" and any(w in horizon_lower for w in long_term_words):
        # horizonte muy largo para datos intradía de forex -> desalineado
        score -= 30
    if problem_spec.domain == "business" and any(w in horizon_lower for w in short_term_words):
        # horizonte muy corto para un problema de negocio (ventas/churn) -> poco realista
        score -= 15

    return round(max(0.0, min(score, 100.0)), 1)


# ══════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════

def assess_feasibility_from(problem_spec: ProblemSpec, dataset_report: DatasetReport) -> FeasibilityReport:
    """Calcula viabilidad ya con ProblemSpec + DatasetReport en mano (para encadenar en el pipeline)."""
    if not dataset_report.ok:
        return FeasibilityReport(ok=False, error=dataset_report.error)

    # dataset_report.target_variable ya fue validado contra las columnas reales del CSV
    # (ver dataset_analyzer._guess_target / validación) — tiene prioridad sobre el texto
    # crudo que haya extraído el Prompt Analyzer, que puede no ser un nombre de columna real.
    # BUGFIX: el fallback a problem_spec.target_variable también debe validarse contra
    # las columnas reales — si no, un target "sucio" (ej. "algo interesante" extraído
    # por el heurístico de texto libre) se colaba sin pasar por el gate duro de abajo.
    all_columns = set(dataset_report.numeric_cols) | set(dataset_report.non_numeric_cols)
    raw_candidate = problem_spec.target_variable
    validated_candidate = raw_candidate if raw_candidate in all_columns else None
    resolved_target = dataset_report.target_variable or validated_candidate

    # Gate duro: sin variable objetivo no hay forma de validar señal/balance real —
    # no tiene sentido reportar "viable" con métricas calculadas sobre un target inexistente.
    if not resolved_target:
        return FeasibilityReport(
            ok=True,
            problem_type=problem_spec.problem_type,
            domain=problem_spec.domain,
            target_variable=None,
            dimension_scores={},
            viability_index=0.0,
            is_viable=False,
            verdict="NO VIABLE — no se pudo identificar la variable objetivo.",
            blocking_issues=[
                "No se pudo identificar la variable objetivo ni en la idea ni por nombre de columna en el dataset. "
                "Indícala explícitamente, ej: lab dataset <csv> <nombre_columna_target>, o reformula la idea "
                "mencionando claramente qué quieres predecir."
            ],
            suggestions=[
                f"Columnas disponibles en el dataset: {', '.join(dataset_report.numeric_cols + dataset_report.non_numeric_cols)}"
            ],
        )

    dims = {
        "datos":       _score_datos(dataset_report.n_rows),
        "calidad":     dataset_report.overall_quality,
        "balance":     dataset_report.quality_scores.get("balance", 100.0),
        "senal":       dataset_report.quality_scores.get("signal", 40.0),
        "complejidad": _score_complejidad(problem_spec),
        "horizonte":   _score_horizonte(problem_spec),
    }

    viability = sum(dims[d] * WEIGHTS[d] for d in WEIGHTS)
    viability = round(viability, 1)
    is_viable = viability >= VIABILITY_THRESHOLD

    if viability >= 80:
        verdict = "MUY VIABLE — dataset e idea alineados, se puede proceder con confianza."
    elif viability >= 60:
        verdict = "VIABLE — se puede construir un predictor razonable."
    elif viability >= VIABILITY_THRESHOLD:
        verdict = "VIABLE CON RESERVAS — procede, pero revisa las sugerencias antes de confiar en el modelo."
    else:
        verdict = "NO VIABLE — el dataset o la idea necesitan trabajo antes de construir un pipeline."

    blocking_issues = []
    suggestions = []

    if dims["datos"] < 40:
        msg = f"Muy pocas filas ({dataset_report.n_rows}) — se recomienda un mínimo de 300 para entrenar con confianza."
        (blocking_issues if not is_viable else suggestions).append(msg)
    if dims["calidad"] < 50:
        msg = f"Calidad general del dataset baja ({dataset_report.overall_quality:.0f}/100) — revisa NaN, outliers y multicolinealidad (ver reporte de Dataset Analyzer)."
        (blocking_issues if not is_viable else suggestions).append(msg)
    if dims["balance"] < 50:
        msg = "El target está muy desbalanceado — considera SMOTE, undersampling, o ajustar el umbral de decisión."
        (blocking_issues if not is_viable else suggestions).append(msg)
    if dims["senal"] < 40:
        msg = "Ninguna feature muestra correlación fuerte con el target — la señal predictiva es débil, considera agregar features nuevas o revisar la hipótesis."
        (blocking_issues if not is_viable else suggestions).append(msg)
    if dims["horizonte"] < 60:
        if not problem_spec.horizon:
            suggestions.append("El horizonte temporal no fue especificado — se recomienda indicarlo explícitamente (ej. '10 velas', '3 meses').")
        else:
            suggestions.append(f"El horizonte '{problem_spec.horizon}' no está bien alineado con el dominio '{problem_spec.domain}' — revisa si es razonable dada la granularidad del dataset.")
    if not blocking_issues and viability < VIABILITY_THRESHOLD:
        blocking_issues.append("La combinación de factores (datos + calidad + señal) no alcanza el umbral mínimo de viabilidad (40/100).")

    return FeasibilityReport(
        ok=True,
        problem_type=problem_spec.problem_type,
        domain=problem_spec.domain,
        target_variable=resolved_target,
        dimension_scores=dims,
        viability_index=viability,
        is_viable=is_viable,
        verdict=verdict,
        blocking_issues=blocking_issues,
        suggestions=suggestions,
    )


def assess_feasibility(csv_path: str, idea: str, target_variable: Optional[str] = None) -> FeasibilityReport:
    """
    Punto de entrada de alto nivel: idea en lenguaje natural + CSV -> viabilidad.
    Encadena internamente prompt_analyzer -> dataset_analyzer -> feasibility scoring.
    """
    problem_spec = analyze_prompt(idea)
    dataset_report = analyze_dataset(
        csv_path,
        target_variable=target_variable,
        problem_spec=problem_spec,
    )
    return assess_feasibility_from(problem_spec, dataset_report)


def cmd_lab_viabilidad(csv_path: str, idea: str, target_variable=None) -> str:
    """Comando CLI: 'lab viabilidad <csv> \"<idea>\" [target]' — para wiring en main.py.
    target_variable es opcional: úsalo cuando el nombre de la columna objetivo
    no se pueda inferir de la idea ni por heurística de nombres de columna."""
    if not csv_path or not idea:
        return 'Uso: lab viabilidad <archivo.csv> "<describe tu idea>" [columna_target]'
    report = assess_feasibility(csv_path, idea, target_variable=target_variable)
    return report.summary()
