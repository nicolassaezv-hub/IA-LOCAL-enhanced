import numpy as np
import pandas as pd

from .predictor import ForexPredictor


class ForexBacktester:

    def __init__(
        self,
        initial_balance=10000,
        risk_per_trade=0.01
    ):

        self.initial_balance = initial_balance
        self.balance = initial_balance

        self.risk_per_trade = risk_per_trade

        self.predictor = ForexPredictor()

        self.trades = []
        self.equity_curve = []

    # -----------------------------
    # RUN BACKTEST
    # -----------------------------
    def run(self, df: pd.DataFrame):

        X = df.copy()

        predictions = self.predictor.predict_batch(X)

        for i in range(len(df)):

            row = df.iloc[i]
            pred = predictions[i]

            price_change = 0

            # Simulate next step return (realistic proxy)
            if i < len(df) - 1:

                price_change = (
                    df["close"].iloc[i + 1]
                    - row["close"]
                )

            direction = pred["direction"]
            confidence = pred["confidence"]

            # -----------------------------
            # TRADE LOGIC
            # -----------------------------
            position_size = (
                self.balance * self.risk_per_trade * confidence
            )

            pnl = 0

            if direction == "bullish":

                pnl = position_size * (price_change / row["close"])

            elif direction == "bearish":

                pnl = -position_size * (price_change / row["close"])

            # update balance
            self.balance += pnl

            self.trades.append({
                "index": i,
                "direction": direction,
                "confidence": confidence,
                "pnl": pnl,
                "balance": self.balance
            })

            self.equity_curve.append(self.balance)

        return self.summary()

    # -----------------------------
    # PERFORMANCE METRICS
    # -----------------------------
    def summary(self):

        pnls = [t["pnl"] for t in self.trades]

        wins = len([p for p in pnls if p > 0])
        losses = len([p for p in pnls if p <= 0])

        total_return = (
            self.balance - self.initial_balance
        )

        win_rate = (
            wins / len(pnls) if pnls else 0
        )

        max_drawdown = self.compute_drawdown()

        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "total_return": total_return,
            "win_rate": win_rate,
            "total_trades": len(pnls),
            "max_drawdown": max_drawdown
        }

    # -----------------------------
    # DRAWDOWN CALCULATION
    # -----------------------------
    def compute_drawdown(self):

        peak = self.equity_curve[0]
        max_dd = 0

        for value in self.equity_curve:

            if value > peak:
                peak = value

            drawdown = (peak - value) / peak

            max_dd = max(max_dd, drawdown)

        return max_dd
