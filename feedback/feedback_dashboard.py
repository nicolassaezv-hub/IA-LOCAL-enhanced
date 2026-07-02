"""
feedback/feedback_dashboard.py — ASTRA Phase 6.5
Panel visual de métricas de feedback en consola.
"""
from __future__ import annotations
from .feedback_analyzer import FeedbackAnalyzer, _analyzer
from .adaptive_thresholds import AdaptiveThresholds, _thresholds
from .evolution_memory import EvolutionMemory, _memory as _ev_memory
from .contextual_memory import ContextualMemory, _memory as _ctx_memory

class FeedbackDashboard:
    def __init__(self, analyzer=_analyzer, thresholds=_thresholds, ev_memory=_ev_memory, ctx_memory=_ctx_memory):
        self.analyzer = analyzer; self.thresholds = thresholds
        self.ev_memory = ev_memory; self.ctx_memory = ctx_memory
    def render(self, compact: bool = False) -> str:
        sep = "═" * 64; thin = "─" * 64
        pattern = self.analyzer.analyze(200)
        all_thresh = self.thresholds.get_all()
        ev_stats = self.ev_memory.stats()
        tops = self.ctx_memory.top_contexts(5)
        lines = ["", sep, "  ASTRA — FEEDBACK DASHBOARD", sep, "",
            "RESUMEN GENERAL", thin,
            f"  Total feedback    : {pattern.total_entries}",
            f"  Tasa aprobación   : {pattern.approval_rate:.1%}",
            f"  Tendencia         : {pattern.trend}"]
        if pattern.by_type:
            lines += ["", "POR TIPO DE PREDICCIÓN", thin]
            for t, d in pattern.by_type.items():
                bar_len = int(d.get("approval_rate", 0) * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"  {t:20s}: [{bar}] {d.get('approval_rate',0):.0%}  ({d.get('total',0)} entradas)")
        if not compact:
            lines += ["", "UMBRALES ADAPTATIVOS", thin]
            if all_thresh:
                lines.append(f"  {'Par':<12} {'Conf':>8} {'ADX':>6} {'Ajustes':>8}")
                for pair, d in sorted(all_thresh.items()):
                    lines.append(f"  {pair:<12} {d['confidence']:>8.4f} {d['adx']:>6.1f} {d.get('n_updates',0):>8}")
            else:
                lines.append("  Sin umbrales personalizados (usando defaults)")
            if tops:
                lines += ["", "TOP CONTEXTOS", thin]
                for t in tops:
                    lines.append(f"  {t['context_key']:40s}: {t['success_rate']:.0%}  ({t['correct']}/{t['total']})")
        if ev_stats:
            lines += ["", "EVENTOS DE EVOLUCIÓN", thin]
            for etype, count in sorted(ev_stats.items(), key=lambda x: -x[1]):
                lines.append(f"  {etype:30s}: {count}")
        if pattern.insights:
            lines += ["", "INSIGHTS", thin] + [f"  - {i}" for i in pattern.insights]
        lines += ["", sep]
        return "\n".join(lines)

_dashboard = FeedbackDashboard()

def cmd_feedback_dashboard(compact: bool = False) -> str:
    return _dashboard.render(compact=compact)
