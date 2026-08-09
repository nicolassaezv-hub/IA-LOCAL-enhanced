"""
analytics_memory.py

ASTRA Analytics Memory System

Purpose:
- Store analytics reports
- Prevent duplicate processing
- Store compressed summaries
- Persist findings into long-term memory
- Retrieve previous analyses

Designed for:
- Forex datasets
- CSV analytics
- Future ML reports
- Financial research workflows
"""

import json
import hashlib

from datetime import datetime

from memory_router import (
    save_chat,
    save_temp,
    get_temp
)


class AnalyticsMemory:

    def __init__(self):

        self.redis_prefix = "analytics"

    # ==================================================
    # ID GENERATION
    # ==================================================

    def generate_id(self, filepath):

        return hashlib.md5(
            filepath.encode("utf-8")
        ).hexdigest()

    # ==================================================
    # REPORT COMPRESSION
    # ==================================================

    def compress_report(self, report):

        if not isinstance(report, dict):

            return {
                "summary":
                    str(report)
            }

        summary = {}

        # --------------------------
        # DATASET
        # --------------------------

        dataset = report.get(
            "dataset",
            {}
        )

        summary["dataset"] = {

            "rows":
                dataset.get("rows"),

            "columns":
                dataset.get("columns")
        }

        # --------------------------
        # VOLATILITY
        # --------------------------

        if "volatility" in report:

            summary["volatility"] = {

                "mean":
                    report["volatility"].get(
                        "mean"
                    ),

                "std":
                    report["volatility"].get(
                        "std"
                    )
            }

        # --------------------------
        # TREND
        # --------------------------

        if "trend" in report:

            summary["trend"] = {

                "bullish_ratio":
                    report["trend"].get(
                        "bullish_ratio"
                    ),

                "bearish_ratio":
                    report["trend"].get(
                        "bearish_ratio"
                    )
            }

        # --------------------------
        # REGIMES
        # --------------------------

        if "regimes" in report:

            summary["regimes"] = report[
                "regimes"
            ]

        return summary

    # ==================================================
    # SAVE ANALYSIS
    # ==================================================

    def save_analysis(
        self,
        filepath,
        report
    ):

        analysis_id = (
            self.generate_id(filepath)
        )

        compressed = (
            self.compress_report(
                report
            )
        )

        payload = {

            "analysis_id":
                analysis_id,

            "file":
                filepath,

            "created":
                datetime.now().isoformat(),

            "compressed":
                compressed,

            "full_report":
                report
        }

        save_temp(
            f"{self.redis_prefix}:{analysis_id}",
            json.dumps(payload)
        )

        return analysis_id

    # ==================================================
    # LOAD ANALYSIS
    # ==================================================

    def load_analysis(
        self,
        analysis_id
    ):

        data = get_temp(
            f"{self.redis_prefix}:{analysis_id}"
        )

        if not data:

            return None

        return json.loads(data)

    # ==================================================
    # GET BY FILE
    # ==================================================

    def get_by_file(
        self,
        filepath
    ):

        analysis_id = (
            self.generate_id(filepath)
        )

        return self.load_analysis(
            analysis_id
        )

    # ==================================================
    # EXISTS
    # ==================================================

    def exists(
        self,
        filepath
    ):

        analysis_id = (
            self.generate_id(filepath)
        )

        result = get_temp(
            f"{self.redis_prefix}:{analysis_id}"
        )

        return result is not None

    # ==================================================
    # STORE SUMMARY INTO MEMORY
    # ==================================================

    def store_summary_memory(
        self,
        filepath,
        report
    ):

        summary = (
            self.compress_report(
                report
            )
        )

        memory_text = (
            f"Forex analysis saved.\n"
            f"File: {filepath}\n\n"
            f"{json.dumps(summary, indent=2)}"
        )

        save_chat(
            f"Analysis of {filepath}",
            memory_text
        )

        return True

    # ==================================================
    # STORE FULL ANALYSIS
    # ==================================================

    def remember_analysis(
        self,
        filepath,
        report
    ):

        analysis_id = (
            self.save_analysis(
                filepath,
                report
            )
        )

        self.store_summary_memory(
            filepath,
            report
        )

        return analysis_id

    # ==================================================
    # ANALYSIS METADATA
    # ==================================================

    def get_metadata(
        self,
        filepath
    ):

        analysis = self.get_by_file(
            filepath
        )

        if analysis is None:

            return None

        return {

            "analysis_id":
                analysis.get(
                    "analysis_id"
                ),

            "file":
                analysis.get(
                    "file"
                ),

            "created":
                analysis.get(
                    "created"
                )
        }

    # ==================================================
    # SUMMARY ONLY
    # ==================================================

    def get_summary(
        self,
        filepath
    ):

        analysis = self.get_by_file(
            filepath
        )

        if analysis is None:

            return None

        return analysis.get(
            "compressed"
        )

    # ==================================================
    # FULL REPORT
    # ==================================================

    def get_full_report(
        self,
        filepath
    ):

        analysis = self.get_by_file(
            filepath
        )

        if analysis is None:

            return None

        return analysis.get(
            "full_report"
        )

    # ==================================================
    # DELETE ANALYSIS
    # ==================================================

    def delete_analysis(
        self,
        filepath
    ):

        """
        Placeholder.

        Implement later when
        memory_router gets delete support.
        """

        return False

    # ==================================================
    # STATUS
    # ==================================================

    def status(self):

        return {

            "module":
                "AnalyticsMemory",

            "backend":
                "memory_router",

            "ready":
                True
        }


# ======================================================
# GLOBAL INSTANCE
# ======================================================

analytics_memory = AnalyticsMemory()


# ======================================================
# WRAPPER FUNCTIONS
# ======================================================

def remember_forex_analysis(
    filepath,
    report
):

    return (
        analytics_memory.remember_analysis(
            filepath,
            report
        )
    )


def load_forex_analysis(
    filepath
):

    return (
        analytics_memory.get_full_report(
            filepath
        )
    )


def get_forex_summary(
    filepath
):

    return (
        analytics_memory.get_summary(
            filepath
        )
    )


def analysis_exists(
    filepath
):

    return (
        analytics_memory.exists(
            filepath
        )
    )
