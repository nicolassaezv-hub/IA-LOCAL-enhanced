"""evolution — ASTRA Phase 7: Motor de Evolución"""
from .proposal_store import ProposalStore, Proposal, save_proposal, get_proposals
from .performance_monitor import PerformanceMonitor, PerformanceSnapshot, take_snapshot
from .improvement_detector import ImprovementDetector, ImprovementOpportunity, detect_improvements
from .evolution_proposal import EvolutionProposal, ProposalBundle, propose_evolution
__all__ = [
    "ProposalStore","Proposal","save_proposal","get_proposals",
    "PerformanceMonitor","PerformanceSnapshot","take_snapshot",
    "ImprovementDetector","ImprovementOpportunity","detect_improvements",
    "EvolutionProposal","ProposalBundle","propose_evolution",
]
