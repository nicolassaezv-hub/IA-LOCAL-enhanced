"""
Quality Report — V.5 Roadmap V
================================
Generador de informes de calidad de dataset.
Define la estructura del QualityReport que QualityAnalyzer produce.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class QualityIssue:
    severity: str  # "critical", "warning", "info"
    category: str  # "missing_values", "outliers", "duplicates", etc.
    column: str
    description: str
    suggestion: str = ""
    value: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QualityReport:
    approved: bool = False
    global_score: float = 0.0
    total_issues: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[QualityIssue] = field(default_factory=list)
    dataset_info: dict = field(default_factory=dict)
    column_stats: dict = field(default_factory=dict)
    class_balance: dict = field(default_factory=dict)
    temporal_coverage: dict = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "global_score": round(self.global_score, 2),
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
            "dataset_info": self.dataset_info,
            "column_stats": self.column_stats,
            "class_balance": self.class_balance,
            "temporal_coverage": self.temporal_coverage,
            "recommendation": self.recommendation,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def summary(self) -> str:
        status = "APROBADO" if self.approved else "RECHAZADO"
        return (
            f"Quality Score: {self.global_score:.1f}/100 | "
            f"Status: {status} | "
            f"Issues: {self.critical_count} critical, {self.warning_count} warnings, {self.info_count} info"
        )
