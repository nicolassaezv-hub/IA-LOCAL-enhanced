"""
prediction_lab/prompt_analyzer.py — ASTRA Phase 5.1

Interpreta una idea del usuario en lenguaje natural y extrae un ProblemSpec
estructurado: tipo de problema, variable objetivo, features candidatas,
horizonte temporal y tipo de salida esperada.

CLI: lab analiza "<idea>"
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProblemSpec:
    """Especificación estructurada del problema de predicción."""
    raw_prompt: str
    problem_type: str           # "classification" | "regression" | "timeseries" | "anomaly"
    target_column: Optional[str]
    candidate_features: List[str]
    horizon: Optional[int]
    output_type: str            # "binary" | "multiclass" | "continuous" | "sequence"
    domain: str                 # "forex" | "business" | "generic"
    confidence: float
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Problema    : {self.problem_type} ({self.output_type})",
            f"Target      : {self.target_column or 'no detectado'}",
            f"Features    : {', '.join(self.candidate_features) or 'no detectadas'}",
            f"Horizonte   : {self.horizon or 'no aplica'}",
            f"Dominio     : {self.domain}",
            f"Confianza   : {self.confidence:.0%}",
        ]
        if self.notes:
            lines.append("Notas       : " + "; ".join(self.notes))
        return "\n".join(lines)


_CLASSIFICATION_KW = [
    "clasificar", "clasificación", "predecir si", "detectar si",
    "identify", "classify", "predict whether", "is it", "es un", "es una",
    "comprar", "vender", "buy", "sell", "subir", "bajar", "alza", "baja",
    "bueno", "malo", "aprobado", "rechazado", "churn", "fraude", "spam",
    "default", "impago",
]
_REGRESSION_KW = [
    "predecir precio", "predecir valor", "cuánto", "cuanto", "estimar",
    "forecast price", "predict price", "predict value", "regresión", "regression",
]
_TIMESERIES_KW = [
    "serie temporal", "time series", "próximo candle", "próxima vela",
    "próximos n", "next candle", "forecast", "pronosticar", "proyectar",
    "tendencia", "trend", "eurusd", "gbpusd", "usdjpy", "xauusd",
    "ventas futuras", "demanda futura",
]
_ANOMALY_KW = [
    "anomalía", "anomalia", "outlier", "detección de fraude",
    "fraud detection", "inusual", "unusual", "atípico",
]
_FOREX_KW = [
    "eurusd", "gbpusd", "usdjpy", "xauusd", "audusd", "usdcad",
    "forex", "fx", "par", "divisa", "pips", "candle", "vela",
    "buy", "sell", "comprar", "vender", "señal", "signal",
]
_BUSINESS_KW = [
    "ventas", "sales", "revenue", "ingresos", "clientes", "churn",
    "margen", "margin", "profit", "ganancia", "pyme", "negocio", "empresa",
]
_TARGET_PATTERNS = [
    r"predecir\s+(?:el\s+|la\s+)?(\w+)",
    r"predict\s+(?:the\s+)?(\w+)",
    r"clasificar\s+(?:el\s+|la\s+)?(\w+)",
    r"columna\s+'?\"?(\w+)'?\"?",
    r"target[:\s]+'?\"?(\w+)'?\"?",
]
_FEATURE_PATTERNS = [
    r"usando\s+([\w\s,]+)",
    r"con\s+(?:las\s+columnas?\s+)?([\w\s,]+)",
    r"features?[:\s]+([\w\s,]+)",
    r"basado\s+en\s+([\w\s,]+)",
]
_HORIZON_PATTERN = re.compile(
    r"(?:próxim[oa]s?\s+|next\s+)(\d+)\s*(?:candle|vela|hora|day|día|step|paso)",
    re.IGNORECASE,
)


class PromptAnalyzer:
    def analyze(self, text: str) -> ProblemSpec:
        low = text.lower()
        problem_type, output_type, confidence = self._detect_type(low)
        domain = self._detect_domain(low)
        target = self._extract_target(low)
        features = self._extract_features(low)
        horizon = self._extract_horizon(text)
        notes = self._build_notes(problem_type, target, features, horizon, low)
        if target:
            confidence = min(1.0, confidence + 0.15)
        if features:
            confidence = min(1.0, confidence + 0.10)
        return ProblemSpec(
            raw_prompt=text, problem_type=problem_type, target_column=target,
            candidate_features=features, horizon=horizon, output_type=output_type,
            domain=domain, confidence=confidence, notes=notes,
        )

    def _detect_type(self, low):
        scores = {
            "timeseries":     sum(1 for k in _TIMESERIES_KW if k in low),
            "classification": sum(1 for k in _CLASSIFICATION_KW if k in low),
            "regression":     sum(1 for k in _REGRESSION_KW if k in low),
            "anomaly":        sum(1 for k in _ANOMALY_KW if k in low),
        }
        best = max(scores, key=scores.get)
        total = sum(scores.values()) or 1
        confidence = min(0.95, scores[best] / total * 1.5 + 0.40)
        output_map = {
            "timeseries": "sequence", "classification": "binary",
            "regression": "continuous", "anomaly": "binary",
        }
        return best, output_map[best], confidence

    def _detect_domain(self, low):
        if sum(1 for k in _FOREX_KW if k in low) >= 2:
            return "forex"
        if sum(1 for k in _BUSINESS_KW if k in low) >= 2:
            return "business"
        return "generic"

    def _extract_target(self, low):
        for pattern in _TARGET_PATTERNS:
            m = re.search(pattern, low)
            if m:
                candidate = m.group(1).strip().split()[0]
                if len(candidate) >= 2:
                    return candidate
        return None

    def _extract_features(self, low):
        for pattern in _FEATURE_PATTERNS:
            m = re.search(pattern, low)
            if m:
                raw = m.group(1)
                parts = [p.strip() for p in re.split(r"[,y\s]+", raw) if len(p.strip()) >= 2]
                if parts:
                    return parts[:8]
        return []

    def _extract_horizon(self, text):
        m = _HORIZON_PATTERN.search(text)
        if m:
            return int(m.group(1))
        m2 = re.search(r"(\d+)\s*per[ií]odos?", text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
        return None

    def _build_notes(self, ptype, target, features, horizon, low):
        notes = []
        if not target:
            notes.append("Target no detectado — se inferirá del dataset")
        if not features:
            notes.append("Features no especificadas — se usarán todas las columnas disponibles")
        if ptype == "timeseries" and horizon is None:
            notes.append("Horizonte no especificado — se usará 1 por defecto")
        return notes


_analyzer = PromptAnalyzer()


def analyze_prompt(text: str) -> ProblemSpec:
    return _analyzer.analyze(text)


def cmd_lab_analiza(text: str) -> str:
    if not text or len(text.strip()) < 5:
        return "Uso: lab analiza \"<descripción del problema>\""
    spec = analyze_prompt(text)
    return (
        f"\n{'═' * 56}\n"
        f"  ASTRA Prediction Lab — Análisis de Problema\n"
        f"{'═' * 56}\n"
        f"{spec.summary()}\n"
        f"{'═' * 56}"
    )
