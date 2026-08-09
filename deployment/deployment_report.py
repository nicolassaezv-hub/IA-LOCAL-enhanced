"""
Deployment Report — Resumen general del despliegue de todos los simbolos.
Se genera despues de que todos los simbolos completan su Pipeline Report.
"""
from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

from .pipeline_report import PipelineReport


@dataclass
class SymbolSummary:
    """Resumen de un simbolo en el deployment report."""
    symbol: str
    timeframe: str
    overall_status: str
    passed: int
    failed: int
    warned: int
    total_stages: int
    failed_stages: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class DeploymentReport:
    """Informe general de despliegue."""
    timestamp: str = ""
    symbols_total: int = 0
    symbols_passed: int = 0
    symbols_failed: int = 0
    symbols_partial: int = 0
    symbols: list[SymbolSummary] = field(default_factory=list)
    global_status: str = "pending"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    def add_symbol(self, report: PipelineReport):
        """Agrega un simbolo desde su PipelineReport."""
        failed_stages = [s.stage for s in report.stages if s.status == "fail"]
        causes = list(set(s.cause for s in report.stages if s.status == "fail" and s.cause))
        recs = list(set(s.recommendation for s in report.stages if s.status == "fail" and s.recommendation))

        summary = SymbolSummary(
            symbol=report.symbol,
            timeframe=report.timeframe,
            overall_status=report.overall_status,
            passed=report.passed_count,
            failed=report.failed_count,
            warned=report.warn_count,
            total_stages=len(report.stages),
            failed_stages=failed_stages,
            causes=causes,
            recommendations=recs,
        )
        self.symbols.append(summary)
        self.symbols_total += 1
        if report.overall_status == "pass":
            self.symbols_passed += 1
        elif report.overall_status == "fail":
            self.symbols_failed += 1
        else:
            self.symbols_partial += 1

        self._update_global()

    def _update_global(self):
        if self.symbols_failed > 0:
            self.global_status = "FAILED"
        elif self.symbols_partial > 0:
            self.global_status = "PARTIAL"
        elif self.symbols_passed > 0:
            self.global_status = "SUCCESS"
        else:
            self.global_status = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "global_status": self.global_status,
            "symbols_total": self.symbols_total,
            "symbols_passed": self.symbols_passed,
            "symbols_failed": self.symbols_failed,
            "symbols_partial": self.symbols_partial,
            "symbols": [
                {
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "overall_status": s.overall_status,
                    "passed": s.passed,
                    "failed": s.failed,
                    "warned": s.warned,
                    "failed_stages": s.failed_stages,
                    "causes": s.causes,
                    "recommendations": s.recommendations,
                }
                for s in self.symbols
            ],
        }

    def to_markdown(self) -> str:
        icons = {"pass": "PASS", "fail": "FAIL", "partial": "WARN"}

        lines = [
            f"# Deployment Report — Resumen General",
            f"",
            f"**Fecha:** {self.timestamp}",
            f"**Estado global:** {self.global_status}",
            f"",
            f"| Metrica | Valor |",
            f"|---------|-------|",
            f"| Simbolos totales | {self.symbols_total} |",
            f"| Simbolos exitosos | {self.symbols_passed} |",
            f"| Simbolos con errores | {self.symbols_failed} |",
            f"| Simbolos parciales | {self.symbols_partial} |",
            f"",
            f"---",
            f"",
            f"## Resumen por simbolo",
            f"",
            f"| Simbolo | TF | Estado | OK | Fail | Warn | Etapas fallidas |",
            f"|---------|----|--------|----|------|------|------------------|",
        ]

        for s in self.symbols:
            icon = icons.get(s.overall_status, s.overall_status.upper())
            failed_str = ", ".join(s.failed_stages) if s.failed_stages else "-"
            lines.append(
                f"| {s.symbol} | {s.timeframe} | {icon} | {s.passed} | {s.failed} | {s.warned} | {failed_str} |"
            )

        # Detalle de simbolos con problemas
        problem_symbols = [s for s in self.symbols if s.overall_status != "pass"]
        if problem_symbols:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Simbolos con problemas")
            lines.append("")

            for s in problem_symbols:
                lines.append(f"### {s.symbol} ({s.timeframe})")
                lines.append(f"")
                lines.append(f"**Estado:** {icons.get(s.overall_status, s.overall_status.upper())}")
                if s.failed_stages:
                    lines.append(f"**Etapas fallidas:** {', '.join(s.failed_stages)}")
                if s.causes:
                    lines.append(f"**Causas detectadas:**")
                    for c in s.causes:
                        lines.append(f"  - {c}")
                if s.recommendations:
                    lines.append(f"**Acciones recomendadas:**")
                    for r in s.recommendations:
                        lines.append(f"  - {r}")
                lines.append("")

        # Simbolos exitosos
        ok_symbols = [s for s in self.symbols if s.overall_status == "pass"]
        if ok_symbols:
            lines.append("---")
            lines.append("")
            lines.append("## Simbolos exitosos")
            lines.append("")
            for s in ok_symbols:
                lines.append(f"- {s.symbol} ({s.timeframe}): {s.passed}/{s.total_stages} etapas OK")

        return "\n".join(lines)


def run_deployment_report(pipeline_reports: list[PipelineReport]) -> DeploymentReport:
    """Genera el Deployment Report a partir de una lista de Pipeline Reports."""
    report = DeploymentReport()
    for pr in pipeline_reports:
        report.add_symbol(pr)
    return report
