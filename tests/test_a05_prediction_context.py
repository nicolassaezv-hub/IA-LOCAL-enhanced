"""Isolated A-05 tests for PredictionContext safeguard diagnostics."""

from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from forex.prediction import prediction_context


class PredictionContextSafeguardTests(unittest.TestCase):
    def test_circuit_breaker_active_is_inverse_of_trading_open(self):
        breaker = types.SimpleNamespace(check=lambda: {"open": True})
        with patch(
            "forex.prediction.circuit_breaker.CircuitBreaker",
            return_value=breaker,
        ):
            active, state = prediction_context._circuit_breaker_state()
        self.assertFalse(active)
        self.assertTrue(state["open"])

        breaker.check = lambda: {"open": False, "reason": "drawdown"}
        with patch(
            "forex.prediction.circuit_breaker.CircuitBreaker",
            return_value=breaker,
        ):
            active, state = prediction_context._circuit_breaker_state()
        self.assertTrue(active)
        self.assertFalse(state["open"])

    def test_invalid_circuit_breaker_state_is_not_assumed_safe(self):
        breaker = types.SimpleNamespace(check=lambda: {})
        with patch(
            "forex.prediction.circuit_breaker.CircuitBreaker",
            return_value=breaker,
        ):
            with self.assertRaises(ValueError):
                prediction_context._circuit_breaker_state()

    def test_context_preserves_structured_critical_and_optional_failures(self):
        context = prediction_context.PredictionContext(pair="EURUSD")
        context.record_protection_error(
            "mtf",
            "mtf_evaluation_failed",
            "MTF failed",
            critical=True,
            exc=RuntimeError("mtf exploded"),
        )
        context.record_protection_error(
            "candlestick_patterns",
            "candlestick_patterns_failed",
            "Candlestick failed",
            critical=False,
        )

        payload = context.to_dict()
        self.assertEqual(payload["degraded_components"], ["mtf", "candlestick_patterns"])
        self.assertTrue(payload["protection_errors"][0]["critical"])
        self.assertEqual(payload["protection_errors"][0]["error"], "mtf exploded")
        self.assertFalse(payload["protection_errors"][1]["critical"])

    def test_invalid_risk_reasons_remain_serializable_under_risk_engine(self):
        context = prediction_context.PredictionContext(pair="EURUSD")
        context.risk = types.SimpleNamespace(
            to_dict=lambda: {
                "valid": False,
                "blocking_reasons": ["missing_account_equity"],
            }
        )
        context.record_protection_error(
            "risk_engine",
            "risk_result_invalid",
            "Risk sizing failed closed.",
            critical=True,
        )

        payload = context.to_dict()
        self.assertFalse(payload["risk_engine"]["valid"])
        self.assertEqual(
            payload["risk_engine"]["blocking_reasons"],
            ["missing_account_equity"],
        )
        self.assertEqual(payload["risk"], payload["risk_engine"])


if __name__ == "__main__":
    unittest.main()
