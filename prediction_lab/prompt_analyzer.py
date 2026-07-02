"""
prediction_lab/prompt_analyzer.py — Fase 5.1 (Prediction Lab)

Interpreta la idea del usuario en lenguaje natural y la convierte en un
ProblemSpec estructurado: tipo de problema, variable objetivo, features
candidatas, horizonte temporal y tipo de salida esperada.

Es el primer paso del pipeline de Prediction Lab — todo lo que viene
después (Dataset Analyzer, Feasibility Engine, Model Planner...) consume
el ProblemSpec que este módulo produce.

Dos modos de extracción:
  1. LLM (Groq/Llama-3.3-70B) — preciso, entiende matices, requiere API key.
  2. Heurístico (regex/keywords) — fallback offline, siempre disponible.

Si el LLM falla o no hay API key, se degrada automáticamente al heurístico
(mismo patrón que el resto de ASTRA: nunca romper, siempre responder algo útil).

API pública:
  analyze_prompt(idea, dataset_columns=None) -> ProblemSpec
  cmd_lab_analiza(idea)                      -> str   (para main.py / _print_result)
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List


# ══════════════════════════════════════════════════════════
#  PROBLEM SPEC
# ══════════════════════════════════════════════════════════

@dataclass
class ProblemSpec:
    raw_idea:           str
    problem_type:       str            # classification | regression | timeseries | clustering | unknown
    domain:             str            # forex | business | general
    target_variable:    Optional[str]
    candidate_features: List[str]      = field(default_factory=list)
    horizon:            Optional[str]  = None     # ej. "10 velas", "3 meses", "próximo trimestre"
    expected_output:    str            = ""       # qué debe devolver el modelo final
    confidence:         float          = 0.5      # 0-1, qué tan seguro está el analyzer de su propia lectura
    notes:              str            = ""       # ambigüedades, advertencias, supuestos hechos
    extracted_via:      str            = "heuristic"  # "llm" | "heuristic"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def summary(self) -> str:
        feats = ", ".join(self.candidate_features) if self.candidate_features else "(sin especificar — se detectarán del dataset)"
        lines = [
            "═" * 60,
            " PROMPT ANALYZER — ProblemSpec",
            "═" * 60,
            f" Idea original    : {self.raw_idea}",
            f" Tipo de problema : {self.problem_type}",
            f" Dominio          : {self.domain}",
            f" Variable objetivo: {self.target_variable or '(no identificada — Dataset Analyzer la inferirá)'}",
            f" Features cand.   : {feats}",
            f" Horizonte        : {self.horizon or '(no especificado)'}",
            f" Salida esperada  : {self.expected_output or '(no especificada)'}",
            f" Confianza        : {self.confidence:.0%}  (extraído vía {self.extracted_via})",
        ]
        if self.notes:
            lines.append(f" Notas            : {self.notes}")
        lines.append("═" * 60)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  MODO 1 — EXTRACCIÓN VÍA LLM
# ══════════════════════════════════════════════════════════

_EXTRACTION_SYSTEM_PROMPT = """\
Eres un analista técnico de Machine Learning. Tu única tarea es leer la \
descripción de un problema predictivo en lenguaje natural y devolver \
EXCLUSIVAMENTE un objeto JSON (sin texto adicional, sin markdown, sin \
explicaciones) con esta forma exacta:

{
  "problem_type": "classification" | "regression" | "timeseries" | "clustering" | "unknown",
  "domain": "forex" | "business" | "general",
  "target_variable": "<nombre de la variable a predecir, o null si no está clara>",
  "candidate_features": ["<feature1>", "<feature2>", ...],
  "horizon": "<horizonte temporal mencionado, o null>",
  "expected_output": "<qué debe devolver el modelo, en una frase corta>",
  "confidence": <número entre 0 y 1, qué tan clara/completa está la idea>,
  "notes": "<ambigüedades, supuestos que tuviste que hacer, o vacío>"
}

