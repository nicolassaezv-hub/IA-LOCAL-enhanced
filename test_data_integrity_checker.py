import unittest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil

from robustness.data_integrity_checker import (
    DataIssue,
    FileCheckResult,
    DataIntegrityReport,
    check_csv_integrity,
    run_data_integrity_check,
)


def create_sample_df(rows=150):
    dates = pd.date_range(start="2023-01-01", periods=rows, freq="1h")
    df = pd.DataFrame({
        "timestamp": dates.astype(str),
        "open": np.linspace(1.10, 1.15, rows),
        "high": np.linspace(1.11, 1.16, rows),
        "low": np.linspace(1.09, 1.14, rows),
        "close": np.linspace(1.10, 1.15, rows),
        "volume": np.random.randint(100, 1000, size=rows),
        "pair": ["EURUSD"] * rows,
        "RSI_14": np.linspace(30, 70, rows),
    })
    return df


class TestDataIntegrityChecker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_clean_csv(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(150)
        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.rows, 150)
        self.assertEqual(res.pair, "EURUSD")
        self.assertEqual(res.timeframe, "H1")
        self.assertEqual(len(res.issues), 0)

    def test_insufficient_rows(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(50)
        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertEqual(res.status, "error")
        self.assertTrue(any(i.issue_type == "insufficient_rows" for i in res.issues))

    def test_timestamp_issues(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(120)
        df["timestamp"] = df["timestamp"].astype(str)
        
        # Add duplicate timestamp
        df.loc[10, "timestamp"] = df.loc[9, "timestamp"]
        # Add invalid/NaT timestamp
        df.loc[20, "timestamp"] = "invalid_date_str"
        # Add out-of-order timestamp
        df.loc[30, "timestamp"] = "2020-01-01 00:00:00"

        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertEqual(res.status, "error")
        types = [i.issue_type for i in res.issues]
        self.assertIn("timestamp_nat", types)
        self.assertIn("duplicate_timestamps", types)
        self.assertIn("timestamps_not_sorted", types)

    def test_temporal_gaps(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(120)
        
        # Introduce a 10-hour gap at row 50
        dates = pd.date_range(start="2023-01-01", periods=120, freq="1h")
        dates_list = list(dates)
        dates_list[50:] = [d + pd.Timedelta(hours=10) for d in dates_list[50:]]
        df["timestamp"] = [d.strftime("%Y-%m-%d %H:%M:%S") for d in dates_list]

        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertTrue(any(i.issue_type == "temporal_gap" for i in res.issues))

    def test_ohlc_validity(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(120)
        
        # High < Low
        df.loc[5, "high"] = 1.00
        df.loc[5, "low"] = 1.50
        # Negative price
        df.loc[15, "close"] = -1.0
        # NaN in OHLC
        df.loc[25, "open"] = np.nan

        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertEqual(res.status, "error")
        types = [i.issue_type for i in res.issues]
        self.assertIn("ohlc_invalid", types)
        self.assertIn("ohlc_negative", types)
        self.assertIn("ohlc_nan", types)

    def test_volume_checks(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        
        # Test all-zero volume
        csv_file1 = h1_dir / "EURUSD_zero.csv"
        df1 = create_sample_df(120)
        df1["volume"] = 0
        df1.to_csv(csv_file1, index=False)

        res1 = check_csv_integrity(csv_file1)
        self.assertTrue(any(i.issue_type == "volume_all_zero" for i in res1.issues))

        # Test negative volume
        csv_file2 = h1_dir / "EURUSD_neg.csv"
        df2 = create_sample_df(120)
        df2.loc[12, "volume"] = -50
        df2.to_csv(csv_file2, index=False)

        res2 = check_csv_integrity(csv_file2)
        self.assertTrue(any(i.issue_type == "volume_negative" for i in res2.issues))

    def test_indicators_and_excess_nulls(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(120)
        
        # All NaN indicator
        df["RSI_14"] = np.nan
        # Excess nulls (>5%) in a non-indicator column
        df["custom_feature"] = 1.0
        df.loc[0:20, "custom_feature"] = np.nan  # 21/120 > 5%

        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        types = [i.issue_type for i in res.issues]
        self.assertIn("indicator_all_nan", types)
        self.assertIn("excess_nulls", types)

    def test_format_error(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        csv_file = h1_dir / "EURUSD.csv"
        df = create_sample_df(120)
        df["close"] = df["close"].astype(str)
        df.loc[10, "close"] = "non_numeric_text"

        df.to_csv(csv_file, index=False)

        res = check_csv_integrity(csv_file)
        self.assertTrue(any(i.issue_type == "format_error" for i in res.issues))

    def test_run_data_integrity_check(self):
        h1_dir = self.temp_dir / "H1"
        h1_dir.mkdir()
        
        # Clean file
        df1 = create_sample_df(120)
        df1.to_csv(h1_dir / "EURUSD.csv", index=False)

        # File with error
        df2 = create_sample_df(50)
        df2.to_csv(h1_dir / "GBPUSD.csv", index=False)

        report = run_data_integrity_check(self.temp_dir)
        self.assertIsInstance(report, DataIntegrityReport)
        self.assertEqual(report.total_files, 2)
        self.assertEqual(report.ok_count, 1)
        self.assertEqual(report.error_count, 1)
        
        md = report.to_markdown()
        self.assertIn("# 📊 Forex Data Integrity Report", md)
        self.assertIn("EURUSD.csv", md)
        self.assertIn("GBPUSD.csv", md)


if __name__ == "__main__":
    unittest.main()
