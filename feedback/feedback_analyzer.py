"""
feedback/feedback_analyzer.py — ASTRA Phase 6.2
Agrega entradas de feedback y extrae patrones.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from collections import defaultdict
from .feedback_collector import FeedbackCollector, FeedbackEntry, _collector

@dataclass
class FeedbackPattern:
    total_entries: int
    approval_rate: float
    by_type: Dict[str, Dict]
    worst_targets: List[str]
    best_targets: List[str]
    trend: str
    insights: List[str]
    def summary(self) -> str:
        lines = [f"Total feedback   : {self.total_entries}", f"Tasa aprobación  : {self.approval_rate:.1%}", f"Tendencia        : {self.trend}"]
        if self.by_type:
            lines.append("\nPor tipo:")
            for t, d in self.by_type.items():
                lines.append(f"  {t:25s}: {d.get('total',0):3d} entradas  ({d.get('approval_rate',0):.0%} aprobación)")
        if self.worst_targets: lines.append(f"\nPeores targets : {', '.join(self.worst_targets[:5])}")
        if self.best_targets:  lines.append(f"Mejores targets: {', '.join(self.best_targets[:5])}")
        if self.insights:
            lines.append("\nInsights:")
            lines += [f"  - {i}" for i in self.insights]
        return "\n".join(lines)

class FeedbackAnalyzer:
    def __init__(self, collector: FeedbackCollector = _collector):
        self.collector = collector
    def analyze(self, limit: int = 500) -> FeedbackPattern:
        entries = self.collector.get_recent(limit)
        if not entries:
            return FeedbackPattern(total_entries=0, approval_rate=0.0, by_type={}, worst_targets=[], best_targets=[], trend="stable", insights=["Sin datos de feedback aún."])
        total = len(entries)
        positive = sum(1 for e in entries if e.vote > 0)
        approval = positive / total
        by_type = self.collector.summary_by_type()
        target_scores: Dict[str, List[int]] = defaultdict(list)
        for e in entries: target_scores[e.target_id].append(e.vote)
        worst = sorted(target_scores.keys(), key=lambda t: sum(target_scores[t])/len(target_scores[t]))[:5]
        best = sorted(target_scores.keys(), key=lambda t: -sum(target_scores[t])/len(target_scores[t]))[:5]
        trend = self._compute_trend(entries)
        insights = self._build_insights(approval, by_type, worst, entries)
        return FeedbackPattern(total_entries=total, approval_rate=round(approval,3), by_type=by_type, worst_targets=worst, best_targets=best, trend=trend, insights=insights)
    def _compute_trend(self, entries):
        if len(entries) < 10: return "stable"
        first_half = entries[len(entries)//2:]
        second_half = entries[:len(entries)//2]
        score_old = sum(e.vote for e in first_half) / len(first_half)
        score_new = sum(e.vote for e in second_half) / len(second_half)
        diff = score_new - score_old
        if diff > 0.10: return "improving"
        if diff < -0.10: return "degrading"
        return "stable"
    def _build_insights(self, approval, by_type, worst, entries):
        insights = []
        if approval < 0.40: insights.append(f"Tasa de aprobación muy baja ({approval:.0%}) — revisa el modelo o los umbrales")
        elif approval > 0.75: insights.append(f"Buen rendimiento general ({approval:.0%} de aprobación)")
        for t, d in by_type.items():
            ar = d.get("approval_rate", 0)
            if ar < 0.35 and d.get("total", 0) >= 5: insights.append(f"Tipo '{t}' tiene baja aprobación ({ar:.0%})")
        neg_comments = [e.comment for e in entries if e.vote < 0 and e.comment]
        if len(neg_comments) >= 3: insights.append(f"{len(neg_comments)} comentarios negativos registrados")
        return insights or ["Sin patrones significativos detectados aún."]

_analyzer = FeedbackAnalyzer()

def analyze_feedback(limit: int = 500) -> FeedbackPattern:
    return _analyzer.analyze(limit)

def cmd_feedback_analisis() -> str:
    pattern = analyze_feedback()
    return f"\n{'═'*56}\n  ASTRA — Análisis de Feedback\n{'═'*56}\n{pattern.summary()}\n{'═'*56}"
