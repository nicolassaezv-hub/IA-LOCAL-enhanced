"""
evolution/improvement_detector.py — ASTRA Phase 7.2
Detecta qué componentes necesitan mejorar y por qué.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .performance_monitor import PerformanceMonitor, _monitor
from feedback.feedback_analyzer import FeedbackAnalyzer, _analyzer as _fb_analyzer
from feedback.adaptive_thresholds import AdaptiveThresholds, _thresholds

@dataclass
class ImprovementOpportunity:
    opportunity_type: str; component: str; severity: str
    description: str; evidence: List[str]; suggested_action: str; priority: int = 2
    def summary(self) -> str:
        sev_sym = {"critical":"!!!","moderate":"!!","minor":"!"}.get(self.severity, "?")
        lines = [f"{sev_sym} [{self.severity.upper()}] {self.opportunity_type} → {self.component}",
                 f"   {self.description}", f"   Acción: {self.suggested_action}"]
        if self.evidence: lines.append("   Evidencia: " + "; ".join(self.evidence[:3]))
        return "\n".join(lines)

class ImprovementDetector:
    def __init__(self, monitor=_monitor, fb_analyzer=_fb_analyzer, thresholds=_thresholds):
        self.monitor = monitor; self.fb_analyzer = fb_analyzer; self.thresholds = thresholds
    def detect(self) -> List[ImprovementOpportunity]:
        opportunities = []
        history = self.monitor.get_history(20)
        pattern = self.fb_analyzer.analyze(200)
        all_thresh = self.thresholds.get_all()
        if pattern.total_entries >= 5 and pattern.approval_rate < 0.45:
            opportunities.append(ImprovementOpportunity("retrain","forex_predictor","critical",
                f"Tasa de aprobación global muy baja ({pattern.approval_rate:.0%})",
                [f"approval_rate={pattern.approval_rate:.3f}"],
                "Re-entrenar modelos con datos más recientes",priority=1))
        for t, d in pattern.by_type.items():
            ar = d.get("approval_rate", 0); total = d.get("total", 0)
            if total >= 5 and ar < 0.35:
                opportunities.append(ImprovementOpportunity("retrain",t,"moderate",
                    f"Tipo '{t}' tiene baja aprobación ({ar:.0%}) en {total} muestras",
                    [f"approval_rate={ar:.3f}"],f"Re-entrenar pipeline específico para '{t}'",priority=2))
        trend = self.monitor.trend("feedback_approval", 10)
        if trend == "degrading" and len(history) >= 5:
            opportunities.append(ImprovementOpportunity("strategy_change","system","moderate",
                "Tendencia decreciente en aprobación",["trend=degrading"],
                "Revisar cambios recientes de mercado",priority=2))
        if history:
            latest = history[0]
            if latest.total_signals >= 50 and not all_thresh:
                opportunities.append(ImprovementOpportunity("threshold_adjust","adaptive_thresholds","minor",
                    "Señales suficientes pero umbrales no adaptados",
                    [f"total_signals={latest.total_signals}"],
                    "Ejecutar 'thresholds adaptar'",priority=3))
            if latest.models_trained == 0:
                opportunities.append(ImprovementOpportunity("retrain","model_storage","critical",
                    "No hay modelos entrenados",["models_trained=0"],
                    "Ejecutar 'lab reporte <csv>' o 'train forex <csv> <par>'",priority=1))
            elif latest.models_trained < 3:
                opportunities.append(ImprovementOpportunity("feature_add","model_storage","minor",
                    f"Solo {latest.models_trained} modelos — considera más pares",
                    [f"models_trained={latest.models_trained}"],
                    "Entrenar más pares con 'scan forex'",priority=3))
        opportunities.sort(key=lambda o: o.priority)
        return opportunities

_detector = ImprovementDetector()

def detect_improvements() -> List[ImprovementOpportunity]: return _detector.detect()

def cmd_mejoras_detectar() -> str:
    opportunities = detect_improvements()
    if not opportunities: return "Sin oportunidades de mejora detectadas."
    lines = [f"{'═'*60}","  ASTRA — Oportunidades de Mejora",f"{'═'*60}"]
    for opp in opportunities: lines.append(opp.summary()); lines.append("")
    lines.append(f"Total: {len(opportunities)}  |  Críticas: {sum(1 for o in opportunities if o.severity=='critical')}")
    lines.append(f"{'═'*60}")
    return "\n".join(lines)
