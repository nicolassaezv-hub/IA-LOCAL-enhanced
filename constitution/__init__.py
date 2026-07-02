"""constitution — ASTRA Phase 8: Motor Constitucional"""
from .audit_log import AuditLog, AuditEntry, log_audit, get_audit_trail, cmd_audit_log
from .constitution_rules import ConstitutionRules, Rule, get_rules, add_rule, cmd_reglas_ver
from .rollback_manager import (
    RollbackManager, RollbackPoint, create_rollback_point, rollback_to,
    cmd_rollback_ver, cmd_rollback_aplicar,
)
from .constitution_validator import ConstitutionValidator, ValidationDecision, validate_proposal, cmd_validar_propuesta
from .approval_flow import (
    ApprovalFlow, ApprovalRequest, submit_for_approval, approve, reject,
    cmd_aprobar_propuesta, cmd_rechazar_propuesta,
)
# BUGFIX: el borrador de Bolt nunca exportaba las funciones cmd_* (interfaz de
# comandos) desde __init__.py — solo las clases/funciones internas. Sin esto,
# main.py no podia importar 'from constitution import cmd_aprobar_propuesta, ...'.
__all__ = [
    "AuditLog","AuditEntry","log_audit","get_audit_trail","cmd_audit_log",
    "ConstitutionRules","Rule","get_rules","add_rule","cmd_reglas_ver",
    "RollbackManager","RollbackPoint","create_rollback_point","rollback_to",
    "cmd_rollback_ver","cmd_rollback_aplicar",
    "ConstitutionValidator","ValidationDecision","validate_proposal","cmd_validar_propuesta",
    "ApprovalFlow","ApprovalRequest","submit_for_approval","approve","reject",
    "cmd_aprobar_propuesta","cmd_rechazar_propuesta",
]
