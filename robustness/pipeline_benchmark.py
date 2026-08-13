"""
robustness/pipeline_benchmark.py — Permanent pipeline benchmark system for ASTRA.

Records timing and performance statistics for each pipeline stage:
Stages: data_download, dataset_update, indicator_calc, training, evaluation,
        prediction, ranking_update, storage, total
"""

from __future__ import annotations

import os
import json
import time
import sqlite3
import statistics
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

# Standard pipeline stages for reference
STAGES = [
    "data_download",
    "dataset_update",
    "indicator_calc",
    "training",
    "evaluation",
    "prediction",
    "ranking_update",
    "storage",
    "total",
]

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "memory_db" / "benchmarks.db"


@dataclass
class StageTiming:
    """Dataclass holding timing information for a single pipeline stage execution."""
    stage_name: str
    duration_seconds: float
    timestamp: str
    pair: Optional[str] = None
    timeframe: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "metadata": self.metadata,
        }


class PipelineBenchmark:
    """
    Permanent pipeline benchmarking engine backed by SQLite.
    Records stage durations, calculates aggregations (avg/median/max),
    and formats reports.
    """

    def __init__(self, db_path: str | os.PathLike[str] = _DEFAULT_DB_PATH):
        self.db_path = str(Path(db_path).resolve())
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Creates the pipeline_benchmarks table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    pair TEXT,
                    timeframe TEXT,
                    metadata TEXT
                )
            """)
            conn.commit()

    def record_stage(
        self,
        stage_name: str,
        duration_seconds: float,
        pair: Optional[str] = None,
        timeframe: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StageTiming:
        """Explicitly records timing for a pipeline stage."""
        ts = datetime.now().isoformat()
        meta_dict = metadata if isinstance(metadata, dict) else {}
        meta_json = json.dumps(meta_dict)
        dur = float(duration_seconds)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_benchmarks
                (timestamp, stage_name, duration_seconds, pair, timeframe, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, stage_name, dur, pair, timeframe, meta_json),
            )
            conn.commit()

        return StageTiming(
            stage_name=stage_name,
            duration_seconds=dur,
            timestamp=ts,
            pair=pair,
            timeframe=timeframe,
            metadata=meta_dict,
        )

    @contextmanager
    def start_stage(
        self,
        stage_name: str,
        pair: Optional[str] = None,
        timeframe: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager to measure execution time of a code block.
        Yields a metadata dict that can be augmented inside the block.
        """
        t0 = time.perf_counter()
        meta = dict(metadata) if metadata else {}
        try:
            yield meta
        finally:
            elapsed = time.perf_counter() - t0
            self.record_stage(
                stage_name=stage_name,
                duration_seconds=elapsed,
                pair=pair,
                timeframe=timeframe,
                metadata=meta,
            )

    def get_history(
        self,
        limit: int = 50,
        pair: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> List[StageTiming]:
        """Retrieves history of recorded stage timings with optional filters."""
        query = (
            "SELECT timestamp, stage_name, duration_seconds, pair, timeframe, metadata "
            "FROM pipeline_benchmarks WHERE 1=1"
        )
        params: list[Any] = []
        if pair:
            query += " AND pair = ?"
            params.append(pair)
        if stage:
            query += " AND stage_name = ?"
            params.append(stage)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        results: List[StageTiming] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                try:
                    meta = json.loads(row["metadata"]) if row["metadata"] else {}
                except Exception:
                    meta = {}
                results.append(
                    StageTiming(
                        stage_name=row["stage_name"],
                        duration_seconds=float(row["duration_seconds"]),
                        timestamp=row["timestamp"],
                        pair=row["pair"],
                        timeframe=row["timeframe"],
                        metadata=meta,
                    )
                )
        return results

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculates avg, median, and max duration per stage."""
        stats: Dict[str, Dict[str, float]] = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stage_name, duration_seconds FROM pipeline_benchmarks")
            rows = cursor.fetchall()

        stage_data: Dict[str, List[float]] = {}
        for row in rows:
            s_name = row["stage_name"]
            dur = float(row["duration_seconds"])
            if s_name not in stage_data:
                stage_data[s_name] = []
            stage_data[s_name].append(dur)

        for s_name, durations in stage_data.items():
            if not durations:
                continue
            stats[s_name] = {
                "avg": round(statistics.mean(durations), 4),
                "median": round(statistics.median(durations), 4),
                "max": round(max(durations), 4),
                "min": round(min(durations), 4),
                "count": float(len(durations)),
            }

        return stats

    def to_markdown(self, limit: int = 20) -> str:
        """Formats stats and history into a Markdown report."""
        stats = self.get_stats()
        history = self.get_history(limit=limit)

        md = ["# Pipeline Benchmark Report\n"]
        md.append("## Stage Performance Summary\n")
        if not stats:
            md.append("*No benchmark records found.*\n")
        else:
            md.append("| Stage Name | Avg (s) | Median (s) | Max (s) | Min (s) | Count |")
            md.append("|------------|---------|------------|---------|---------|-------|")
            for stage_name, s in stats.items():
                md.append(
                    f"| {stage_name} | {s['avg']:.4f} | {s['median']:.4f} | "
                    f"{s['max']:.4f} | {s['min']:.4f} | {int(s['count'])} |"
                )
            md.append("")

        md.append(f"## Recent Stage Executions (Last {limit})\n")
        if not history:
            md.append("*No recent stage timing logs.*\n")
        else:
            md.append("| Timestamp | Stage | Pair | TF | Duration (s) | Metadata |")
            md.append("|-----------|-------|------|----|--------------|----------|")
            for h in history:
                pair_str = h.pair or "-"
                tf_str = h.timeframe or "-"
                meta_str = json.dumps(h.metadata) if h.metadata else "-"
                md.append(
                    f"| {h.timestamp} | {h.stage_name} | {pair_str} | "
                    f"{tf_str} | {h.duration_seconds:.4f} | {meta_str} |"
                )
            md.append("")

        return "\n".join(md)


_benchmark_singleton: Optional[PipelineBenchmark] = None


def get_benchmark(db_path: str | os.PathLike[str] = _DEFAULT_DB_PATH) -> PipelineBenchmark:
    """Returns a singleton instance of PipelineBenchmark."""
    global _benchmark_singleton
    if _benchmark_singleton is None:
        _benchmark_singleton = PipelineBenchmark(db_path=db_path)
    return _benchmark_singleton


def get_benchmark_evidence(
    limit: int = 50,
    pair: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Return real benchmark evidence with an explicit command/API status."""
    try:
        benchmark = get_benchmark()
        stats = benchmark.get_stats()
        history = benchmark.get_history(limit=limit, pair=pair, stage=stage)
    except Exception as exc:
        return {"status": "ERROR", "stats": {}, "history": [], "error": str(exc)}

    serialized_history = [item.to_dict() for item in history]
    status = "SUCCESS" if stats or serialized_history else "UNAVAILABLE"
    result: dict[str, Any] = {
        "status": status,
        "stats": stats,
        "history": serialized_history,
    }
    if status == "UNAVAILABLE":
        result["reason"] = "No benchmark records are available."
    return result


def cmd_benchmark(argstr: str = "") -> str:
    """CLI/tool-registry boundary for the pipeline benchmark."""
    try:
        limit = int(argstr.strip()) if argstr.strip() else 10
        if limit < 1 or limit > 1000:
            raise ValueError
    except ValueError:
        return "[ERROR] Uso: robustness benchmark [limit 1..1000]"

    evidence = get_benchmark_evidence(limit=limit)
    status = evidence["status"]
    if status == "ERROR":
        return f"[ERROR] Pipeline benchmark: {evidence.get('error', 'unknown error')}"
    if status == "UNAVAILABLE":
        return f"[UNAVAILABLE] Pipeline benchmark: {evidence['reason']}"

    lines = ["[SUCCESS] PIPELINE BENCHMARK", ""]
    for stage_name, data in sorted(evidence["stats"].items()):
        lines.append(
            f"  {stage_name}: avg={data.get('avg', 0):.3f}s | "
            f"median={data.get('median', 0):.3f}s | max={data.get('max', 0):.3f}s | "
            f"count={int(data.get('count', 0))}"
        )
    if evidence["history"]:
        lines.append(f"\n  Last {len(evidence['history'])} runs:")
        for item in evidence["history"]:
            lines.append(
                f"  [{item['timestamp']}] {item.get('pair')} {item.get('timeframe')} "
                f"{item['stage_name']}: {item['duration_seconds']:.3f}s"
            )
    return "\n".join(lines)
