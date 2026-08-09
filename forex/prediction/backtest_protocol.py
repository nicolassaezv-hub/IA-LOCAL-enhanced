"""
Backtest Protocol — V.9 Roadmap V
=================================
Protocolo estandarizado de metricas para todos los modelos.
Todos los modelos se evaluan con exactamente las mismas metricas,
permitiendo comparacion justa entre ellos.

Metricas minimas:
  - Accuracy, Precision, Recall, F1
  - Win Rate, Profit Factor
  - Drawdown maximo y esperado
  - Sharpe Ratio, Calmar Ratio
  - Expected Return por operacion

Extensiones:
  - Walk-Forward Validation (ampliar existente)
  - Monte Carlo simulation
  - Out-of-sample testing
  - Report HTML exportable
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

try:
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        confusion_matrix,
        classification_report,
    )
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False


# ──────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────

@dataclass
class BacktestMetrics:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    expected_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    expected_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    std_trade: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    confusion_matrix: list = field(default_factory=list)
    classification_report: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


@dataclass
class WalkForwardResult:
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    accuracy: float
    win_rate: float
    profit_factor: float
    sharpe: float
    trades: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MonteCarloResult:
    iterations: int
    median_return: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    prob_profit: float
    median_max_drawdown: float
    worst_max_drawdown: float
    best_return: float
    worst_return: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestReport:
    metrics: BacktestMetrics
    walk_forward: list = field(default_factory=list)
    monte_carlo: MonteCarloResult | None = None
    model_name: str = ""
    pair: str = ""
    timeframe: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics.to_dict(),
            "walk_forward": [w.to_dict() for w in self.walk_forward],
            "monte_carlo": self.monte_carlo.to_dict() if self.monte_carlo else None,
            "model_name": self.model_name,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────────────
# Core protocol
# ──────────────────────────────────────────────────────

class BacktestProtocol:
    """Aplica el protocolo estandar de backtesting a un conjunto de predicciones."""

    def __init__(self, rr_ratio: float = 1.0):
        self.rr_ratio = rr_ratio

    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        returns: np.ndarray | None = None,
        model_name: str = "",
        pair: str = "",
        timeframe: str = "",
    ) -> BacktestReport:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        metrics = self._compute_classification_metrics(y_true, y_pred)

        if returns is not None:
            trade_results = self._compute_trade_results(y_true, y_pred, np.asarray(returns))
            self._fill_trading_metrics(metrics, trade_results)
        else:
            trade_results = self._estimate_trade_results(y_true, y_pred)
            self._fill_trading_metrics(metrics, trade_results)

        from datetime import datetime
        return BacktestReport(
            metrics=metrics,
            model_name=model_name,
            pair=pair,
            timeframe=timeframe,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _compute_classification_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> BacktestMetrics:
        m = BacktestMetrics()
        m.total_trades = int(np.sum(y_pred != 0)) if len(y_pred) > 0 else 0

        non_zero_mask = (y_pred != 0) | (y_true != 0)
        if non_zero_mask.sum() > 0:
            yt = y_true[non_zero_mask]
            yp = y_pred[non_zero_mask]
        else:
            yt = y_true
            yp = y_pred

        if _HAS_SKLEARN and len(yt) > 0:
            labels = sorted(set(yt.tolist()) | set(yp.tolist()))
            m.accuracy = float(accuracy_score(yt, yp))
            m.precision = float(precision_score(yt, yp, average="weighted", zero_division=0, labels=labels))
            m.recall = float(recall_score(yt, yp, average="weighted", zero_division=0, labels=labels))
            m.f1 = float(f1_score(yt, yp, average="weighted", zero_division=0, labels=labels))
            cm = confusion_matrix(yt, yp, labels=labels)
            m.confusion_matrix = cm.tolist()
            m.classification_report = classification_report(yt, yp, labels=labels, zero_division=0)
        else:
            correct = int(np.sum(yt == yp))
            total = len(yt)
            m.accuracy = correct / total if total > 0 else 0.0
            m.precision = m.accuracy
            m.recall = m.accuracy
            m.f1 = m.accuracy

        return m

    def _compute_trade_results(self, y_true: np.ndarray, y_pred: np.ndarray, returns: np.ndarray) -> np.ndarray:
        trade_mask = y_pred != 0
        if trade_mask.sum() == 0:
            return np.array([])

        direction = np.sign(y_pred[trade_mask])
        actual_returns = returns[trade_mask]
        trade_results = direction * actual_returns * self.rr_ratio
        return trade_results

    def _estimate_trade_results(self, y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
        trade_mask = y_pred != 0
        if trade_mask.sum() == 0:
            return np.array([])

        correct = y_true[trade_mask] == y_pred[trade_mask]
        results = np.where(correct, self.rr_ratio, -1.0)
        return results

    def _fill_trading_metrics(self, m: BacktestMetrics, trades: np.ndarray) -> None:
        if len(trades) == 0:
            return

        wins = trades[trades > 0]
        losses = trades[trades < 0]

        m.winning_trades = len(wins)
        m.losing_trades = len(losses)
        m.win_rate = len(wins) / len(trades) if len(trades) > 0 else 0.0
        m.avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        m.avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
        m.avg_trade = float(trades.mean())
        m.std_trade = float(trades.std()) if len(trades) > 1 else 0.0
        m.best_trade = float(trades.max())
        m.worst_trade = float(trades.min())

        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        m.profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        m.expected_return = m.avg_trade

        cumulative = np.cumsum(trades)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        m.max_drawdown = float(drawdowns.max()) if len(drawdowns) > 0 else 0.0

        if len(drawdowns) > 0:
            sorted_dd = np.sort(drawdowns)
            m.expected_drawdown = float(np.percentile(sorted_dd, 75))
        else:
            m.expected_drawdown = 0.0

        if m.std_trade > 0:
            m.sharpe_ratio = float(m.avg_trade / m.std_trade * math.sqrt(len(trades)))
        else:
            m.sharpe_ratio = 0.0

        if m.max_drawdown > 0:
            annualized_return = m.avg_trade * len(trades)
            m.calmar_ratio = float(annualized_return / m.max_drawdown)
        else:
            m.calmar_ratio = 0.0 if m.avg_trade <= 0 else float("inf")

        m.max_consecutive_wins = self._max_consecutive(trades > 0)
        m.max_consecutive_losses = self._max_consecutive(trades < 0)

    @staticmethod
    def _max_consecutive(mask: np.ndarray) -> int:
        if len(mask) == 0:
            return 0
        max_count = 0
        current = 0
        for val in mask:
            if val:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count


# ──────────────────────────────────────────────────────
# Walk-Forward Validation
# ──────────────────────────────────────────────────────

def walk_forward_validation(
    model_factory,
    X: np.ndarray,
    y: np.ndarray,
    returns: np.ndarray | None = None,
    n_folds: int = 5,
    train_ratio: float = 0.7,
    rr_ratio: float = 1.0,
) -> list[WalkForwardResult]:
    """
    Walk-Forward Validation: entrena en una ventana creciente, evalua en la siguiente.

    model_factory: callable que retorna un modelo sklearn-like (fresh instance)
    """
    n = len(X)
    if n < n_folds * 2:
        return []

    fold_size = n // n_folds
    results: list[WalkForwardResult] = []
    protocol = BacktestProtocol(rr_ratio=rr_ratio)

    for i in range(n_folds):
        train_end = int(fold_size * (i + 1) * train_ratio) + fold_size * i
        test_start = train_end
        test_end = min(train_end + fold_size, n)

        if test_start >= n or test_end <= test_start:
            continue

        X_train, y_train = X[:train_end], y[:train_end]
        X_test, y_test = X[test_start:test_end], y[test_start:test_end]
        ret_test = returns[test_start:test_end] if returns is not None else None

        try:
            model = model_factory()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            report = protocol.evaluate(y_test, y_pred, returns=ret_test)

            results.append(WalkForwardResult(
                fold=i + 1,
                train_start=0,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                accuracy=report.metrics.accuracy,
                win_rate=report.metrics.win_rate,
                profit_factor=report.metrics.profit_factor,
                sharpe=report.metrics.sharpe_ratio,
                trades=report.metrics.total_trades,
            ))
        except Exception:
            continue

    return results


# ──────────────────────────────────────────────────────
# Monte Carlo Simulation
# ──────────────────────────────────────────────────────

def monte_carlo_simulation(
    trades: np.ndarray,
    iterations: int = 1000,
    confidence_levels: list[float] | None = None,
) -> MonteCarloResult:
    """
    Simula el orden de trades aleatoriamente N veces para estimar
    la distribucion de retornos y drawdowns.
    """
    if len(trades) == 0 or iterations < 1:
        return MonteCarloResult(
            iterations=0, median_return=0, percentile_5=0, percentile_25=0,
            percentile_75=0, percentile_95=0, prob_profit=0,
            median_max_drawdown=0, worst_max_drawdown=0, best_return=0, worst_return=0,
        )

    if confidence_levels is None:
        confidence_levels = [5, 25, 50, 75, 95]

    final_returns = np.zeros(iterations)
    max_drawdowns = np.zeros(iterations)

    for i in range(iterations):
        shuffled = np.random.permutation(trades)
        cumulative = np.cumsum(shuffled)
        final_returns[i] = cumulative[-1]
        running_max = np.maximum.accumulate(cumulative)
        dd = running_max - cumulative
        max_drawdowns[i] = dd.max()

    return MonteCarloResult(
        iterations=iterations,
        median_return=float(np.median(final_returns)),
        percentile_5=float(np.percentile(final_returns, 5)),
        percentile_25=float(np.percentile(final_returns, 25)),
        percentile_75=float(np.percentile(final_returns, 75)),
        percentile_95=float(np.percentile(final_returns, 95)),
        prob_profit=float(np.mean(final_returns > 0)),
        median_max_drawdown=float(np.median(max_drawdowns)),
        worst_max_drawdown=float(max_drawdowns.max()),
        best_return=float(final_returns.max()),
        worst_return=float(final_returns.min()),
    )


# ──────────────────────────────────────────────────────
# HTML Report Generator
# ──────────────────────────────────────────────────────

def generate_html_report(report: BacktestReport, output_path: str = "backtest_report.html") -> str:
    """Genera un reporte HTML exportable del backtest."""
    m = report.metrics
    mc = report.monte_carlo

    wfv_rows = ""
    for w in report.walk_forward:
        wfv_rows += f"""
        <tr>
          <td>{w.fold}</td>
          <td>{w.accuracy:.4f}</td>
          <td>{w.win_rate:.4f}</td>
          <td>{w.profit_factor:.2f}</td>
          <td>{w.sharpe:.2f}</td>
          <td>{w.trades}</td>
        </tr>"""

    mc_section = ""
    if mc:
        mc_section = f"""
      <div class="card">
        <h2>Monte Carlo Simulation ({mc.iterations} iterations)</h2>
        <div class="metrics-grid">
          <div class="metric"><span class="label">Median Return</span><span class="value">{mc.median_return:.2f}</span></div>
          <div class="metric"><span class="label">P5 Return</span><span class="value">{mc.percentile_5:.2f}</span></div>
          <div class="metric"><span class="label">P95 Return</span><span class="value">{mc.percentile_95:.2f}</span></div>
          <div class="metric"><span class="label">Prob. Profit</span><span class="value">{mc.prob_profit:.1%}</span></div>
          <div class="metric"><span class="label">Median Max DD</span><span class="value">{mc.median_max_drawdown:.2f}</span></div>
          <div class="metric"><span class="label">Worst Max DD</span><span class="value">{mc.worst_max_drawdown:.2f}</span></div>
        </div>
      </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Backtest Report — {report.model_name} — {report.pair}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 2rem; background: #f8f9fa; color: #1a1a1a; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.3rem; }}
  h2 {{ font-size: 1.1rem; margin-bottom: 0.8rem; color: #555; }}
  .subtitle {{ color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  .card {{ background: white; border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1.2rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.8rem; }}
  .metric {{ display: flex; flex-direction: column; gap: 0.15rem; }}
  .metric .label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: #888; }}
  .metric .value {{ font-size: 1.15rem; font-weight: 700; }}
  .good {{ color: #16a34a; }}
  .bad {{ color: #dc2626; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 0.5rem; background: #f1f5f9; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  td {{ padding: 0.5rem; border-bottom: 1px solid #e2e8f0; }}
  pre {{ background: #f1f5f9; padding: 0.8rem; border-radius: 6px; font-size: 0.78rem; overflow-x: auto; }}
</style>
</head>
<body>
  <h1>Backtest Report — {report.model_name}</h1>
  <div class="subtitle">{report.pair} · {report.timeframe} · {report.timestamp}</div>

  <div class="card">
    <h2>Classification Metrics</h2>
    <div class="metrics-grid">
      <div class="metric"><span class="label">Accuracy</span><span class="value {'good' if m.accuracy >= 0.6 else 'bad' if m.accuracy < 0.5 else ''}">{m.accuracy:.4f}</span></div>
      <div class="metric"><span class="label">Precision</span><span class="value">{m.precision:.4f}</span></div>
      <div class="metric"><span class="label">Recall</span><span class="value">{m.recall:.4f}</span></div>
      <div class="metric"><span class="label">F1 Score</span><span class="value">{m.f1:.4f}</span></div>
    </div>
  </div>

  <div class="card">
    <h2>Trading Metrics</h2>
    <div class="metrics-grid">
      <div class="metric"><span class="label">Total Trades</span><span class="value">{m.total_trades}</span></div>
      <div class="metric"><span class="label">Win Rate</span><span class="value {'good' if m.win_rate >= 0.5 else 'bad'}">{m.win_rate:.2%}</span></div>
      <div class="metric"><span class="label">Profit Factor</span><span class="value {'good' if m.profit_factor >= 1.5 else 'bad' if m.profit_factor < 1.0 else ''}">{m.profit_factor:.2f}</span></div>
      <div class="metric"><span class="label">Expected Return</span><span class="value">{m.expected_return:.4f}</span></div>
      <div class="metric"><span class="label">Avg Win</span><span class="value good">{m.avg_win:.4f}</span></div>
      <div class="metric"><span class="label">Avg Loss</span><span class="value bad">{m.avg_loss:.4f}</span></div>
      <div class="metric"><span class="label">Max Drawdown</span><span class="value bad">{m.max_drawdown:.4f}</span></div>
      <div class="metric"><span class="label">Sharpe Ratio</span><span class="value {'good' if m.sharpe_ratio >= 1.0 else ''}">{m.sharpe_ratio:.2f}</span></div>
      <div class="metric"><span class="label">Calmar Ratio</span><span class="value">{m.calmar_ratio:.2f}</span></div>
      <div class="metric"><span class="label">Max Consec. Wins</span><span class="value">{m.max_consecutive_wins}</span></div>
      <div class="metric"><span class="label">Max Consec. Losses</span><span class="value">{m.max_consecutive_losses}</span></div>
    </div>
  </div>

  {mc_section}

  <div class="card">
    <h2>Walk-Forward Validation</h2>
    <table>
      <thead><tr><th>Fold</th><th>Accuracy</th><th>Win Rate</th><th>Profit Factor</th><th>Sharpe</th><th>Trades</th></tr></thead>
      <tbody>{wfv_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Classification Report</h2>
    <pre>{m.classification_report or "N/A"}</pre>
  </div>
</body>
</html>"""

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass

    return html


# ──────────────────────────────────────────────────────
# CLI formatting (colorama) — sige el patron cmd_* del proyecto
# ──────────────────────────────────────────────────────

def cmd_backtest_report(report: BacktestReport) -> str:
    """Formatea un BacktestReport para consola con colorama."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        G = Fore.GREEN
        R = Fore.RED
        Y = Fore.YELLOW
        C = Fore.CYAN
        B = Fore.BLUE
        W = Fore.WHITE
        S = Style.RESET_ALL
    except Exception:
        G = R = Y = C = B = W = S = ""

    m = report.metrics
    lines: list[str] = []

    lines.append(f"\n{C}{'='*60}{S}")
    lines.append(f"{C}  BACKTEST REPORT — {report.model_name}{S}")
    lines.append(f"{C}  {report.pair} · {report.timeframe} · {report.timestamp}{S}")
    lines.append(f"{C}{'='*60}{S}\n")

    lines.append(f"{B}── Classification Metrics ──{S}")
    lines.append(f"  Accuracy:  {G if m.accuracy >= 0.6 else R if m.accuracy < 0.5 else Y}{m.accuracy:.4f}{S}")
    lines.append(f"  Precision: {m.precision:.4f}")
    lines.append(f"  Recall:    {m.recall:.4f}")
    lines.append(f"  F1 Score:  {m.f1:.4f}\n")

    lines.append(f"{B}── Trading Metrics ──{S}")
    lines.append(f"  Total Trades:     {m.total_trades}")
    lines.append(f"  Win Rate:         {G if m.win_rate >= 0.5 else R}{m.win_rate:.2%}{S}")
    lines.append(f"  Profit Factor:    {G if m.profit_factor >= 1.5 else R if m.profit_factor < 1.0 else Y}{m.profit_factor:.2f}{S}")
    lines.append(f"  Expected Return:  {m.expected_return:.4f}")
    lines.append(f"  Avg Win:          {G}{m.avg_win:.4f}{S}")
    lines.append(f"  Avg Loss:         {R}{m.avg_loss:.4f}{S}")
    lines.append(f"  Max Drawdown:     {R}{m.max_drawdown:.4f}{S}")
    lines.append(f"  Sharpe Ratio:     {G if m.sharpe_ratio >= 1.0 else Y}{m.sharpe_ratio:.2f}{S}")
    lines.append(f"  Calmar Ratio:     {m.calmar_ratio:.2f}")
    lines.append(f"  Max Consec Wins:  {G}{m.max_consecutive_wins}{S}")
    lines.append(f"  Max Consec Loss:  {R}{m.max_consecutive_losses}{S}\n")

    if report.walk_forward:
        lines.append(f"{B}── Walk-Forward Validation ({len(report.walk_forward)} folds) ──{S}")
        lines.append(f"  {'Fold':>4}  {'Acc':>8}  {'WinR':>8}  {'PF':>6}  {'Sharpe':>7}  {'Trades':>6}")
        for w in report.walk_forward:
            lines.append(f"  {w.fold:>4}  {w.accuracy:>8.4f}  {w.win_rate:>8.2%}  {w.profit_factor:>6.2f}  {w.sharpe:>7.2f}  {w.trades:>6}")
        avg_acc = np.mean([w.accuracy for w in report.walk_forward])
        avg_wr = np.mean([w.win_rate for w in report.walk_forward])
        lines.append(f"  {'AVG':>4}  {avg_acc:>8.4f}  {avg_wr:>8.2%}\n")

    if report.monte_carlo:
        mc = report.monte_carlo
        lines.append(f"{B}── Monte Carlo Simulation ({mc.iterations} iterations) ──{S}")
        lines.append(f"  Median Return:     {mc.median_return:.2f}")
        lines.append(f"  P5 / P95 Return:   {mc.percentile_5:.2f} / {mc.percentile_95:.2f}")
        lines.append(f"  Prob. Profit:      {G if mc.prob_profit >= 0.5 else R}{mc.prob_profit:.1%}{S}")
        lines.append(f"  Median Max DD:     {mc.median_max_drawdown:.2f}")
        lines.append(f"  Worst Max DD:      {R}{mc.worst_max_drawdown:.2f}{S}\n")

    if m.classification_report:
        lines.append(f"{B}── Classification Report ──{S}")
        lines.append(f"  {m.classification_report.replace(chr(10), chr(10) + '  ')}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Convenience: evaluate model with full protocol
# ──────────────────────────────────────────────────────

def evaluate_model(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    model_name: str = "",
    pair: str = "",
    timeframe: str = "",
    rr_ratio: float = 1.0,
    run_monte_carlo: bool = False,
    mc_iterations: int = 1000,
) -> BacktestReport:
    """
    Evalua un modelo entrenado con el protocolo estandar completo.
    Opcionalmente corre Monte Carlo si se proveen returns.
    """
    protocol = BacktestProtocol(rr_ratio=rr_ratio)
    y_pred = model.predict(X_test)
    report = protocol.evaluate(y_test, y_pred, returns=returns, model_name=model_name, pair=pair, timeframe=timeframe)

    if run_monte_carlo and returns is not None:
        trades = protocol._compute_trade_results(y_test, y_pred, np.asarray(returns))
        if len(trades) > 0:
            report.monte_carlo = monte_carlo_simulation(trades, iterations=mc_iterations)

    return report


def compare_models(
    models: dict[str, Any],
    X_test: np.ndarray,
    y_test: np.ndarray,
    returns: np.ndarray | None = None,
    rr_ratio: float = 1.0,
) -> dict[str, BacktestReport]:
    """
    Compara multiples modelos bajo el mismo protocolo.
    Retorna un dict {model_name: BacktestReport}.
    """
    results: dict[str, BacktestReport] = {}
    for name, model in models.items():
        try:
            report = evaluate_model(model, X_test, y_test, returns=returns, model_name=name, rr_ratio=rr_ratio)
            results[name] = report
        except Exception as e:
            results[name] = BacktestReport(
                metrics=BacktestMetrics(),
                model_name=name,
            )
            results[name].metrics.classification_report = f"Error: {e}"
    return results


def cmd_model_comparison(reports: dict[str, BacktestReport]) -> str:
    """Tabla comparativa en consola."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        G = Fore.GREEN
        R = Fore.RED
        Y = Fore.YELLOW
        C = Fore.CYAN
        S = Style.RESET_ALL
    except Exception:
        G = R = Y = C = S = ""

    if not reports:
        return "No hay modelos para comparar."

    lines = [f"\n{C}{'='*80}{S}", f"{C}  COMPARACION DE MODELOS — Backtest Protocol V.9{S}", f"{C}{'='*80}{S}\n"]

    header = f"  {'Modelo':<20} {'Accuracy':>10} {'WinRate':>10} {'PF':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>7}"
    lines.append(f"{Y}{header}{S}")
    lines.append(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*7}")

    for name, r in sorted(reports.items(), key=lambda kv: kv[1].metrics.accuracy, reverse=True):
        m = r.metrics
        acc_color = G if m.accuracy >= 0.6 else R if m.accuracy < 0.5 else ""
        wr_color = G if m.win_rate >= 0.5 else R
        pf_color = G if m.profit_factor >= 1.5 else R if m.profit_factor < 1.0 else ""
        sh_color = G if m.sharpe_ratio >= 1.0 else ""
        lines.append(
            f"  {name:<20} {acc_color}{m.accuracy:>10.4f}{S} {wr_color}{m.win_rate:>10.2%}{S} "
            f"{pf_color}{m.profit_factor:>8.2f}{S} {sh_color}{m.sharpe_ratio:>8.2f}{S} "
            f"{m.max_drawdown:>8.4f} {m.total_trades:>7}"
        )

    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from sklearn.datasets import make_classification
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier

    X, y = make_classification(n_samples=1000, n_features=20, n_classes=3, n_informative=10, random_state=42)
    returns = np.random.randn(1000) * 0.02

    split = int(len(X) * 0.7)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    ret_test = returns[split:]

    models = {
        "LogisticRegression": LogisticRegression(max_iter=500),
        "RandomForest": RandomForestClassifier(n_estimators=50, random_state=42),
    }

    for name, model in models.items():
        model.fit(X_train, y_train)

    reports = compare_models(models, X_test, y_test, returns=ret_test, run_monte_carlo=True if False else False)

    for name, r in reports.items():
        print(cmd_backtest_report(r))

    print(cmd_model_comparison(reports))

    wfv = walk_forward_validation(
        lambda: LogisticRegression(max_iter=500),
        X, y, returns=returns, n_folds=5,
    )
    if wfv:
        print(f"\n  Walk-Forward: {len(wfv)} folds, avg accuracy = {np.mean([w.accuracy for w in wfv]):.4f}")

    html = generate_html_report(reports["RandomForest"], "test_backtest_report.html")
    print(f"\n  HTML report generated: test_backtest_report.html ({len(html)} bytes)")
