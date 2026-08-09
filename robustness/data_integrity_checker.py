"""
Data Integrity Checker for Forex CSV Datasets.
Checks data quality, timestamp consistency, temporal gaps, OHLC validity, volume,
indicator availability, missing values, format errors, and minimum dataset size.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union, Dict, Tuple, Any
import pandas as pd
import numpy as np


@dataclass
class DataIssue:
    file: str
    issue_type: str
    severity: str  # 'error' | 'warning'
    detail: str
    recommendation: str
    row_numbers: Optional[List[int]] = None


@dataclass
class FileCheckResult:
    file: str
    pair: str
    timeframe: str
    rows: int
    issues: List[DataIssue] = field(default_factory=list)
    status: str = "ok"  # 'ok' | 'warning' | 'error'


@dataclass
class DataIntegrityReport:
    results: List[FileCheckResult] = field(default_factory=list)
    total_files: int = 0
    ok_count: int = 0
    warning_count: int = 0
    error_count: int = 0

    def to_markdown(self) -> str:
        """Generate a structured Markdown report summarizing data integrity checks."""
        lines = [
            "# 📊 Forex Data Integrity Report",
            "",
            "## Summary",
            f"- **Total Files Checked:** {self.total_files}",
            f"- **OK Files:** {self.ok_count}",
            f"- **Warning Files:** {self.warning_count}",
            f"- **Error Files:** {self.error_count}",
            "",
            "## Overview Table",
            "| File | Pair | Timeframe | Rows | Status | Issues Count |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for res in self.results:
            status_badge = (
                "🟢 OK" if res.status == "ok"
                else ("🟡 WARNING" if res.status == "warning" else "🔴 ERROR")
            )
            lines.append(
                f"| `{res.file}` | {res.pair} | {res.timeframe} | {res.rows} | {status_badge} | {len(res.issues)} |"
            )

        lines.append("")
        lines.append("## Detailed File Results")

        for res in self.results:
            status_badge = (
                "🟢 OK" if res.status == "ok"
                else ("🟡 WARNING" if res.status == "warning" else "🔴 ERROR")
            )
            lines.append(f"\n### `{res.file}` ({status_badge})")
            lines.append(f"- **Pair:** {res.pair} | **Timeframe:** {res.timeframe} | **Rows:** {res.rows}")
            if not res.issues:
                lines.append("- *No data integrity issues found.*")
            else:
                lines.append("- **Issues Found:**")
                for i, issue in enumerate(res.issues, 1):
                    sev_badge = "🚨 ERROR" if issue.severity == "error" else "⚠️ WARNING"
                    rows_str = ""
                    if issue.row_numbers:
                        row_sample = issue.row_numbers[:10]
                        rows_str = f" (Rows: {', '.join(map(str, row_sample))}{'...' if len(issue.row_numbers) > 10 else ''})"
                    lines.append(f"  {i}. **{sev_badge}** [`{issue.issue_type}`]{rows_str}: {issue.detail}")
                    lines.append(f"     - *Recommendation:* {issue.recommendation}")

        return "\n".join(lines)


# Gap thresholds per timeframe
GAP_THRESHOLDS: Dict[str, pd.Timedelta] = {
    "H1": pd.Timedelta(hours=4),
    "H4": pd.Timedelta(hours=16),
    "D1": pd.Timedelta(hours=72),
    "M1": pd.Timedelta(minutes=15),
    "M5": pd.Timedelta(minutes=30),
    "M15": pd.Timedelta(hours=2),
    "M30": pd.Timedelta(hours=3),
    "H12": pd.Timedelta(hours=48),
    "W1": pd.Timedelta(days=21),
    "MN": pd.Timedelta(days=60),
}
DEFAULT_GAP_THRESHOLD = pd.Timedelta(hours=24)

KNOWN_INDICATORS = {
    "RSI_14", "ATR_14", "EMA20", "EMA50", "EMA200", "MACD",
    "MACD_SIGNAL", "MACD_HIST", "SMA20", "SMA50", "SMA200",
    "BB_UPPER", "BB_LOWER", "BB_MIDDLE", "STOCH_K", "STOCH_D"
}


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Find a column in df matching any candidate name (case-insensitive)."""
    col_map = {str(c).lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower().strip() in col_map:
            return col_map[cand.lower().strip()]
    return None


def _extract_pair_and_timeframe(file_path: Path, df: Optional[pd.DataFrame] = None) -> Tuple[str, str]:
    """Extract currency pair and timeframe from directory layout, filename, or CSV content."""
    valid_tfs = {"H1", "H4", "D1", "M1", "M5", "M15", "M30", "H12", "W1", "MN"}
    
    # 1. Timeframe from parent folder
    timeframe = "UNKNOWN"
    parent_name = file_path.parent.name.upper()
    if parent_name in valid_tfs:
        timeframe = parent_name
    else:
        # Check filename stem for timeframe
        stem_upper = file_path.stem.upper()
        parts = stem_upper.split("_")
        for tf in valid_tfs:
            if tf in parts or stem_upper.endswith(tf):
                timeframe = tf
                break

    # 2. Pair from dataframe column or filename
    pair = "UNKNOWN"
    if df is not None and "pair" in df.columns:
        pair_series = df["pair"].dropna().astype(str)
        if not pair_series.empty:
            pair = pair_series.iloc[0].strip().upper()

    if pair == "UNKNOWN":
        stem = file_path.stem
        clean_stem = stem.replace("test_", "").replace("TEST_", "")
        for tf in valid_tfs:
            clean_stem = clean_stem.replace(f"_{tf}", "").replace(f"{tf}_", "").replace(tf, "")
        clean_stem = clean_stem.strip("_")
        if clean_stem:
            pair = clean_stem.upper()

    return pair, timeframe


def check_csv_integrity(file_path: Union[str, Path]) -> FileCheckResult:
    """
    Perform complete data integrity checks on a single Forex CSV dataset.
    
    Checks conducted:
    1. Timestamps (ascending order, no duplicates, no NaT)
    2. Temporal gaps (exceeding timeframe limit)
    3. OHLC validity (H>=L, H>=O, H>=C, L<=O, L<=C, price > 0, no NaN)
    4. Volume (no negative, check all-zero)
    5. Missing indicators (check if indicator columns are all NaN)
    6. Excess nulls (column null ratio > 5%)
    7. Format errors (parseable timestamps, numeric columns)
    8. Minimum row count (>= 100 rows)
    """
    file_path = Path(file_path)
    file_str = str(file_path)
    issues: List[DataIssue] = []

    # Try reading the CSV
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        pair, timeframe = _extract_pair_and_timeframe(file_path)
        issue = DataIssue(
            file=file_str,
            issue_type="file_read_error",
            severity="error",
            detail=f"Could not read CSV file: {str(e)}",
            recommendation=f"Regenerate this dataset: generar csvs forex {timeframe}",
            row_numbers=None,
        )
        return FileCheckResult(
            file=file_str,
            pair=pair,
            timeframe=timeframe,
            rows=0,
            issues=[issue],
            status="error",
        )

    pair, timeframe = _extract_pair_and_timeframe(file_path, df)
    rows = len(df)

    # --- Check 8: Minimum Row Count ---
    if rows < 100:
        issues.append(
            DataIssue(
                file=file_str,
                issue_type="insufficient_rows",
                severity="error",
                detail=f"Dataset has only {rows} rows (at least 100 rows required for training)",
                recommendation=f"Regenerate dataset with more historical data: generar csvs forex {timeframe}",
                row_numbers=None,
            )
        )

    # --- Check 7 & 1: Timestamp parseability & validity ---
    ts_col = _find_column(df, ["timestamp", "time", "datetime", "date"])
    if ts_col is None:
        issues.append(
            DataIssue(
                file=file_str,
                issue_type="missing_timestamp_column",
                severity="error",
                detail="No timestamp column found in CSV dataset",
                recommendation=f"Regenerate dataset with timestamp column: generar csvs forex {timeframe}",
                row_numbers=None,
            )
        )
        ts_parsed = None
    else:
        # Convert to datetime
        ts_raw = df[ts_col]
        ts_parsed = pd.to_datetime(ts_raw, errors="coerce")

        # 1c. Check NaT (unparseable / missing timestamps)
        nat_mask = ts_parsed.isna()
        if nat_mask.any():
            nat_rows = df.index[nat_mask].tolist()
            issues.append(
                DataIssue(
                    file=file_str,
                    issue_type="timestamp_nat",
                    severity="error",
                    detail=f"{len(nat_rows)} row(s) contain invalid or NaT timestamps at row(s) {nat_rows[:10]}",
                    recommendation="Remove or fix rows with invalid timestamps",
                    row_numbers=nat_rows,
                )
            )

        # Filter valid timestamps for duplicate & gap & ordering checks
        valid_ts_mask = ts_parsed.notna()
        valid_ts = ts_parsed[valid_ts_mask]

        # 1b. Check duplicate timestamps
        dup_mask = valid_ts.duplicated(keep=False)
        if dup_mask.any():
            dup_rows = valid_ts.index[dup_mask].tolist()
            dup_count = valid_ts.duplicated().sum()
            issues.append(
                DataIssue(
                    file=file_str,
                    issue_type="duplicate_timestamps",
                    severity="error",
                    detail=f"{dup_count} duplicate timestamp(s) found at row(s) {dup_rows[:10]}",
                    recommendation="Remove duplicate rows and re-save",
                    row_numbers=dup_rows,
                )
            )

        # 1a. Check sorted ascending
        if not valid_ts.is_monotonic_increasing:
            diffs = valid_ts.diff()
            out_of_order_mask = diffs < pd.Timedelta(0)
            out_of_order_rows = valid_ts.index[out_of_order_mask].tolist()
            issues.append(
                DataIssue(
                    file=file_str,
                    issue_type="timestamps_not_sorted",
                    severity="error",
                    detail=f"Timestamps are not sorted ascending ({len(out_of_order_rows)} out-of-order timestamps found at row(s) {out_of_order_rows[:10]})",
                    recommendation="Sort dataset by timestamp in ascending order",
                    row_numbers=out_of_order_rows,
                )
            )

        # --- Check 2: Temporal Gaps ---
        if len(valid_ts) > 1:
            sorted_ts = valid_ts.sort_values()
            diffs = sorted_ts.diff()
            threshold = GAP_THRESHOLDS.get(timeframe, DEFAULT_GAP_THRESHOLD)
            gap_mask = diffs > threshold
            if gap_mask.any():
                gap_rows = sorted_ts.index[gap_mask].tolist()
                max_gap = diffs.max()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="temporal_gap",
                        severity="warning",
                        detail=f"{len(gap_rows)} unexpected temporal gap(s) exceeding {threshold} threshold (max gap: {max_gap}) at row(s) {gap_rows[:10]}",
                        recommendation=f"Verify dataset continuity for timeframe {timeframe} or fill missing periods: generar csvs forex {timeframe}",
                        row_numbers=gap_rows,
                    )
                )

    # --- Check 3: OHLC Validity ---
    col_open = _find_column(df, ["open", "open_price"])
    col_high = _find_column(df, ["high", "high_price"])
    col_low = _find_column(df, ["low", "low_price"])
    col_close = _find_column(df, ["close", "close_price"])

    ohlc_cols = [col_open, col_high, col_low, col_close]
    if None in ohlc_cols:
        missing_names = [name for name, col in zip(["open", "high", "low", "close"], ohlc_cols) if col is None]
        issues.append(
            DataIssue(
                file=file_str,
                issue_type="missing_ohlc_columns",
                severity="error",
                detail=f"Missing OHLC column(s): {', '.join(missing_names)}",
                recommendation="Ensure dataset includes open, high, low, close columns",
                row_numbers=None,
            )
        )
    else:
        # Check 7 (format error): Numeric OHLC
        non_numeric_ohlc = False
        for c_name in ohlc_cols:
            raw_series = df[c_name]
            num_series = pd.to_numeric(raw_series, errors="coerce")
            invalid_mask = raw_series.notna() & num_series.isna()
            if invalid_mask.any():
                bad_rows = df.index[invalid_mask].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="format_error",
                        severity="error",
                        detail=f"Column '{c_name}' contains non-numeric values at row(s) {bad_rows[:10]}",
                        recommendation=f"Convert or clean non-numeric values in '{c_name}'",
                        row_numbers=bad_rows,
                    )
                )
                non_numeric_ohlc = True

        if not non_numeric_ohlc:
            # 3a. Check NaN in OHLC
            ohlc_df = df[[col_open, col_high, col_low, col_close]].apply(pd.to_numeric, errors="coerce")
            nan_mask = ohlc_df.isna().any(axis=1)
            if nan_mask.any():
                nan_rows = df.index[nan_mask].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="ohlc_nan",
                        severity="error",
                        detail=f"{len(nan_rows)} row(s) contain NaN values in OHLC columns at row(s) {nan_rows[:10]}",
                        recommendation="Remove rows with NaN values in OHLC or interpolate missing values",
                        row_numbers=nan_rows,
                    )
                )

            # 3b. Check negative/zero prices
            neg_mask = (
                (ohlc_df[col_open] <= 0)
                | (ohlc_df[col_high] <= 0)
                | (ohlc_df[col_low] <= 0)
                | (ohlc_df[col_close] <= 0)
            )
            if neg_mask.any():
                neg_rows = df.index[neg_mask].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="ohlc_negative",
                        severity="error",
                        detail=f"{len(neg_rows)} row(s) contain non-positive prices (<= 0) at row(s) {neg_rows[:10]}",
                        recommendation="Fix or remove invalid negative/zero price rows",
                        row_numbers=neg_rows,
                    )
                )

            # 3c. Check OHLC relationships (H>=L, H>=O, H>=C, L<=O, L<=C)
            invalid_rel_mask = (
                (ohlc_df[col_high] < ohlc_df[col_low])
                | (ohlc_df[col_high] < ohlc_df[col_open])
                | (ohlc_df[col_high] < ohlc_df[col_close])
                | (ohlc_df[col_low] > ohlc_df[col_open])
                | (ohlc_df[col_low] > ohlc_df[col_close])
            )
            if invalid_rel_mask.any():
                invalid_rows = df.index[invalid_rel_mask].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="ohlc_invalid",
                        severity="error",
                        detail=f"{len(invalid_rows)} row(s) violate OHLC logic (high>=low, high>=open/close, low<=open/close) at row(s) {invalid_rows[:10]}",
                        recommendation="Recalculate or fix inconsistent OHLC candle values",
                        row_numbers=invalid_rows,
                    )
                )

    # --- Check 4: Volume ---
    col_vol = _find_column(df, ["volume", "vol", "tick_volume", "real_volume"])
    if col_vol is not None:
        vol_num = pd.to_numeric(df[col_vol], errors="coerce")
        # Format error if conversion introduced NaNs
        invalid_vol_mask = df[col_vol].notna() & vol_num.isna()
        if invalid_vol_mask.any():
            bad_rows = df.index[invalid_vol_mask].tolist()
            issues.append(
                DataIssue(
                    file=file_str,
                    issue_type="format_error",
                    severity="error",
                    detail=f"Volume column '{col_vol}' contains non-numeric values at row(s) {bad_rows[:10]}",
                    recommendation=f"Clean non-numeric entries in column '{col_vol}'",
                    row_numbers=bad_rows,
                )
            )
        else:
            # Negative volume
            neg_vol_mask = vol_num < 0
            if neg_vol_mask.any():
                neg_vol_rows = df.index[neg_vol_mask].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="volume_negative",
                        severity="error",
                        detail=f"{len(neg_vol_rows)} row(s) contain negative volume values at row(s) {neg_vol_rows[:10]}",
                        recommendation="Fix or remove negative volume values",
                        row_numbers=neg_vol_rows,
                    )
                )

            # All-zero volume
            valid_vols = vol_num.dropna()
            if len(valid_vols) == 0 or (valid_vols == 0).all():
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="volume_all_zero",
                        severity="warning",
                        detail=f"Volume column '{col_vol}' contains all zero or null values",
                        recommendation=f"Regenerate dataset with real or tick volume data: generar csvs forex {timeframe}",
                        row_numbers=None,
                    )
                )

    # --- Check 5: Missing Indicators ---
    # Detect indicator columns
    indicator_cols = []
    standard_non_indicators = {"timestamp", "time", "date", "datetime", "open", "high", "low", "close", "volume", "vol", "pair"}
    for c in df.columns:
        c_clean = str(c).upper().strip()
        if c_clean in KNOWN_INDICATORS or any(ind in c_clean for ind in ["RSI", "ATR", "EMA", "SMA", "MACD", "BB_"]):
            indicator_cols.append(c)
        elif str(c).lower().strip() not in standard_non_indicators:
            indicator_cols.append(c)

    flagged_indicator_cols = set()
    for ind_col in indicator_cols:
        if df[ind_col].isna().all():
            flagged_indicator_cols.add(ind_col)
            issues.append(
                DataIssue(
                    file=file_str,
                    issue_type="indicator_all_nan",
                    severity="warning",
                    detail=f"Indicator column '{ind_col}' contains 100% NaN values",
                    recommendation=f"Recalculate indicator '{ind_col}' or regenerate dataset: generar csvs forex {timeframe}",
                    row_numbers=None,
                )
            )

    # --- Check 6: Excess Nulls (>5% null ratio) ---
    for c in df.columns:
        # Skip if already flagged as all NaN indicator or all zero/null volume
        if c in flagged_indicator_cols:
            continue
        null_count = df[c].isna().sum()
        if rows > 0:
            null_ratio = null_count / rows
            if null_ratio > 0.05:
                null_rows = df.index[df[c].isna()].tolist()
                issues.append(
                    DataIssue(
                        file=file_str,
                        issue_type="excess_nulls",
                        severity="warning",
                        detail=f"Column '{c}' has {null_ratio * 100:.1f}% missing values ({null_count}/{rows} rows)",
                        recommendation=f"Fill missing values in column '{c}' using interpolation or regenerate dataset: generar csvs forex {timeframe}",
                        row_numbers=null_rows,
                    )
                )

    # Determine overall status
    has_error = any(issue.severity == "error" for issue in issues)
    has_warning = any(issue.severity == "warning" for issue in issues)
    status = "error" if has_error else ("warning" if has_warning else "ok")

    return FileCheckResult(
        file=file_str,
        pair=pair,
        timeframe=timeframe,
        rows=rows,
        issues=issues,
        status=status,
    )


def run_data_integrity_check(csv_dir: Union[str, Path] = "CSVs") -> DataIntegrityReport:
    """
    Run data integrity check across all Forex CSV datasets in the specified directory.
    
    Args:
        csv_dir: Path to directory containing CSVs or specific subfolders (e.g., CSVs/H1, CSVs/H4, CSVs/D1).
        
    Returns:
        DataIntegrityReport containing individual file results and summary statistics.
    """
    path = Path(csv_dir)
    file_paths: List[Path] = []

    if path.is_file():
        if path.suffix.lower() == ".csv":
            file_paths = [path]
    elif path.is_dir():
        file_paths = sorted([p for p in path.rglob("*.csv") if p.is_file()])

    results: List[FileCheckResult] = []
    ok_count = 0
    warning_count = 0
    error_count = 0

    for file_p in file_paths:
        res = check_csv_integrity(file_p)
        results.append(res)
        if res.status == "ok":
            ok_count += 1
        elif res.status == "warning":
            warning_count += 1
        elif res.status == "error":
            error_count += 1

    return DataIntegrityReport(
        results=results,
        total_files=len(results),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
    )
