"""
ReportManager — Almacenamiento y recuperacion de informes de despliegue.
Gestiona la carpeta reports/deployment/ con marca temporal.
"""
from __future__ import annotations

import os
import json
import glob
from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_REPORT_DIR = _BASE / "reports" / "deployment"


class ReportManager:
    """Gestiona el ciclo de vida de los informes de despliegue."""

    def __init__(self, report_dir: Path | str | None = None):
        self.report_dir = Path(report_dir) if report_dir else _REPORT_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────
    # Guardar
    # ─────────────────────────────────────────────────────────
    def save_report(
        self,
        report_type: str,
        content_md: str,
        metadata: dict | None = None,
    ) -> str:
        """
        Guarda un informe en disco.
        report_type: 'pipeline' | 'deployment' | 'readiness'
        Retorna la ruta relativa del archivo guardado.
        """
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{ts}.md"
        filepath = self.report_dir / filename

        # Asegurar que el contenido tenga el header
        if not content_md.startswith("# "):
            content_md = f"# ASTRA {report_type.title()} Report\n\n{content_md}"

        filepath.write_text(content_md, encoding="utf-8")

        # Guardar metadata en JSON lado a lado
        meta_path = self.report_dir / f"{report_type}_{ts}.json"
        meta = {
            "type": report_type,
            "timestamp": ts,
            "filename": filename,
            "filepath": str(filepath),
            "created_at": datetime.utcnow().isoformat() + "Z",
            **(metadata or {}),
        }
        meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

        return str(filepath.relative_to(_BASE))

    # ─────────────────────────────────────────────────────────
    # Listar
    # ─────────────────────────────────────────────────────────
    def list_reports(self, report_type: str | None = None) -> list[dict]:
        """Lista todos los informes, opcionalmente filtrados por tipo."""
        pattern = f"{report_type}_*.json" if report_type else "*_*.json"
        metas = []
        for meta_path in sorted(self.report_dir.glob(pattern), reverse=True):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                metas.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
        return metas

    def list_pipeline_reports(self) -> list[dict]:
        return self.list_reports("pipeline")

    def list_deployment_reports(self) -> list[dict]:
        return self.list_reports("deployment")

    def list_readiness_reports(self) -> list[dict]:
        return self.list_reports("readiness")

    # ─────────────────────────────────────────────────────────
    # Leer
    # ─────────────────────────────────────────────────────────
    def get_report_content(self, filename: str) -> str | None:
        """Lee el contenido Markdown de un informe por nombre de archivo."""
        filepath = self.report_dir / filename
        if not filepath.exists():
            # Intentar con .md
            if not filename.endswith(".md"):
                filepath = self.report_dir / f"{filename}.md"
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def get_latest(self, report_type: str) -> dict | None:
        """Retorna la metadata del informe mas reciente del tipo dado."""
        reports = self.list_reports(report_type)
        return reports[0] if reports else None

    def get_latest_content(self, report_type: str) -> str | None:
        """Retorna el contenido del informe mas reciente del tipo dado."""
        latest = self.get_latest(report_type)
        if not latest:
            return None
        return self.get_report_content(latest["filename"])

    # ─────────────────────────────────────────────────────────
    # Resumen para API
    # ─────────────────────────────────────────────────────────
    def get_summary(self) -> dict:
        """Resumen de todos los informes para la API del workspace."""
        return {
            "report_dir": str(self.report_dir.relative_to(_BASE)),
            "pipeline_reports": len(self.list_pipeline_reports()),
            "deployment_reports": len(self.list_deployment_reports()),
            "readiness_reports": len(self.list_readiness_reports()),
            "latest_pipeline": self.get_latest("pipeline"),
            "latest_deployment": self.get_latest("deployment"),
            "latest_readiness": self.get_latest("readiness"),
            "all_reports": [
                {
                    "type": r.get("type"),
                    "timestamp": r.get("timestamp"),
                    "filename": r.get("filename"),
                    "created_at": r.get("created_at"),
                    "symbol": r.get("symbol"),
                    "summary": r.get("summary"),
                }
                for r in self.list_reports()
            ],
        }

    # ─────────────────────────────────────────────────────────
    # Limpiar viejos
    # ─────────────────────────────────────────────────────────
    def cleanup_old_reports(self, keep: int = 20) -> int:
        """Mantiene solo los `keep` informes mas recientes por tipo. Retorna cuantos borro."""
        deleted = 0
        for rtype in ("pipeline", "deployment", "readiness"):
            reports = self.list_reports(rtype)
            if len(reports) > keep:
                for old in reports[keep:]:
                    for ext in (".md", ".json"):
                        path = self.report_dir / old["filename"].replace(".md", ext)
                        if path.exists():
                            path.unlink()
                            deleted += 1
        return deleted
