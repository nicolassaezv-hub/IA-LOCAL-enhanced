#!/usr/bin/env python3
"""
ASTRA Process Monitor & Supervisor
===================================
Monitors the health of ASTRA workspace components without supervising them:
1. API availability (FastAPI on port 8000 /health)
2. SQLite database integrity and accessibility
3. Freshness of scheduled execution cycles (H1, H4, D1)

systemd remains the sole production restart authority.
"""

import sys
import os
import time
import signal
import sqlite3
import urllib.request
import urllib.error
import logging
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configuration from environment variables
INTERVAL_SECONDS = int(os.environ.get("ASTRA_MONITOR_INTERVAL_SECONDS", 30))
API_HOST = os.environ.get("ASTRA_API_HOST", "127.0.0.1")
if API_HOST == "0.0.0.0":
    API_HOST = "127.0.0.1"
API_PORT = int(os.environ.get("ASTRA_API_PORT", 8000))
DB_PATH = os.environ.get("ASTRA_DB_PATH", "memory_db/astra_autonomous.db")

# Thresholds for scheduler runs (in seconds)
SCHEDULER_THRESHOLDS = {
    "H1": 2 * 3600,       # 2 hours
    "H4": 8 * 3600,       # 8 hours
    "D1": 48 * 3600,      # 48 hours
}

# Configure logging
LOG_DIR = Path("/var/log/astra")
LOG_DIR.mkdir(parents=True, exist_ok=True)

formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [supervisor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("astra_supervisor")
logger.setLevel(logging.INFO)

# Console Handler
c_handler = logging.StreamHandler(sys.stdout)
c_handler.setFormatter(formatter)
logger.addHandler(c_handler)

_running = True


def handle_shutdown(signum, frame):
    global _running
    logger.info(f"Received signal {signum}. Shutting down supervisor gracefully...")
    _running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def check_api_health() -> bool:
    """Verifies that the FastAPI workspace server is responding on health or status endpoints."""
    urls = [
        f"http://{API_HOST}:{API_PORT}/health",
        f"http://{API_HOST}:{API_PORT}/api/status",
    ]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ASTRA-Supervisor/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    logger.debug(f"[health] API responded OK at {url}")
                    return True
        except Exception:
            continue

    # Socket fallback check
    import socket
    try:
        with socket.create_connection((API_HOST, API_PORT), timeout=3):
            logger.debug(f"[health] API socket check connected at {API_HOST}:{API_PORT}")
            return True
    except Exception as e:
        logger.warning(f"[health] API port check failed on {API_HOST}:{API_PORT}: {e}")
        return False


def check_database_health() -> bool:
    """Verifies SQLite database is accessible and not corrupt or locked."""
    abs_db = Path(DB_PATH)
    if not abs_db.is_absolute():
        abs_db = PROJECT_ROOT / abs_db

    if not abs_db.exists():
        logger.warning(f"[database] DB file does not exist at {abs_db}. Will be initialized on first write.")
        return True

    try:
        conn = sqlite3.connect(str(abs_db), timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        res = cursor.fetchone()
        conn.close()

        if res and res[0].lower() == "ok":
            logger.debug("[database] SQLite PRAGMA quick_check PASSED.")
            return True
        else:
            logger.critical(f"[database] SQLite quick_check failed: {res}")
            return False
    except sqlite3.OperationalError as oe:
        logger.critical(f"[database] SQLite operational error (DB locked or inaccessible): {oe}")
        return False
    except sqlite3.DatabaseError as de:
        logger.critical(f"[database] SQLite database corrupt: {de}")
        return False
    except Exception as e:
        logger.critical(f"[database] Unexpected error accessing SQLite DB: {e}")
        return False


def get_last_scheduler_run_time(timeframe: str) -> datetime | None:
    """Gets the timestamp of the last successful run for a timeframe."""
    # 1. Check SQLite DB
    abs_db = Path(DB_PATH)
    if not abs_db.is_absolute():
        abs_db = PROJECT_ROOT / abs_db

    if abs_db.exists():
        try:
            conn = sqlite3.connect(str(abs_db), timeout=3.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp FROM scheduler_runs 
                WHERE timeframe=? AND status='SUCCESS' 
                ORDER BY id DESC LIMIT 1
            """, (timeframe,))
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                return datetime.fromisoformat(row[0])
        except Exception:
            pass

    # 2. Check marker file /var/log/astra/scheduler_<tf>.last
    marker = LOG_DIR / f"scheduler_{timeframe}.last"
    if marker.exists():
        try:
            ts_str = marker.read_text().strip()
            return datetime.fromisoformat(ts_str)
        except Exception:
            pass

    # 3. Fallback: check log file mtime /var/log/astra/scheduler-<tf>.log
    log_file = LOG_DIR / f"scheduler-{timeframe}.log"
    if log_file.exists():
        try:
            mtime = log_file.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except Exception:
            pass

    return None


def check_scheduler_freshness():
    """Checks whether H1, H4, and D1 schedulers have executed within expected thresholds."""
    now = datetime.now()

    for tf, threshold in SCHEDULER_THRESHOLDS.items():
        last_run = get_last_scheduler_run_time(tf)
        if last_run is None:
            logger.info(f"[scheduler] {tf} scheduler has no recorded runs yet.")
            continue

        elapsed = (now - last_run).total_seconds()
        if elapsed > threshold:
            hours_ago = elapsed / 3600.0
            thresh_hours = threshold / 3600.0
            logger.warning(
                f"[scheduler] {tf} scheduler delay detected! Last run was {hours_ago:.1f}h ago "
                f"(expected within {thresh_hours:.1f}h)."
            )
        else:
            logger.debug(f"[scheduler] {tf} scheduler fresh (last run {elapsed/60.0:.1f}m ago).")


def run_supervisor():
    logger.info("Starting ASTRA Supervisor Process Monitor...")
    logger.info(f"Target API: http://{API_HOST}:{API_PORT} | Interval: {INTERVAL_SECONDS}s | DB: {DB_PATH}")

    while _running:
        try:
            # 1. API Health Check
            api_ok = check_api_health()
            if not api_ok:
                logger.error(
                    "[alert] astra-api appears DOWN or unresponsive; "
                    "systemd restart policy remains authoritative."
                )

            # 2. Database Health Check
            db_ok = check_database_health()
            if not db_ok:
                logger.critical(
                    "[alert] SQLite database issue detected; no automatic "
                    "database or service mutation was attempted."
                )

            # 3. Scheduler Freshness Check
            check_scheduler_freshness()

        except Exception as e:
            logger.error(f"[supervisor] Unhandled exception in main monitor loop: {e}", exc_info=True)

        # Sleep in small increments for fast shutdown response
        for _ in range(INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("ASTRA Supervisor Process Monitor stopped.")


if __name__ == "__main__":
    run_supervisor()
