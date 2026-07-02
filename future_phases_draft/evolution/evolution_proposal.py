"""
evolution/evolution_proposal.py — ASTRA Phase 7.3
Genera propuestas concretas desde oportunidades de mejora.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from .improvement_detector import ImprovementDetector, ImprovementOpportunity, _detector
from .proposal_store import Proposal, ProposalStore, _store

@dataclass
class ProposalBundle:
    proposals: List[Proposal]; opportunities: List[ImprovementOpportunity]
    timestamp: str = ""; llm_summary: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()
    def summary(self) -> str:
        lines = [f"{'═'*60}",f"  ASTRA — Bundle de Evolución ({self.timestamp[:19]})",f"{'═'*60}",
                 f"  Oportunidades detectadas : {len(self.opportunities)}",f"  Propuestas generadas     : {len(self.proposals)}",""]
        for p in self.proposals: lines.append(p.summary()); lines.append("")
        if self.llm_summary: lines += ["-"*60, f"  Análisis ASTRA: {self.llm_summary}"]
        lines.append(f"{'═'*60}")
        return "\n".join(lines)

class EvolutionProposal:
    def __init__(self, detector=_detector, store=_store):
        self.detector = detector; self.store = store
    def propose(self, ask_llm: bool = False) -> ProposalBundle:
        opportunities = self.detector.detect()
        proposals = []
        for opp in opportunities:
            proposal = self._opportunity_to_proposal(opp)
            pid = self.store.save(proposal)
            proposal.proposal_id = pid
            proposals.append(proposal)
        llm_text = ""
        if ask_llm and proposals: llm_text = self._ask_llm(opportunities)
        return ProposalBundle(proposals=proposals, opportunities=opportunities, llm_summary=llm_text)
    def _opportunity_to_proposal(self, opp) -> Proposal:
        payload = {"action": opp.opportunity_type, "component": opp.component, "evidence": opp.evidence,
                   "suggested_cmd": self._suggest_cmd(opp)}
        return Proposal(proposal_type=opp.opportunity_type, component=opp.component,
            description=opp.description, rationale="; ".join(opp.evidence) if opp.evidence else opp.suggested_action,
            payload=payload, priority=opp.priority, status="pending")
    def _suggest_cmd(self, opp) -> str:
        if opp.opportunity_type == "retrain": return f"train forex <csv> {opp.component}"
        if opp.opportunity_type == "threshold_adjust": return "thresholds adaptar"
        if opp.opportunity_type == "feature_add": return "lab generar <csv>"
        return opp.suggested_action
    def _ask_llm(self, opportunities) -> str:
        try:
            from ai_models import ask_openai
            opp_text = "\n".join(f"- [{o.severity}] {o.opportunity_type} en {o.component}: {o.description}" for o in opportunities[:5])
            return ask_openai(f"Eres ASTRA, sistema ML auto-evolutivo. Oportunidades de mejora:\n{opp_text}\nEn 3-4 oraciones, qué pasos prioritarios tomar.")
        except Exception as e: return f"(LLM no disponible: {e})"
    def apply(self, proposal_id: int) -> str:
        proposal = self.store.get(proposal_id)
        if not proposal: return f"Propuesta #{proposal_id} no encontrada"
        if proposal.status != "approved": return f"Propuesta #{proposal_id} no está aprobada (status={proposal.status})"
        ptype = proposal.proposal_type
        if ptype == "threshold_adjust":
            try:
                from feedback.adaptive_thresholds import _thresholds
                from feedback.feedback_collector import _collector
                entries = _collector.get_recent(100)
                scores = [e.vote for e in entries if e.target_type == "signal"]
                if scores:
                    upd = _thresholds.adapt_from_feedback(proposal.component, scores)
                    if upd: return f"Umbrales adaptados para {proposal.component}: {upd.summary()}"
                return f"Sin feedback suficiente para {proposal.component}"
            except Exception as e: return f"Error: {e}"
        cmd = proposal.payload.get("suggested_cmd", "")
        return f"Propuesta '{ptype}' requiere acción manual. Ejecuta: {cmd}"

_proposer = EvolutionProposal()

def propose_evolution(ask_llm: bool = False) -> ProposalBundle: return _proposer.propose(ask_llm=ask_llm)

def cmd_evolucionar(ask_llm: bool = False) -> str:
    bundle = propose_evolution(ask_llm)
    if not bundle.proposals: return "Sin propuestas generadas. Sistema en buen estado."
    return bundle.summary()

def cmd_aplicar_propuesta(proposal_id_str: str) -> str:
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    return _proposer.apply(pid)
