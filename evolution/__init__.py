"""evolution — ASTRA Phase 7: Motor de Evolución"""
from .proposal_store import (
    ProposalStore, Proposal, save_proposal, get_proposals,
    cmd_proposals_ver, cmd_aprobar_propuesta, cmd_rechazar_propuesta,
)
from .performance_monitor import (
    PerformanceMonitor, PerformanceSnapshot, take_snapshot,
    cmd_monitor_snapshot, cmd_monitor_historial,
)
from .improvement_detector import (
    ImprovementDetector, ImprovementOpportunity, detect_improvements,
    cmd_mejoras_detectar,
)
from .evolution_proposal import (
    EvolutionProposal, ProposalBundle, propose_evolution,
    cmd_evolucionar, cmd_aplicar_propuesta,
)

__all__ = [
    "ProposalStore", "Proposal", "save_proposal", "get_proposals",
    "cmd_proposals_ver", "cmd_aprobar_propuesta", "cmd_rechazar_propuesta",
    "PerformanceMonitor", "PerformanceSnapshot", "take_snapshot",
    "cmd_monitor_snapshot", "cmd_monitor_historial",
    "ImprovementDetector", "ImprovementOpportunity", "detect_improvements", "cmd_mejoras_detectar",
    "EvolutionProposal", "ProposalBundle", "propose_evolution",
    "cmd_evolucionar", "cmd_aplicar_propuesta",
]
