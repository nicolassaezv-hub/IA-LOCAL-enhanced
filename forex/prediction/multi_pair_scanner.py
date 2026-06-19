"""
multi_pair_scanner.py — Scan multiple CSV files and produce a ranked signal report.

Usage:
    from forex.prediction.multi_pair_scanner import MultiPairScanner

    scanner = MultiPairScanner()

    # Option A: pass a list of file paths
    report = scanner.scan([
        "data/EURUSD_H1.csv",
        "data/USDJPY_H1.csv",
        "data/XAUUSD_H1.csv",
    ])

    # Option B: scan an entire folder
    report = scanner.scan_folder("data/")

    scanner.print_report(report)
"""

import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from .csv_adapter         import adapt_csv
from .feature_engineering import build_features
from .dataset_builder     import DatasetBuilder
from .predictor           import ForexPredictor


# Supported file extensions
_SUPPORTED_EXT = (".csv", ".xlsx", ".xls")


class MultiPairScanner:
    """
    Loads multiple CSV files (one per pair), runs the signal pipeline on each,
    and returns a ranked report sorted by signal strength.

    Parameters
    ----------
    min_confidence : float  — minimum confidence to show BUY/SELL (else HOLD)
    min_adx        : float  — minimum ADX for trending market filter
    horizon        : int    — candles ahead for target building
    rr_ratio       : float  — risk/reward ratio
    max_workers    : int    — parallel threads for loading (default 4)
    """

    def __init__(
        self,
        min_confidence: float = 0.62,
        min_adx: float        = 22.0,
        horizon: int          = 10,
        rr_ratio: float       = 1.5,
        max_workers: int      = 4,
    ):
        self.predictor   = ForexPredictor(min_confidence=min_confidence, min_adx=min_adx)
        self.horizon     = horizon
        self.rr_ratio    = rr_ratio
        self.max_workers = max_workers

    # -------------------------------------------------------
    # SCAN A LIST OF FILES
    # -------------------------------------------------------
    def scan(self, filepaths: List[str], pair_map: dict = None) -> dict:
        """
        Scan a list of CSV file paths and return a consolidated signal report.

        Parameters
        ----------
        filepaths : list of file paths to scan
        pair_map  : optional dict mapping filepath → pair name
                    e.g. {"data/usdjpy.csv": "USDJPY"}
                    If not provided, pair is inferred from the filename.
        """
        pair_map = pair_map or {}
        results  = []
        errors   = []

        print(f"\n{'='*60}")
        print(f" MULTI-PAIR SCANNER — {len(filepaths)} pairs")
        print(f"{'='*60}")

        def _process(fp):
            pair = pair_map.get(fp)
            return self._scan_one(fp, pair=pair)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_process, fp): fp for fp in filepaths}
            for future in as_completed(futures):
                fp     = futures[future]
                result = future.result()
                if "error" in result:
                    errors.append(result)
                else:
                    results.append(result)

        # Sort: BUY first, then SELL, then HOLD — within each group by signal_strength desc
        priority = {"BUY": 0, "SELL": 1, "HOLD": 2}
        results.sort(key=lambda r: (priority.get(r["action"], 3), -r.get("signal_strength", 0)))

        buy_signals  = [r for r in results if r["action"] == "BUY"]
        sell_signals = [r for r in results if r["action"] == "SELL"]
        hold_signals = [r for r in results if r["action"] == "HOLD"]

        return {
            "type":          "multi_pair_scan",
            "total_scanned": len(filepaths),
            "successful":    len(results),
            "failed":        len(errors),
            "buy_count":     len(buy_signals),
            "sell_count":    len(sell_signals),
            "hold_count":    len(hold_signals),
            "signals":       results,
            "errors":        errors,
            "top_buy":       buy_signals[0]  if buy_signals  else None,
            "top_sell":      sell_signals[0] if sell_signals else None,
        }

    # -------------------------------------------------------
    # SCAN AN ENTIRE FOLDER
    # -------------------------------------------------------
    def scan_folder(self, folder: str, pair_map: dict = None) -> dict:
        """
        Discover all supported CSV/XLSX files in a folder and scan them.

        Parameters
        ----------
        folder   : path to folder containing CSV files (one per pair)
        pair_map : optional dict mapping filename → pair name
        """
        if not os.path.isdir(folder):
            return {"error": f"Folder not found: {folder}"}

        filepaths = [
            os.path.join(folder, f)
            for f in sorted(os.listdir(folder))
            if f.lower().endswith(_SUPPORTED_EXT)
        ]

        if not filepaths:
            return {"error": f"No CSV/XLSX files found in: {folder}"}

        print(f"[SCANNER] Found {len(filepaths)} files in {folder}")
        return self.scan(filepaths, pair_map=pair_map)

    # -------------------------------------------------------
    # INTERNAL: process one file
    # -------------------------------------------------------
    def _scan_one(self, filepath: str, pair: str = None) -> dict:
        try:
            df = adapt_csv(filepath, pair=pair)
            df = build_features(df)

            inferred_pair = str(df["pair"].iloc[-1]) if "pair" in df.columns else "UNKNOWN"

            builder = DatasetBuilder(df)
            X, _    = builder.build(horizon=self.horizon, rr_ratio=self.rr_ratio)

            if len(X) == 0:
                return {
                    "pair":  inferred_pair,
                    "file":  os.path.basename(filepath),
                    "error": "No rows after feature engineering.",
                }

            signal = self.predictor.signal(X, pair=inferred_pair)

            return {
                **signal,
                "file":        os.path.basename(filepath),
                "rows_loaded": len(X),
            }

        except Exception as e:
            return {
                "pair":  pair or os.path.basename(filepath),
                "file":  os.path.basename(filepath),
                "error": str(e),
                "trace": traceback.format_exc(),
            }

    # -------------------------------------------------------
    # PRINT FORMATTED REPORT TO CONSOLE
    # -------------------------------------------------------
    def print_report(self, report: dict):
        if "error" in report:
            print(f"[SCANNER ERROR] {report['error']}")
            return

        signals = report.get("signals", [])

        print(f"\n{'='*70}")
        print(f"  ASTRA MULTI-PAIR SIGNAL REPORT")
        print(f"  Scanned: {report['total_scanned']} pairs  |  "
              f"BUY: {report['buy_count']}  SELL: {report['sell_count']}  HOLD: {report['hold_count']}")
        print(f"{'='*70}")

        _ACTION_ICON = {"BUY": "▲", "SELL": "▼", "HOLD": "─"}

        for r in signals:
            if "error" in r:
                print(f"  ✗  {r.get('pair', '?'):<12}  ERROR: {r['error'][:50]}")
                continue

            action   = r.get("action",         "HOLD")
            pair     = r.get("pair",            "?")
            conf     = r.get("confidence",      0)
            strength = r.get("signal_strength", 0)
            regime   = r.get("regime",          "unknown")
            adx      = r.get("adx",             0)
            icon     = _ACTION_ICON.get(action, "─")

            # Strength bar (10 chars wide)
            bar_filled = int(strength / 10)
            bar        = "█" * bar_filled + "░" * (10 - bar_filled)

            reason = ""
            if action == "HOLD" and r.get("hold_reason"):
                reason = f"  ({r['hold_reason'][:45]})"

            print(
                f"  {icon}  {pair:<12}  {action:<5}  "
                f"conf={conf:.2f}  str=[{bar}]{strength:5.1f}  "
                f"adx={adx:5.1f}  {regime}{reason}"
            )

        if report.get("errors"):
            print(f"\n  Failed ({len(report['errors'])}):")
            for e in report["errors"]:
                print(f"    ✗ {e.get('file', '?')}: {e.get('error', '')[:60]}")

        print(f"{'='*70}")

        # Highlight top opportunities
        top_buy  = report.get("top_buy")
        top_sell = report.get("top_sell")

        if top_buy:
            print(f"\n  ▲ BEST BUY  → {top_buy['pair']}  "
                  f"(confidence={top_buy['confidence']:.2f}, "
                  f"strength={top_buy['signal_strength']})")
        if top_sell:
            print(f"  ▼ BEST SELL → {top_sell['pair']}  "
                  f"(confidence={top_sell['confidence']:.2f}, "
                  f"strength={top_sell['signal_strength']})")
        print()

    # -------------------------------------------------------
    # RETURN AS ASTRA-READY DICT (for ASTRA command routing)
    # -------------------------------------------------------
    def astra_summary(self, report: dict) -> str:
        """
        Compact one-paragraph summary for ASTRA to display inline.
        """
        if "error" in report:
            return f"Scanner error: {report['error']}"

        buy_count  = report["buy_count"]
        sell_count = report["sell_count"]
        hold_count = report["hold_count"]
        total      = report["total_scanned"]

        top_buy  = report.get("top_buy")
        top_sell = report.get("top_sell")

        lines = [
            f"Scanned {total} pairs — "
            f"BUY: {buy_count}  SELL: {sell_count}  HOLD: {hold_count}."
        ]

        if top_buy:
            lines.append(
                f"Strongest BUY: {top_buy['pair']} "
                f"(confidence={top_buy['confidence']:.2f}, "
                f"strength={top_buy['signal_strength']}, "
                f"regime={top_buy['regime']})."
            )
        if top_sell:
            lines.append(
                f"Strongest SELL: {top_sell['pair']} "
                f"(confidence={top_sell['confidence']:.2f}, "
                f"strength={top_sell['signal_strength']}, "
                f"regime={top_sell['regime']})."
            )
        if not top_buy and not top_sell:
            lines.append("No high-confidence signals at this time — all pairs showing HOLD.")

        return " ".join(lines)
