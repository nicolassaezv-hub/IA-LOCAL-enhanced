"""
ASTRA — Fase 5.3: Feasibility Engine ⭐

COMPONENTE CENTRAL de Prediction Lab.

Responde: "¿puede construirse un predictor útil con esto?"

Calcula Índice de Viabilidad 0-100 ponderando:
  25% - Cantidad de datos (rows)
  20% - Calidad (completeness)
  15% - Balance de target
  20% - Señal predictiva (varianza/correlación)
  10% - Complejidad
  10% - Horizonte

Si viabilidad < 40% → explica qué falta y NO procede.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from .dataset_analyzer import DatasetAnalyzer, DatasetAnalysis
from .prompt_analyzer import ProblemSpec


# ═══════════════════════════════════════════════════════════════════════
#  TIPOS
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FeasibilityScore:
    """Resultado de análisis de viabilidad"""
    viability_index: float  # 0-100
    is_viable: bool  # > 40%
    problem_type: str
    dataset_analysis: DatasetAnalysis
    scores: Dict[str, float]  # {"data_volume": 75, "quality": 60, ...}
    bottlenecks: List[str]  # qué falta
    recommendations: List[str]  # qué hacer
    estimated_effort: str  # "low", "medium", "high"


# ═══════════════════════════════════════════════════════════════════════
#  FEASIBILITY ENGINE
# ═══════════════════════════════════════════════════════════════════════

class FeasibilityEngine:
    """Evalúa viabilidad de construir un predictor con datos dados"""

    def __init__(self):
        self.dataset_analyzer = DatasetAnalyzer()

    def assess(
        self,
        csv_path: str,
        problem_spec: ProblemSpec,
    ) -> FeasibilityScore:
        """Evalúa viabilidad de un proyecto predictivo"""

        # Analizar dataset
        dataset_analysis = self.dataset_analyzer.analyze(
            csv_path,
            target_col=problem_spec.target_variable
        )

        # Calcular scores por dimensión
        scores = self._calculate_scores(dataset_analysis, problem_spec)

        # Score ponderado
        viability_index = (
            scores["data_volume"] * 0.25 +
            scores["quality"] * 0.20 +
            scores["target_balance"] * 0.15 +
            scores["signal"] * 0.20 +
            scores["complexity"] * 0.10 +
            scores["horizon"] * 0.10
        )

        # Detectar cuellos de botella
        bottlenecks = self._detect_bottlenecks(scores, dataset_analysis)

        # Generar recomendaciones
        recommendations = self._generate_recommendations(bottlenecks, dataset_analysis)

        # Estimar esfuerzo
        effort = self._estimate_effort(viability_index, problem_spec.problem_type)

        # Determinar viabilidad
        is_viable = viability_index >= 40.0

        return FeasibilityScore(
            viability_index=float(viability_index),
            is_viable=is_viable,
            problem_type=problem_spec.problem_type,
            dataset_analysis=dataset_analysis,
            scores=scores,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            estimated_effort=effort,
        )

    def _calculate_scores(
        self,
        analysis: DatasetAnalysis,
        spec: ProblemSpec
    ) -> Dict[str, float]:
        """Calcula scores por dimensión"""
        
        scores = {}

        # 1. Data Volume (25%)
        rows = analysis.shape[0]
        cols = analysis.shape[1]
        
        # Necesitamos N mínimo según complejidad esperada
        # Simple: 100+ filas, Medium: 500+ filas, Complex: 1000+ filas
        min_rows = 100 if cols < 5 else (500 if cols < 20 else 1000)
        volume_score = min(100, (rows / min_rows) * 100) if rows >= 50 else (rows / 50 * 50)
        scores["data_volume"] = float(volume_score)

        # 2. Quality (20%) - % NaN y duplicados
        null_pct = analysis.null_summary["null_pct"]
        quality_score = max(0, 100 - null_pct * 2)  # Penalizar 2x por cada % NaN
        scores["quality"] = float(quality_score)

        # 3. Target Balance (15%)
        balance_score = 50  # neutral
        if analysis.target_balance:
            if spec.problem_type == "classification":
                # Si classification, evaluar balance
                imbalance_ratio = analysis.target_balance.get("imbalance_ratio", 1.0)
                if imbalance_ratio < 1.5:
                    balance_score = 100  # Perfect balance
                elif imbalance_ratio < 3:
                    balance_score = 75  # Good
                elif imbalance_ratio < 10:
                    balance_score = 50  # Acceptable
                else:
                    balance_score = 25  # Poor
            else:
                # Si regression, verificar que no sea constante
                if len(analysis.target_balance) > 1:
                    balance_score = 100
                else:
                    balance_score = 0  # Target casi constante

        scores["target_balance"] = float(balance_score)

        # 4. Signal (20%) - varianza y correlaciones
        signal_score = 0
        numeric_cols = [c for c in analysis.columns if c.dtype.startswith("int") or c.dtype.startswith("float")]
        
        if len(numeric_cols) > 1:
            # Contar features con varianza > 0
            features_with_signal = len(numeric_cols)
            signal_score = min(100, (features_with_signal / max(cols, 1)) * 100)
            
            # Bonus si hay correlaciones
            high_corr_count = len(analysis.correlations.get("high_correlations", []))
            if high_corr_count > 0:
                signal_score = min(100, signal_score + 10)
        
        scores["signal"] = float(signal_score)

        # 5. Complexity (10%) - número de features
        # 5-30 features es óptimo; menos es simple, más es complejo
        complexity_score = 100 if 5 <= cols <= 30 else (100 - abs(cols - 17.5) / 17.5 * 50)
        complexity_score = max(0, complexity_score)
        scores["complexity"] = float(complexity_score)

        # 6. Horizon (10%) - ratio filas / features
        ratio = rows / max(cols, 1)
        # Necesitamos mínimo 10 filas por feature
        horizon_score = min(100, (ratio / 10) * 100)
        scores["horizon"] = float(horizon_score)

        return scores

    def _detect_bottlenecks(
        self,
        scores: Dict[str, float],
        analysis: DatasetAnalysis
    ) -> List[str]:
        """Detecta qué limita la viabilidad"""
        bottlenecks = []

        if scores["data_volume"] < 50:
            bottlenecks.append("📊 Volumen de datos insuficiente")

        if scores["quality"] < 50:
            bottlenecks.append("🔍 Baja calidad de datos (muchos NaN)")

        if scores["target_balance"] < 30:
            bottlenecks.append("⚖️  Target muy desbalanceado")

        if scores["signal"] < 30:
            bottlenecks.append("📈 Baja señal predictiva (poca varianza)")

        if scores["complexity"] < 30:
            bottlenecks.append("🔧 Datos muy complejos (demasiadas features)")

        if scores["horizon"] < 50:
            bottlenecks.append("⏱️  Ratio datos/features bajo (riesgo overfitting)")

        return bottlenecks

    def _generate_recommendations(
        self,
        bottlenecks: List[str],
        analysis: DatasetAnalysis
    ) -> List[str]:
        """Genera acciones concretas para mejorar viabilidad"""
        recs = []

        if any("volumen" in b.lower() for b in bottlenecks):
            recs.append("💡 Recolectar más datos (objetivo: 1000+ filas)")

        if any("calidad" in b.lower() for b in bottlenecks):
            recs.append("💡 Aplicar imputación o remover columnas muy vacías")

        if any("desbalanceado" in b.lower() for b in bottlenecks):
            recs.append("💡 Usar SMOTE o pesos de clase en el modelo")

        if any("señal" in b.lower() for b in bottlenecks):
            recs.append("💡 Crear nuevas features o usar feature engineering")

        if any("complejos" in b.lower() for b in bottlenecks):
            recs.append("💡 Seleccionar features más relevantes (eliminar colineales)")

        if any("ratio" in b.lower() for b in bottlenecks):
            recs.append("💡 Reducir número de features o aumentar datos")

        # Recommendations generales
        if analysis.recommendations:
            recs.extend([f"💡 {r}" for r in analysis.recommendations])

        return recs[:5]  # Top 5

    def _estimate_effort(self, viability: float, problem_type: str) -> str:
        """Estima esfuerzo de implementación"""
        if viability < 40:
            return "infeasible"
        elif viability < 60:
            return "high"
        elif viability < 75:
            return "medium"
        else:
            return "low"


# ═══════════════════════════════════════════════════════════════════════
#  FUNCIONES DE CONVENIENCIA
# ═══════════════════════════════════════════════════════════════════════

_engine = None

def get_engine() -> FeasibilityEngine:
    global _engine
    if _engine is None:
        _engine = FeasibilityEngine()
    return _engine


def calculate_feasibility(
    csv_path: str,
    problem_spec: ProblemSpec,
) -> FeasibilityScore:
    """Calcula viabilidad de un proyecto predictivo"""
    return get_engine().assess(csv_path, problem_spec)
