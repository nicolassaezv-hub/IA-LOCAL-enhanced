"""
V.18 — Portfolio Intelligence
==============================
Ranking de las mejores oportunidades entre multiples activos ordenadas
por confiabilidad. ASTRA analiza todos los activos vigilados por el
Market Sentinel y genera un ranking unificado.

Integracion:
    from forex.portfolio.portfolio_ranker import PortfolioRanker
    ranker = PortfolioRanker()
    ranking = ranker.rank(opportunities=[
        {"pair": "EURUSD", "signal": "BUY", "reliability": 88.0, ...},
        {"pair": "GBPUSD", "signal": "SELL", "reliability": 82.0, ...},
    ])
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from infra.db.database import SymbolLifecycleError, require_active_symbol

try:
    from colorama import Fore, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = True

if HAS_COLOR:
    _C = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _B = lambda s: f"{Fore.BLUE}{s}{Style.RESET_ALL}"
else:
    _C = _G = _Y = _R = _B = lambda s: s


@dataclass
class PortfolioOpportunity:
    pair: str
    timeframe: str = "H1"
    signal: str = "HOLD"
    decision: str = "HOLD"
    reliability_score: float = 0.0
    regime: str = ""
    mtf_coherent: bool = False
    win_rate: float = 0.0
    wfv_accuracy: float = 0.0
    risk_level: str = "medium"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_pct: float = 0.0
    factors_for: list[str] = field(default_factory=list)
    factors_against: list[str] = field(default_factory=list)
    explanation: str = ""
    composite_score: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class PortfolioRanking:
    timestamp: str = ""
    total_opportunities: int = 0
    active_signals: int = 0
    ranking: list[PortfolioOpportunity] = field(default_factory=list)
    filter_signal: str = ""
    min_reliability: float = 0.0
    total_active: int = 0
    total_rejected: int = 0
    rejected: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_opportunities": self.total_opportunities,
            "active_signals": self.active_signals,
            "filter_signal": self.filter_signal,
            "min_reliability": self.min_reliability,
            "total_active": self.total_active,
            "total_rejected": self.total_rejected,
            "rejected": self.rejected,
            "ranking": [o.to_dict() for o in self.ranking],
        }

    def to_csv(self) -> str:
        if not self.ranking:
            return "No opportunities"
        header = "rank,pair,timeframe,signal,reliability,composite_score,regime,win_rate,wfv_accuracy,risk_level,sl,tp,risk_pct\n"
        rows = []
        for o in self.ranking:
            rows.append(
                f"{o.rank},{o.pair},{o.timeframe},{o.signal},{o.reliability_score:.1f},"
                f"{o.composite_score:.1f},{o.regime},{o.win_rate:.2%},{o.wfv_accuracy:.2%},"
                f"{o.risk_level},{o.stop_loss:.5f},{o.take_profit:.5f},{o.risk_pct:.2f}"
            )
        return header + "\n".join(rows)


DEFAULT_WEIGHTS = {
    "reliability": 0.40,
    "win_rate": 0.20,
    "wfv_accuracy": 0.15,
    "mtf_coherent": 0.10,
    "regime_favorable": 0.10,
    "risk_adjusted": 0.05,
}

FAVORABLE_REGIMES = {
    "trending_bullish": ["BUY"],
    "trending_bearish": ["SELL"],
    "ranging": [],
    "high_volatility": [],
    "low_volatility": [],
    "breakout_bullish": ["BUY"],
    "breakout_bearish": ["SELL"],
    "news_impacted": [],
}


class PortfolioRanker:
    """Motor de ranking de oportunidades de portfolio."""

    def __init__(
        self,
        db_path: str = "memoria.db",
        weights: dict | None = None,
        *,
        database=None,
    ):
        self.db_path = db_path
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.database = database
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ranking_json TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Compute composite score ──
    def _compute_composite(self, opp: PortfolioOpportunity) -> float:
        score = 0.0

        # Reliability (0-100 → 0-1)
        score += self.weights["reliability"] * (opp.reliability_score / 100.0)

        # Win rate
        score += self.weights["win_rate"] * opp.win_rate

        # WFV accuracy
        score += self.weights["wfv_accuracy"] * opp.wfv_accuracy

        # MTF coherent
        score += self.weights["mtf_coherent"] * (1.0 if opp.mtf_coherent else 0.0)

        # Regime favorable
        favorable = FAVORABLE_REGIMES.get(opp.regime, [])
        score += self.weights["regime_favorable"] * (1.0 if opp.signal in favorable else 0.5)

        # Risk adjusted (lower risk = higher score)
        risk_factor = 1.0
        if opp.risk_level == "low":
            risk_factor = 1.0
        elif opp.risk_level == "medium":
            risk_factor = 0.8
        elif opp.risk_level == "high":
            risk_factor = 0.5
        elif opp.risk_level == "extreme":
            risk_factor = 0.2
        score += self.weights["risk_adjusted"] * risk_factor

        return score * 100.0

    # ── Rank opportunities ──
    def rank(
        self,
        opportunities: list[dict],
        filter_signal: str = "",
        min_reliability: float = 0.0,
        top_n: int = 10,
        save: bool = True,
    ) -> PortfolioRanking:
        ranking = PortfolioRanking(
            timestamp=datetime.utcnow().isoformat(),
            total_opportunities=len(opportunities),
            filter_signal=filter_signal,
            min_reliability=min_reliability,
        )

        opps: list[PortfolioOpportunity] = []
        for o in opportunities:
            pair = str(o.get("pair", "")).upper()
            try:
                require_active_symbol(pair, database=self.database)
            except SymbolLifecycleError as exc:
                ranking.rejected.append({"pair": pair, "reason": str(exc)})
                continue
            ranking.total_active += 1
            opp = PortfolioOpportunity(
                pair=pair,
                timeframe=o.get("timeframe", "H1"),
                signal=o.get("signal", "HOLD"),
                decision=o.get("decision", "HOLD"),
                reliability_score=o.get("reliability_score", 0.0),
                regime=o.get("regime", ""),
                mtf_coherent=o.get("mtf_coherent", False),
                win_rate=o.get("win_rate", 0.0),
                wfv_accuracy=o.get("wfv_accuracy", 0.0),
                risk_level=o.get("risk_level", "medium"),
                stop_loss=o.get("stop_loss", 0.0),
                take_profit=o.get("take_profit", 0.0),
                risk_pct=o.get("risk_pct", 0.0),
                factors_for=o.get("factors_for", []),
                factors_against=o.get("factors_against", []),
                explanation=o.get("explanation", ""),
            )

            # Apply filters
            if filter_signal and opp.signal != filter_signal:
                continue
            if min_reliability and opp.reliability_score < min_reliability:
                continue
            if opp.signal not in ("BUY", "SELL"):
                continue

            opp.composite_score = self._compute_composite(opp)
            opps.append(opp)

        # Sort by composite score descending
        opps.sort(key=lambda x: x.composite_score, reverse=True)

        # Assign ranks
        for i, opp in enumerate(opps[:top_n]):
            opp.rank = i + 1
            ranking.ranking.append(opp)

        ranking.active_signals = len(opps)
        ranking.total_rejected = len(ranking.rejected)

        if save and ranking.total_active:
            self._save_ranking(ranking)

        return ranking

    # ── Save ranking ──
    def _save_ranking(self, ranking: PortfolioRanking):
        for opportunity in ranking.ranking:
            require_active_symbol(
                opportunity.pair,
                database=self.database,
            )
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO portfolio_rankings (timestamp, ranking_json) VALUES (?, ?)",
                (ranking.timestamp, json.dumps(ranking.to_dict())),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Get latest ranking ──
    def get_latest_ranking(self) -> dict | None:
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT ranking_json FROM portfolio_rankings ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return None

    # ── Get ranking history ──
    def get_history(self, limit: int = 20) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT timestamp, ranking_json FROM portfolio_rankings ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [{"timestamp": r[0], "ranking": json.loads(r[1])} for r in rows]
        except Exception:
            return []


# ── CLI ──
def cmd_portfolio_ranking(args: str = "") -> str:
    """Comando CLI: portfolio_ranking [filter_signal] [min_reliability]"""
    parts = args.strip().split()
    filter_signal = parts[0].upper() if parts else ""
    min_reliability = float(parts[1]) if len(parts) > 1 else 0.0

    ranker = PortfolioRanker()
    latest = ranker.get_latest_ranking()
    if not latest or not latest.get("ranking"):
        return f"{_Y('Sin ranking disponible — ejecutar Market Sentinel primero')}"

    lines = [f"{_C('Portfolio Ranking')} — {latest['timestamp'][:19]}"]
    lines.append(f"  Total: {latest['total_opportunities']} | Activas: {latest['active_signals']}")
    lines.append("")

    for opp in latest["ranking"]:
        sig_color = _G if opp["signal"] == "BUY" else _R if opp["signal"] == "SELL" else _Y
        lines.append(
            f"  #{opp['rank']} {opp['pair']} {opp['timeframe']} | "
            f"{sig_color(opp['signal'])} | "
            f"R={opp['reliability_score']:.1f} | "
            f"Score={opp['composite_score']:.1f} | "
            f"WR={opp['win_rate']:.1%} | "
            f"{opp['regime']} | "
            f"Risk={opp['risk_level']}"
        )
        if opp["stop_loss"]:
            lines.append(f"       SL={opp['stop_loss']:.5f} TP={opp['take_profit']:.5f} Risk={opp['risk_pct']:.2f}%")

    return "\n".join(lines)


def cmd_portfolio_export(args: str = "") -> str:
    """Comando CLI: portfolio_export [filename]"""
    parts = args.strip().split()
    filename = parts[0] if parts else "portfolio_ranking.csv"
    ranker = PortfolioRanker()
    latest = ranker.get_latest_ranking()
    if not latest or not latest.get("ranking"):
        return f"{_Y('Sin ranking para exportar')}"

    header = "rank,pair,timeframe,signal,reliability,composite_score,regime,win_rate,wfv_accuracy,risk_level,sl,tp,risk_pct\n"
    rows = []
    for o in latest["ranking"]:
        rows.append(
            f"{o['rank']},{o['pair']},{o['timeframe']},{o['signal']},{o['reliability_score']:.1f},"
            f"{o['composite_score']:.1f},{o['regime']},{o['win_rate']:.2%},{o['wfv_accuracy']:.2%},"
            f"{o['risk_level']},{o['stop_loss']:.5f},{o['take_profit']:.5f},{o['risk_pct']:.2f}"
        )
    try:
        with open(filename, "w") as f:
            f.write(header + "\n".join(rows) + "\n")
        return f"{_G('Exportado')} → {filename} ({len(rows)} oportunidades)"
    except Exception as e:
        return f"{_R('Error')}: {e}"


if __name__ == "__main__":
    ranker = PortfolioRanker()
    ranking = ranker.rank(
        opportunities=[
            {"pair": "EURUSD", "signal": "BUY", "reliability_score": 88.0, "regime": "trending_bullish",
             "mtf_coherent": True, "win_rate": 0.65, "wfv_accuracy": 0.70, "risk_level": "medium",
             "stop_loss": 1.078, "take_profit": 1.092, "risk_pct": 2.0},
            {"pair": "GBPUSD", "signal": "SELL", "reliability_score": 82.0, "regime": "trending_bearish",
             "mtf_coherent": True, "win_rate": 0.60, "wfv_accuracy": 0.68, "risk_level": "medium",
             "stop_loss": 1.275, "take_profit": 1.260, "risk_pct": 1.5},
            {"pair": "USDJPY", "signal": "HOLD", "reliability_score": 65.0, "regime": "ranging",
             "mtf_coherent": False, "win_rate": 0.50, "wfv_accuracy": 0.55, "risk_level": "low"},
            {"pair": "AUDUSD", "signal": "BUY", "reliability_score": 91.0, "regime": "trending_bullish",
             "mtf_coherent": True, "win_rate": 0.68, "wfv_accuracy": 0.72, "risk_level": "low",
             "stop_loss": 0.655, "take_profit": 0.665, "risk_pct": 1.0},
        ],
    )
    print(cmd_portfolio_ranking())
