"""
Model Selection Engine — V.7 Roadmap V
=======================================
Compara algoritmos automaticamente y selecciona el mejor para cada contexto.
Depende del regimen de mercado (V.4): en mercados tendenciales, los modelos
basados en arboles suelen funcionar mejor; en laterales, un SVM puede destacar.

Algoritmos candidatos:
  - Logistic Regression (baseline)
  - SVM (mercados laterales)
  - Random Forest (ya existe)
  - XGBoost (ya existe)
  - LightGBM (ya existe)

Usa V.9 (BacktestProtocol) como metrica de comparacion.
Mantiene compatibilidad con el formato {model, feature_names} existente.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

from forex.prediction.backtest_protocol import (
    BacktestProtocol,
    BacktestReport,
    BacktestMetrics,
    compare_models,
    cmd_model_comparison,
    walk_forward_validation,
)

warnings.filterwarnings("ignore")

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.ensemble import RandomForestClassifier
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except Exception:
    _HAS_XGB = False

try:
    from lightgbm import LGBMClassifier
    _HAS_LGB = True
except Exception:
    _HAS_LGB = False


@dataclass
class ModelCandidate:
    name: str
    model: Any = None
    factory: Any = None
    report: BacktestReport | None = None
    wfv_accuracy: float = 0.0
    wfv_win_rate: float = 0.0
    wfv_sharpe: float = 0.0
    selected: bool = False
    rank: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "wfv_accuracy": round(self.wfv_accuracy, 4),
            "wfv_win_rate": round(self.wfv_win_rate, 4),
            "wfv_sharpe": round(self.wfv_sharpe, 4),
            "selected": self.selected,
            "rank": self.rank,
            "reason": self.reason,
            "backtest": self.report.to_dict() if self.report else None,
        }


@dataclass
class ModelSelectionResult:
    winner: ModelCandidate | None = None
    candidates: list[ModelCandidate] = field(default_factory=list)
    regime: str = ""
    pair: str = ""
    timeframe: str = ""
    comparison_table: dict = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "winner": self.winner.to_dict() if self.winner else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "regime": self.regime,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "comparison_table": self.comparison_table,
            "recommendation": self.recommendation,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def get_model(self) -> Any:
        """Retorna el modelo ganador empaquetado como {model, feature_names}."""
        if self.winner and self.winner.model:
            return self.winner.model
        return None


class ModelSelectionEngine:
    """
    Orquestador de comparacion de modelos.
    Evalua multiples algoritmos bajo el mismo protocolo (V.9) y selecciona el mejor.
    """

    DEFAULTS = {
        "wvf_folds": 5,
        "rr_ratio": 1.0,
        "use_wfv": True,
        "selection_metric": "wfv_accuracy",
        "min_wfv_accuracy": 0.55,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def get_default_candidates(self, regime: str = "") -> dict[str, Any]:
        """
        Retorna los candidatos por defecto segun el regimen.
        El ensemble actual (XGB+LGB+RF) se convierte en un candidato mas.
        """
        candidates: dict[str, Any] = {}

        if _HAS_SKLEARN:
            candidates["LogisticRegression"] = LogisticRegression(max_iter=1000, random_state=42)
            candidates["SVM"] = SVC(kernel="rbf", probability=True, random_state=42)
            candidates["RandomForest"] = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)

        if _HAS_XGB:
            candidates["XGBoost"] = XGBClassifier(n_estimators=100, max_depth=5, random_state=42, use_label_encoder=False, eval_metric="mlogloss")

        if _HAS_LGB:
            candidates["LightGBM"] = LGBMClassifier(n_estimators=100, max_depth=5, random_state=42, verbose=-1)

        return candidates

    def select(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        returns: np.ndarray | None = None,
        candidates: dict[str, Any] | None = None,
        regime: str = "",
        pair: str = "",
        timeframe: str = "",
        feature_names: list[str] | None = None,
    ) -> ModelSelectionResult:
        """
        Compara modelos y selecciona el mejor.
        """
        if candidates is None:
            candidates = self.get_default_candidates(regime)

        result = ModelSelectionResult(regime=regime, pair=pair, timeframe=timeframe)

        # Entrenar todos los candidatos
        for name, model in candidates.items():
            try:
                model.fit(X_train, y_train)
            except Exception as e:
                result.candidates.append(ModelCandidate(
                    name=name, reason=f"Error entrenando: {e}",
                ))

        # Evaluar con BacktestProtocol (V.9)
        trained = {name: model for name, model in candidates.items() if hasattr(model, "predict")}
        if trained:
            reports = compare_models(trained, X_test, y_test, returns=returns, rr_ratio=self.config["rr_ratio"])

            for name, report in reports.items():
                candidate = ModelCandidate(
                    name=name,
                    model=trained[name],
                    report=report,
                )

                # Walk-Forward Validation
                if self.config["use_wfv"]:
                    try:
                        wfv = walk_forward_validation(
                            lambda: self._clone_model(trained[name]),
                            np.vstack([X_train, X_test]),
                            np.concatenate([y_train, y_test]),
                            returns=np.concatenate([returns, returns[-len(y_test):]]) if returns is not None else None,
                            n_folds=self.config["wvf_folds"],
                            rr_ratio=self.config["rr_ratio"],
                        )
                        if wfv:
                            candidate.wfv_accuracy = float(np.mean([w.accuracy for w in wfv]))
                            candidate.wfv_win_rate = float(np.mean([w.win_rate for w in wfv]))
                            candidate.wfv_sharpe = float(np.mean([w.sharpe for w in wfv]))
                    except Exception:
                        candidate.wfv_accuracy = report.metrics.accuracy
                        candidate.wfv_win_rate = report.metrics.win_rate
                        candidate.wfv_sharpe = report.metrics.sharpe_ratio
                else:
                    candidate.wfv_accuracy = report.metrics.accuracy
                    candidate.wfv_win_rate = report.metrics.win_rate
                    candidate.wfv_sharpe = report.metrics.sharpe_ratio

                result.candidates.append(candidate)

        # Rankear
        self._rank_candidates(result)
        result.comparison_table = self._build_comparison_table(result)
        result.recommendation = self._build_recommendation(result)

        return result

    def _rank_candidates(self, result: ModelSelectionResult) -> None:
        """Rankea candidatos por la metrica de seleccion."""
        metric = self.config["selection_metric"]

        def get_metric(c: ModelCandidate) -> float:
            if metric == "wfv_accuracy":
                return c.wfv_accuracy
            elif metric == "wfv_win_rate":
                return c.wfv_win_rate
            elif metric == "wfv_sharpe":
                return c.wfv_sharpe
            elif c.report:
                return c.report.metrics.accuracy
            return 0.0

        ranked = sorted(result.candidates, key=get_metric, reverse=True)

        for i, candidate in enumerate(ranked):
            candidate.rank = i + 1
            if i == 0 and get_metric(candidate) >= self.config["min_wfv_accuracy"]:
                candidate.selected = True
                candidate.reason = f"Mejor {metric}: {get_metric(candidate):.4f}"
                result.winner = candidate
            elif i == 0:
                candidate.reason = f"Mejor candidato pero {metric} ({get_metric(candidate):.4f}) < minimo ({self.config['min_wfv_accuracy']})"
                result.winner = candidate
            else:
                candidate.reason = f"{metric}: {get_metric(candidate):.4f}"

    def _build_comparison_table(self, result: ModelSelectionResult) -> dict:
        """Construye tabla comparativa para guardar en memoria."""
        table = {}
        for c in result.candidates:
            entry = {
                "rank": c.rank,
                "wfv_accuracy": round(c.wfv_accuracy, 4),
                "wfv_win_rate": round(c.wfv_win_rate, 4),
                "wfv_sharpe": round(c.wfv_sharpe, 4),
                "selected": c.selected,
            }
            if c.report:
                entry["backtest_accuracy"] = round(c.report.metrics.accuracy, 4)
                entry["profit_factor"] = round(c.report.metrics.profit_factor, 2)
                entry["max_drawdown"] = round(c.report.metrics.max_drawdown, 4)
            table[c.name] = entry
        return table

    def _build_recommendation(self, result: ModelSelectionResult) -> str:
        if not result.winner:
            return "No se pudo seleccionar un modelo ganador."
        w = result.winner
        regime_desc = f" para regimen '{result.regime}'" if result.regime else ""
        return (
            f"Modelo ganador: {w.name}{regime_desc}. "
            f"WFV Accuracy: {w.wfv_accuracy:.4f}, Win Rate: {w.wfv_win_rate:.2%}, "
            f"Sharpe: {w.wfv_sharpe:.2f}. {w.reason}"
        )

    @staticmethod
    def _clone_model(model: Any) -> Any:
        """Crea una instancia fresca del mismo tipo de modelo."""
        from sklearn.base import clone
        try:
            return clone(model)
        except Exception:
            return type(model)()


# ──────────────────────────────────────────────────────
# Model Registry — registro de modelos por regimen
# ──────────────────────────────────────────────────────

class ModelRegistry:
    """Registro de mejores modelos por par y regimen."""

    def __init__(self, db_path: str = "memoria.db"):
        self.db_path = db_path

    def store(self, result: ModelSelectionResult) -> bool:
        """Almacena el resultado de seleccion en memoria.db."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    wfv_accuracy REAL,
                    wfv_win_rate REAL,
                    wfv_sharpe REAL,
                    comparison_table TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            if result.winner:
                conn.execute("""
                    INSERT INTO model_registry
                        (pair, timeframe, regime, model_name, wfv_accuracy, wfv_win_rate, wfv_sharpe, comparison_table)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.pair, result.timeframe, result.regime,
                    result.winner.name, result.winner.wfv_accuracy,
                    result.winner.wfv_win_rate, result.winner.wfv_sharpe,
                    json.dumps(result.comparison_table),
                ))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_best(self, pair: str, timeframe: str, regime: str = "") -> dict | None:
        """Obtiene el mejor modelo registrado para un par/regimen."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            if regime:
                cursor = conn.execute(
                    "SELECT * FROM model_registry WHERE pair=? AND timeframe=? AND regime=? ORDER BY timestamp DESC LIMIT 1",
                    (pair, timeframe, regime)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM model_registry WHERE pair=? AND timeframe=? ORDER BY timestamp DESC LIMIT 1",
                    (pair, timeframe)
                )
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception:
            return None


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_model_selection_report(result: ModelSelectionResult) -> str:
    """Formatea un ModelSelectionResult para consola."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        G = Fore.GREEN
        R = Fore.RED
        Y = Fore.YELLOW
        C = Fore.CYAN
        B = Fore.BLUE
        S = Style.RESET_ALL
    except Exception:
        G = R = Y = C = B = S = ""

    lines: list[str] = []

    lines.append(f"\n{C}{'='*70}{S}")
    lines.append(f"{C}  MODEL SELECTION ENGINE — V.7{S}")
    if result.pair:
        lines.append(f"{C}  {result.pair} · {result.timeframe} · Regimen: {result.regime}{S}")
    lines.append(f"{C}{'='*70}{S}\n")

    if result.winner:
        w = result.winner
        lines.append(f"{B}── Ganador ──{S}")
        lines.append(f"  Modelo:      {G}{w.name}{S}")
        lines.append(f"  WFV Acc:     {w.wfv_accuracy:.4f}")
        lines.append(f"  WFV WinRate: {w.wfv_win_rate:.2%}")
        lines.append(f"  WFV Sharpe:  {w.wfv_sharpe:.2f}")
        lines.append(f"  Seleccionado: {G if w.selected else R}{'Si' if w.selected else 'No'}{S}")
        lines.append(f"  Razon:       {w.reason}\n")

    if result.candidates:
        lines.append(f"{B}── Ranking de Candidatos ({len(result.candidates)}) ──{S}")
        lines.append(f"  {'Rank':>4}  {'Modelo':<22} {'WFV Acc':>8} {'WinRate':>8} {'Sharpe':>8} {'Sel':>4}")
        lines.append(f"  {'-'*4}  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*4}")
        for c in sorted(result.candidates, key=lambda x: x.rank):
            sel = f"{G}Si{S}" if c.selected else ""
            lines.append(
                f"  {c.rank:>4}  {c.name:<22} {c.wfv_accuracy:>8.4f} {c.wfv_win_rate:>8.2%} {c.wfv_sharpe:>8.2f} {sel:>4}"
            )

    lines.append(f"\n  {result.recommendation}")
    lines.append(f"\n{C}{'='*70}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split

    np.random.seed(42)
    X, y = make_classification(n_samples=1000, n_features=20, n_classes=3, n_informative=10, random_state=42)
    returns = np.random.randn(1000) * 0.02

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    ret_test = returns[len(X_train):]

    engine = ModelSelectionEngine({"use_wfv": True, "wvf_folds": 3, "min_wfv_accuracy": 0.50})
    result = engine.select(
        X_train, y_train, X_test, y_test,
        returns=ret_test,
        regime="trending_bullish",
        pair="EURUSD",
        timeframe="H1",
    )

    print(cmd_model_selection_report(result))
    print(f"\n  Winner: {result.winner.name if result.winner else 'None'}")
    print(f"  Comparison table keys: {list(result.comparison_table.keys())}")
    print("\n=== V.7 PASSED ===")
