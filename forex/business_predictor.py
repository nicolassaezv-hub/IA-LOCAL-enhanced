"""
forex/business/business_pipeline.py

Full Business Intelligence pipeline orchestrator.

Ties together:
    - business_csv_adapter  (normalize CSV/Excel)
    - kpi_engine             (compute KPIs + health score)
    - business_predictor    (GROWING/DECLINING/STABLE signal)
    - sme_consultant        (strategic recommendations)

Public API (used by main.py and bi_analytics.py):
    pipeline.analyze(filepath)  -> str   (KPI report)
    pipeline.consult(filepath)  -> str   (full consultant report)
    pipeline.predict(filepath)  -> dict  (ML signal)
    pipeline.train(filepath)    -> dict  (train model)

Author: Nicolas Saez / Astra Project
"""

from typing import Dict, Union

from forex.business.business_csv_adapter import adapt_business_csv
from forex.business.kpi_engine import KPIEngine
from forex.business.business_predictor import BusinessPredictor


class BusinessPipeline:
    """End-to-end business analysis pipeline."""

    def __init__(self):
        self.predictor = BusinessPredictor()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(filepath: str):
        """Load and normalize a business CSV/Excel file."""
        return adapt_business_csv(filepath)

    @staticmethod
    def _format_kpis(kpis: Dict) -> str:
        """Format KPI dict into a readable report string."""
        lines = []
        lines.append(f"Business Type : {kpis.get('business_type', 'generic')}")
        lines.append(f"Rows Analyzed : {kpis.get('rows', 0)}")
        lines.append("")

        rev = kpis.get("total_revenue")
        if rev is not None:
            lines.append(f"Total Revenue : ${rev:,.0f}")
        avg = kpis.get("avg_revenue")
        if avg is not None:
            lines.append(f"Avg Revenue   : ${avg:,.0f}")

        growth = kpis.get("growth_rate_pct")
        if growth is not None:
            lines.append(f"Growth Rate   : {growth:+.1f}%")

        gm = kpis.get("gross_margin_pct")
        if gm is not None:
            lines.append(f"Gross Margin  : {gm:.1f}%")

        nm = kpis.get("net_margin_pct")
        if nm is not None:
            lines.append(f"Net Margin    : {nm:.1f}%")

        er = kpis.get("expense_ratio_pct")
        if er is not None:
            lines.append(f"Expense Ratio : {er:.1f}%")

        lines.append("")
        lines.append(f"Trend         : {kpis.get('trend_direction', 'unknown')}")
        lines.append(f"Health Score  : {kpis.get('health_score', 0)}/100")
        lines.append(f"Risk Level    : {kpis.get('risk_level', 'unknown')}")

        anomalies = kpis.get("anomalies", [])
        if anomalies:
            lines.append("")
            lines.append(f"Anomalies ({len(anomalies)}):")
            for a in anomalies[:5]:
                lines.append(f"  - {a['period']}: {a['change_pct']:.1f}%")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, filepath: str) -> str:
        """KPI report + health score + alerts (no ML)."""
        try:
            df = self._load(filepath)
            kpis = KPIEngine(df).compute_all()
            return self._format_kpis(kpis)
        except Exception as e:
            return f"Error analyzing business data: {e}"

    def consult(self, filepath: str) -> str:
        """Full PYME consultant: KPIs + forecast + recommendations."""
        try:
            from sme_consultant import sme_diagnostic
            return sme_diagnostic(filepath)
        except Exception as e:
            return f"Error in business consultation: {e}"

    def predict(self, filepath: str) -> Dict:
        """ML forecast: will next period grow or decline?"""
        try:
            df = self._load(filepath)
            return self.predictor.predict(df)
        except Exception as e:
            return {"error": str(e)}

    def train(self, filepath: str) -> Dict:
        """Train ML model on business dataset."""
        try:
            df = self._load(filepath)
            result = self.predictor.train(df)
            result["business_type"] = df.attrs.get("business_type", "generic")
            return result
        except Exception as e:
            return {"error": str(e)}
