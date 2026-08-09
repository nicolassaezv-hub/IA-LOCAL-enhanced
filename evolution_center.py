"""
evolution_center.py — ASTRA Roadmap IV, Sección 8: Evolution Center

Agregador "solo lectura + acciones de aprobación" para el Workspace visual.
No reimplementa lógica: envuelve los módulos ya operativos y probados de
`evolution/` y `constitution/` (Fases 7 y 8) y `evolutionary_cycle.py`
(Fase 9) para exponerlos de forma estructurada (dicts serializables a JSON)
en vez de los strings pre-formateados para consola que usan los comandos
CLI (`cmd_*`).

Mismo patrón "graceful fail" que `cognitive_center.py`: cada función pública
atrapa sus propias excepciones y devuelve `{"ok": False, "error": ...}` en
vez de propagar — el Workspace nunca debe caerse porque una tabla está vacía
o un módulo opcional no cargó.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from evolution.proposal_store import get_proposals, _store, Proposal
from evolution.performance_monitor import _monitor
from feedback.evolution_memory import get_evolution_history
from constitution.audit_log import get_audit_trail
from constitution.rollback_manager import _rollback
from constitution.constitution_rules import get_rules
from constitution.constitution_validator import _validator
from constitution.approval_flow import approve as _approve, reject as _reject, submit_for_approval
from evolutionary_cycle import run_evolutionary_cycle


def _proposal_to_dict(p: Proposal) -> Dict[str, Any]:
    return {
        "id": p.proposal_id,
        "proposal_type": p.proposal_type,
        "component": p.component,
        "description": p.description,
        "rationale": p.rationale,
        "payload": p.payload,
        "priority": p.priority,
        "priority_label": {1: "ALTA", 2: "MEDIA", 3: "BAJA"}.get(p.priority, "?"),
        "status": p.status,
        "created_at": p.created_at,
        "applied_at": p.applied_at,
        "result": p.result,
    }


# ══════════════════════════════════════════════════════════════
# 8.1 — Panel del ciclo evolutivo
# ══════════════════════════════════════════════════════════════

def get_cycle_overview() -> Dict[str, Any]:
    """Estadísticas agregadas: propuestas por status, snapshots, audit, rollback."""
    try:
        stats = _store.stats()
        history = _monitor.get_history(1)
        latest_snapshot = None
        if history:
            s = history[0]
            latest_snapshot = {
                "timestamp": s.timestamp,
                "total_signals": s.total_signals,
                "signal_accuracy": s.signal_accuracy,
                "feedback_approval": s.feedback_approval,
                "models_trained": s.models_trained,
                "active_pairs": s.active_pairs,
                "avg_confidence": s.avg_confidence,
                "avg_adx": s.avg_adx,
                "evolution_events": s.evolution_events,
            }
        audit_stats = _store and get_audit_trail(limit=1) is not None
        audit_by_outcome = {}
        try:
            from constitution.audit_log import _audit
            audit_by_outcome = _audit.stats()
        except Exception:
            pass
        return {
            "ok": True,
            "proposals_by_status": stats,
            "proposals_total": sum(stats.values()),
            "latest_snapshot": latest_snapshot,
            "audit_total": sum(audit_by_outcome.values()) if audit_by_outcome else 0,
            "audit_by_outcome": audit_by_outcome,
            "rollback_points_total": len(_rollback.get_recent(limit=1000)),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_evolution_timeline(limit: int = 40) -> Dict[str, Any]:
    """Historial cronológico de eventos de evolución (feedback/evolution_memory)."""
    try:
        events = get_evolution_history(limit=limit)
        return {
            "ok": True,
            "events": [
                {
                    "event_type": e.event_type,
                    "component": e.component,
                    "description": e.description,
                    "data": e.data,
                    "timestamp": e.timestamp,
                }
                for e in events
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_performance_history(limit: int = 20) -> Dict[str, Any]:
    """Historial de snapshots de rendimiento (evolution/performance_monitor)."""
    try:
        history = _monitor.get_history(limit)
        return {
            "ok": True,
            "snapshots": [
                {
                    "id": s.snapshot_id,
                    "timestamp": s.timestamp,
                    "total_signals": s.total_signals,
                    "signal_accuracy": s.signal_accuracy,
                    "feedback_approval": s.feedback_approval,
                    "models_trained": s.models_trained,
                    "active_pairs": s.active_pairs,
                    "avg_confidence": s.avg_confidence,
                    "avg_adx": s.avg_adx,
                    "evolution_events": s.evolution_events,
                }
                for s in history
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 8.2 — Revisión de propuestas
# ══════════════════════════════════════════════════════════════

def get_proposals_list(status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    try:
        proposals = get_proposals(status=status, limit=limit)
        return {"ok": True, "proposals": [_proposal_to_dict(p) for p in proposals]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_proposal_detail(proposal_id: int) -> Dict[str, Any]:
    """Detalle de una propuesta + su validación constitucional en vivo (preview,
    no cambia estado — mismo cálculo que 'propuesta validar' por CLI) + los
    rollback points asociados si ya fue aprobada."""
    try:
        proposal = _store.get(proposal_id)
        if not proposal:
            return {"ok": False, "error": f"Propuesta #{proposal_id} no encontrada"}
        decision = _validator.validate(proposal)
        related_rollbacks = [
            {"point_id": rp.point_id, "description": rp.description, "created_at": rp.created_at}
            for rp in _rollback.get_recent(limit=200)
            if rp.proposal_id == proposal_id
        ]
        return {
            "ok": True,
            "proposal": _proposal_to_dict(proposal),
            "validation": {
                "is_valid": decision.is_valid,
                "violations": decision.violations,
                "warnings": decision.warnings,
                "checked_rules": decision.checked_rules,
            },
            "rollback_points": related_rollbacks,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def approve_proposal(proposal_id: int, justification: str = "") -> Dict[str, Any]:
    """Aprobación manual real vía el mismo ApprovalFlow que usa el CLI
    ('propuesta aprobar') — crea rollback point automáticamente."""
    try:
        result = _approve(proposal_id, justification or "Aprobado desde Workspace")
        return {"ok": True, "message": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def reject_proposal(proposal_id: int, reason: str = "") -> Dict[str, Any]:
    try:
        result = _reject(proposal_id, reason or "Rechazado desde Workspace")
        return {"ok": True, "message": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def validate_proposal_constitutional(proposal_id: int, requester: str = "workspace_user") -> Dict[str, Any]:
    """Envía la propuesta al flujo de aprobación completo (valida contra la
    constitución Y aprueba/rechaza según el resultado, igual que
    'evolucionar ciclo' hace automáticamente) — a diferencia de
    get_proposal_detail(), esto SÍ cambia el estado."""
    try:
        result = submit_for_approval(proposal_id, requester=requester, justification="workspace review")
        return {"ok": True, "message": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# Extras: reglas constitucionales, audit trail, rollback points,
# y disparo manual del ciclo completo — todo lo que la Sección 8
# necesita para ser una ventana completa sobre evolution/constitution.
# ══════════════════════════════════════════════════════════════

def get_constitution_rules() -> Dict[str, Any]:
    try:
        rules = get_rules(enabled_only=False)
        return {
            "ok": True,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "description": r.description,
                    "rule_type": r.rule_type,
                    "constraint": r.constraint,
                    "is_builtin": r.is_builtin,
                    "enabled": r.enabled,
                }
                for r in rules
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_audit_log(target: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    try:
        entries = get_audit_trail(target=target, limit=limit)
        return {
            "ok": True,
            "entries": [
                {
                    "id": e.entry_id,
                    "action": e.action,
                    "actor": e.actor,
                    "target": e.target,
                    "outcome": e.outcome,
                    "details": e.details,
                    "timestamp": e.timestamp,
                }
                for e in entries
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_rollback_points(limit: int = 30) -> Dict[str, Any]:
    try:
        points = _rollback.get_recent(limit=limit)
        return {
            "ok": True,
            "points": [
                {
                    "point_id": p.point_id,
                    "component": p.component,
                    "description": p.description,
                    "proposal_id": p.proposal_id,
                    "created_at": p.created_at,
                }
                for p in points
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def apply_rollback(point_id: int) -> Dict[str, Any]:
    try:
        result = _rollback.rollback(point_id)
        return {"ok": True, "message": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def trigger_evolutionary_cycle(auto_approve_minor: bool = False) -> Dict[str, Any]:
    """Corre el ciclo completo real (monitor→detecta→propone→valida→aprueba→
    feedback→audit) — mismo que 'evolucionar ciclo [auto]' por CLI, ahora
    invocable desde el botón del Workspace."""
    try:
        result = run_evolutionary_cycle(auto_approve_minor=auto_approve_minor, ask_llm=False)
        return {
            "ok": True,
            "timestamp": result.timestamp,
            "opportunities_found": result.opportunities_found,
            "proposals_created": result.proposals_created,
            "proposals_approved": result.proposals_approved,
            "proposals_rejected": result.proposals_rejected,
            "threshold_updates": result.threshold_updates,
            "cycle_notes": result.cycle_notes,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