Reglas:
- "classification" si se predice una categoría/etiqueta discreta (ej. sube/baja, compra/venta, churn sí/no).
- "regression" si se predice un valor numérico continuo (ej. precio, monto, ingreso futuro).
- "timeseries" si el foco es la evolución temporal de una serie (ej. forecast de ventas, demanda).
- "clustering" si se busca agrupar/segmentar sin una variable objetivo clara.
- Si la idea es ambigua entre dos tipos, elige el más probable y bájale la "confidence".
- "domain" = "forex" si menciona pares de divisas, trading, velas, pips, indicadores técnicos.
- "domain" = "business" si menciona ventas, clientes, PYME, ingresos, inventario, churn.
- "domain" = "general" en cualquier otro caso.
- candidate_features: solo lista las que el usuario menciona explícita o implícitamente. Si no menciona ninguna, deja la lista vacía — el Dataset Analyzer las inferirá del CSV.
- Nunca inventes una variable objetivo que no esté sugerida en el texto — usa null.
"""


def _try_llm_extraction(idea: str, dataset_columns: Optional[List[str]] = None) -> Optional[dict]:
    """
    Intenta usar Groq/Llama para extraer el ProblemSpec.
    Devuelve None si falla por cualquier motivo (sin key, error de red, JSON inválido, etc.)
    — el caller hace fallback automático al modo heurístico.
    """
    try:
        from ai_models import _get_client, _active_model
    except Exception:
        return None

    try:
        client = _get_client()
        model  = _active_model()

        user_msg = f'Idea del usuario: "{idea}"'
        if dataset_columns:
            user_msg += f"\n\nColumnas disponibles en el dataset adjunto: {dataset_columns}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()

        # Extraer el primer bloque {...} por si el modelo agrega texto extra
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        data = json.loads(match.group(0))
        return data

    except Exception:
        return None


# ══════════════════════════════════════════════════════════
#  MODO 2 — EXTRACCIÓN HEURÍSTICA (fallback offline)
# ══════════════════════════════════════════════════════════

_CLASSIFICATION_HINTS = [
    "sube o baja", "sube/baja", "compra o venta", "compra/venta", "buy or sell",
    "sí o no", "si o no", "clasificar", "clasificación", "categoría", "categoria",
    "churn", "abandono", "fraude", "spam", "detectar si", "predecir si",
    "va a subir", "va a bajar", "aprobar o rechazar",
]

_REGRESSION_HINTS = [
    "cuánto", "cuanto", "qué precio", "que precio", "valor de", "monto",
    "cuántas unidades", "cuantas unidades", "ingreso futuro", "estimar el precio",
    "predecir el precio", "predecir el valor",
]

_TIMESERIES_HINTS = [
    "próximos días", "proximos dias", "próximas semanas", "proximas semanas",
    "próximos meses", "proximos meses", "serie temporal", "forecast",
    "pronóstico", "pronostico", "tendencia futura", "próximo trimestre",
    "proximo trimestre", "demanda futura", "próximas velas", "proximas velas",
]

_CLUSTERING_HINTS = [
    "agrupar", "segmentar", "segmentación", "segmentacion", "clusters",
    "grupos de clientes", "patrones ocultos", "sin etiqueta",
]

_FOREX_HINTS = [
    "forex", "par de divisas", "eurusd", "gbpusd", "usdjpy", "xauusd",
    "trading", "velas", "pip", "pips", "rsi", "macd", "bollinger", "ema",
    "soporte y resistencia", "análisis técnico", "analisis tecnico",
]

_BUSINESS_HINTS = [
    "pyme", "pymes", "empresa", "negocio", "ventas", "clientes", "churn",
    "inventario", "ingresos", "facturación", "facturacion", "kpi",
    "flujo de caja", "rentabilidad",
]


def _contains_any(text: str, hints: List[str]) -> bool:
    return any(h in text for h in hints)


def _detect_problem_type(text: str) -> str:
    scores = {
        "timeseries":     sum(h in text for h in _TIMESERIES_HINTS),
        "classification":  sum(h in text for h in _CLASSIFICATION_HINTS),
        "regression":      sum(h in text for h in _REGRESSION_HINTS),
        "clustering":      sum(h in text for h in _CLUSTERING_HINTS),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def _detect_domain(text: str) -> str:
    if _contains_any(text, _FOREX_HINTS):
        return "forex"
    if _contains_any(text, _BUSINESS_HINTS):
        return "business"
    return "general"


def _extract_target_variable(text: str) -> Optional[str]:
    """Busca patrones tipo 'predecir X', 'quiero predecir X', 'el objetivo es X'."""
    patterns = [
        r"predecir (?:el |la |los |las )?([a-záéíóúñ_ ]{3,40})(?:\.|,|$)",
        r"objetivo es ([a-záéíóúñ_ ]{3,40})(?:\.|,|$)",
        r"quiero saber ([a-záéíóúñ_ ]{3,40})(?:\.|,|$)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_horizon(text: str) -> Optional[str]:
    m = re.search(
        r"(pr[oó]xim[oa]s?\s+\d+\s+\w+|\d+\s+(?:d[ií]as|semanas|meses|velas|horas)|"
        r"pr[oó]xim[oa]\s+trimestre|pr[oó]xim[oa]\s+mes|pr[oó]xim[oa]\s+semana)",
        text,
    )
    return m.group(0) if m else None


def _heuristic_extraction(idea: str, dataset_columns: Optional[List[str]] = None) -> dict:
    text = idea.lower().strip()

    problem_type = _detect_problem_type(text)
    domain       = _detect_domain(text)
    target       = _extract_target_variable(text)
    horizon      = _extract_horizon(text)

    # Si el usuario menciona columnas del dataset directamente en el texto, úsalas como candidatas
    candidate_features = []
    if dataset_columns:
        for col in dataset_columns:
            if col.lower() in text:
                candidate_features.append(col)

    notes = []
    if problem_type == "unknown":
        notes.append("no se detectó un tipo de problema claro por keywords — revisar manualmente")
    if not target:
        notes.append("variable objetivo no identificada — el Dataset Analyzer intentará inferirla")

    confidence = 0.35  # el heurístico siempre es menos confiable que el LLM
    if problem_type != "unknown":
        confidence += 0.15
    if target:
        confidence += 0.15
    if horizon:
        confidence += 0.1

    return {
        "problem_type":       problem_type,
        "domain":             domain,
        "target_variable":    target,
        "candidate_features": candidate_features,
        "horizon":            horizon,
        "expected_output":    f"Predicción de tipo {problem_type}" if problem_type != "unknown" else "",
        "confidence":         round(min(confidence, 0.75), 2),
        "notes":              "; ".join(notes),
    }


# ══════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════

def analyze_prompt(idea: str, dataset_columns: Optional[List[str]] = None) -> ProblemSpec:
    """
    Analiza una idea en lenguaje natural y devuelve un ProblemSpec.

    Parameters
    ----------
    idea            : descripción del usuario, ej. "quiero predecir si EURUSD sube
                      o baja en las próximas 10 velas usando RSI y MACD"
    dataset_columns : opcional — nombres de columnas del CSV adjunto, si ya se conoce.
                      Ayuda a anclar candidate_features y detectar el target real.

    Returns
    -------
    ProblemSpec — intenta LLM primero, degrada a heurístico si falla.
    """
    idea = (idea or "").strip()
    if not idea:
        return ProblemSpec(
            raw_idea=idea,
            problem_type="unknown",
            domain="general",
            target_variable=None,
            confidence=0.0,
            notes="idea vacía — no se puede analizar",
            extracted_via="heuristic",
        )

    llm_data = _try_llm_extraction(idea, dataset_columns=dataset_columns)

    if llm_data is not None:
        try:
            return ProblemSpec(
                raw_idea=idea,
                problem_type=llm_data.get("problem_type", "unknown") or "unknown",
                domain=llm_data.get("domain", "general") or "general",
                target_variable=llm_data.get("target_variable") or None,
                candidate_features=llm_data.get("candidate_features") or [],
                horizon=llm_data.get("horizon") or None,
                expected_output=llm_data.get("expected_output", "") or "",
                confidence=float(llm_data.get("confidence", 0.6) or 0.6),
                notes=llm_data.get("notes", "") or "",
                extracted_via="llm",
            )
        except Exception:
            pass  # cae al heurístico si el JSON venía con tipos inesperados

    # Fallback heurístico
    h = _heuristic_extraction(idea, dataset_columns=dataset_columns)
    return ProblemSpec(
        raw_idea=idea,
        problem_type=h["problem_type"],
        domain=h["domain"],
        target_variable=h["target_variable"],
        candidate_features=h["candidate_features"],
        horizon=h["horizon"],
        expected_output=h["expected_output"],
        confidence=h["confidence"],
        notes=h["notes"],
        extracted_via="heuristic",
    )


def cmd_lab_analiza(idea: str) -> str:
    """Comando CLI: 'lab analiza "<idea>"' — para wiring en main.py."""
    if not idea or not idea.strip():
        return "Uso: lab analiza \"<describe tu idea de predicción>\""
    spec = analyze_prompt(idea)
    return spec.summary()
