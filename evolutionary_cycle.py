"""
evolutionary_cycle.py — ASTRA Phase 9: Ciclo Evolutivo Completo

Orquesta el ciclo completo de auto-evolución:
  1. Monitor  → snapshot de rendimiento
  2. Detector → identifica oportunidades
  3. Proposer → genera propuestas
  4. Validator → verifica contra constitución
  5. Approval → aprueba/rechaza
  6. Feedback → adapta umbrales
  7. Audit    → registra todo

CLI: evolucionar ciclo
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from evolution.performance_monitor import take_snapshot, PerformanceSnapshot
from evolution.improvement_detector import detect_improvements
from evolution.evolution_proposal import propose_evolution, ProposalBundle
from constitution.approval_flow import submit_for_approval
from feedback.feedback_analyzer import analyze_feedback
from feedback.adaptive_thresholds import _thresholds
from feedback.feedback_collector import _collector

@dataclass
class CycleResult:
    timestamp: str; snapshot: PerformanceSnapshot
    opportunities_found: int; proposals_created: int
    proposals_approved: int; proposals_rejected: int
    threshold_updates: int; cycle_notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"\n{'═'*64}",
            f"  ASTRA — Ciclo Evolutivo Completo  [{self.timestamp[:19]}]",
            f"{'═'*64}", "",
            "RESULTADOS DEL CICLO:",
            f"  Snapshot de rendimiento    : tomado",
            f"  Oportunidades detectadas   : {self.opportunities_found}",
            f"  Propuestas generadas       : {self.proposals_created}",
            f"  Propuestas aprobadas       : {self.proposals_approved}",
            f"  Propuestas rechazadas      : {self.proposals_rejected}",
            f"  Umbrales ajustados         : {self.threshold_updates}",
            "",
            "MÉTRICAS ACTUALES:",
            f"  Señales totales            : {self.snapshot.total_signals}",
            f"  Aprobación feedback        : {self.snapshot.feedback_approval:.1%}",
            f"  Modelos entrenados         : {self.snapshot.models_trained}",
            f"  Pares activos              : {self.snapshot.active_pairs}",
        ]
        if self.cycle_notes: lines += ["", "NOTAS:"] + [f"  * {n}" for n in self.cycle_notes]
        lines.append(f"\n{'═'*64}")
        return "\n".join(lines)


def run_evolutionary_cycle(auto_approve_minor: bool = False, ask_llm: bool = False) -> CycleResult:
    ts = datetime.now().isoformat()
    notes = []
    snap = take_snapshot()
    notes.append(f"Snapshot #{snap.snapshot_id} tomado")
    bundle = propose_evolution(ask_llm=ask_llm)
    n_proposals = len(bundle.proposals)
    if not bundle.proposals:
        notes.append("Sin oportunidades de mejora — sistema en buen estado")
        return CycleResult(timestamp=ts, snapshot=snap, opportunities_found=len(bundle.opportunities),
            proposals_created=0, proposals_approved=0, proposals_rejected=0, threshold_updates=0, cycle_notes=notes)
    approved = rejected = 0
    for proposal in bundle.proposals:
        pid = proposal.proposal_id
        if pid is None: continue
        if auto_approve_minor and proposal.priority >= 3 and proposal.proposal_type == "threshold_adjust":
            result = submit_for_approval(pid, "system", "auto-approved minor threshold adjustment")
            if "APROBADA" in result: approved += 1; notes.append(f"Propuesta #{pid} auto-aprobada")
            else: rejected += 1
        else:
            result = submit_for_approval(pid, "system", "evolutionary cycle validation")
            if "APROBADA" in result: approved += 1
            elif "RECHAZADA" in result: rejected += 1
    threshold_updates = 0
    try:
        recent = _collector.get_recent(100)
        pairs_feedback = {}
        for entry in recent:
            if entry.target_type == "signal":
                pair_key = entry.context.get("pair", "UNKNOWN")
                if pair_key not in pairs_feedback: pairs_feedback[pair_key] = []
                pairs_feedback[pair_key].append(entry.vote)
        for pair, votes in pairs_feedback.items():
            if len(votes) >= 10:
                upd = _thresholds.adapt_from_feedback(pair, votes)
                if upd: threshold_updates += 1; notes.append(f"Umbrales adaptados para {pair}")
    except Exception as e:
        notes.append(f"Advertencia umbral: {e}")
    return CycleResult(timestamp=ts, snapshot=snap, opportunities_found=len(bundle.opportunities),
        proposals_created=n_proposals, proposals_approved=approved, proposals_rejected=rejected,
        threshold_updates=threshold_updates, cycle_notes=notes)


def system_health_report() -> str:
    lines = [f"\n{'═'*64}", "  ASTRA — Reporte de Salud del Sistema", f"{'═'*64}"]
    try:
        from evolution.performance_monitor import _monitor
        history = _monitor.get_history(1)
        if history:
            s = history[0]
            lines += [f"  Señales       : {s.total_signals}", f"  Aprobación FB : {s.feedback_approval:.1%}",
                      f"  Modelos       : {s.models_trained}", f"  Pares activos : {s.active_pairs}",
                      f"  Eventos evol. : {s.evolution_events}"]
        else:
            lines.append("  Sin snapshots — ejecuta 'monitor snapshot' primero")
    except Exception as e: lines.append(f"  Error: {e}")
    try:
        from evolution.proposal_store import _store
        stats = _store.stats()
        lines += ["", "  Propuestas:"] + [f"    {st:15s}: {count}" for st, count in sorted(stats.items())]
    except Exception: pass
    try:
        from constitution.audit_log import _audit
        total = sum(_audit.stats().values())
        lines += ["", f"  Audit log: {total} entradas"]
    except Exception: pass
    lines.append(f"\n{'═'*64}")
    return "\n".join(lines)


def cmd_ciclo_evolutivo(auto_approve: bool = False) -> str:
    try:
        result = run_evolutionary_cycle(auto_approve_minor=auto_approve, ask_llm=False)
        return result.summary()
    except Exception as e:
        return f"Error en ciclo evolutivo: {e}"

def cmd_health_report() -> str:
    return system_health_report()
