import numpy as np
import pandas as pd
from .predictor import ForexPredictor


class ForexBacktester:

    def __init__(self, initial_balance=10000, risk_per_trade=0.01):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.predictor = ForexPredictor()

    # -----------------------------
    # RUN BACKTEST ON HELD-OUT DATA
    # Accepts only the TEST portion (last 20%) to avoid leakage
    # -----------------------------
    def run(self, df: pd.DataFrame, test_ratio=0.20):
        split = int(len(df) * (1 - test_ratio))
        X_test = df.iloc[split:].copy().reset_index(drop=True)

        if len(X_test) == 0:
            return {"error": "Not enough rows for backtesting. Need at least 5 rows."}

        predictions = self.predictor.predict_batch(X_test)

        balance = self.initial_balance
        trades = []
        equity_curve = [balance]

        for i in range(len(X_test) - 1):
            row = X_test.iloc[i]
            pred = predictions[i]

            price_now  = row["close"]
            price_next = X_test["close"].iloc[i + 1]
            price_change = price_next - price_now

            direction  = pred["direction"]
            confidence = pred["confidence"]

            position_size = balance * self.risk_per_trade * confidence
            pnl = 0

            if direction == "bullish":
                pnl = position_size * (price_change / (price_now + 1e-9))
            elif direction == "bearish":
                pnl = -position_size * (price_change / (price_now + 1e-9))

            balance += pnl

            trades.append({
                "index"     : i,
                "direction" : direction,
                "confidence": round(confidence, 4),
                "pnl"       : round(pnl, 4),
                "balance"   : round(balance, 4),
            })
            equity_curve.append(balance)

        return self._summary(trades, equity_curve)

    # -----------------------------
    # PERFORMANCE METRICS
    # -----------------------------
    def _summary(self, trades, equity_curve):
        pnls  = [t["pnl"] for t in trades]
        wins  = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate     = len(wins) / len(pnls) if pnls else 0
        avg_win      = np.mean(wins)  if wins   else 0
        avg_loss     = np.mean(losses) if losses else 0
        profit_factor = (
            abs(sum(wins)) / abs(sum(losses))
            if losses and sum(losses) != 0 else float("inf")
        )
        total_return = equity_curve[-1] - self.initial_balance
        max_drawdown = self._compute_drawdown(equity_curve)

        return {
            "initial_balance" : self.initial_balance,
            "final_balance"   : round(equity_curve[-1], 2),
            "total_return"    : round(total_return, 2),
            "total_return_pct": round(total_return / self.initial_balance * 100, 2),
            "win_rate"        : round(win_rate, 4),
            "total_trades"    : len(pnls),
            "winning_trades"  : len(wins),
            "losing_trades"   : len(losses),
            "avg_win"         : round(avg_win, 4),
            "avg_loss"        : round(avg_loss, 4),
            "profit_factor"   : round(profit_factor, 4),
            "max_drawdown"    : round(max_drawdown, 4),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
        }

    def _compute_drawdown(self, equity_curve):
        peak   = equity_curve[0]
        max_dd = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / (peak + 1e-9)
            max_dd = max(max_dd, dd)
        return max_dd
