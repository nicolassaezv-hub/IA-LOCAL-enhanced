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

import argparse
import json
import re
import sys
import os
import time
import signal
import socket
import sqlite3
import urllib.request
import urllib.error
import logging
from datetime import datetime, timedelta, timezone
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
STARTUP_GRACE_SECONDS = max(
    30,
    min(60, int(os.environ.get("ASTRA_MONITOR_STARTUP_GRACE_SECONDS", 45))),
)
DELEGATED_DB_HEALTH_ENDPOINT = "/api/health/database"
_DB_HEALTH_STATES = frozenset({
    "DB_HEALTH_PASS",
    "DB_HEALTH_FAILED",
    "DB_HEALTH_UNAVAILABLE",
})
_SAFE_CLASSIFICATION = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

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
_scheduler_disabled_logged = False


def handle_shutdown(signum, frame):
    global _running
    logger.info(f"Received signal {signum}. Shutting down supervisor gracefully...")
    _running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def _api_failure_classification(exc: Exception) -> str:
    """Return a safe classification without serializing request evidence."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP_STATUS_{exc.code}"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "TIMEOUT"
        if isinstance(reason, ConnectionRefusedError):
            return "CONNECTION_REFUSED"
        return "URL_NETWORK_ERROR"
    if isinstance(exc, ConnectionRefusedError):
        return "CONNECTION_REFUSED"
    return f"OTHER_{type(exc).__name__}"


def check_api_health(*, startup_grace: bool = False) -> bool:
    """Verify API health while retaining safe endpoint diagnostics."""
    endpoints = ("/health", "/api/status")
    failures = []

    for endpoint in endpoints:
        url = f"http://{API_HOST}:{API_PORT}{endpoint}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ASTRA-Supervisor/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    logger.debug(f"[health] API responded OK at {url}")
                    return True
                classification = f"HTTP_STATUS_{response.status}"
        except Exception as exc:
            classification = _api_failure_classification(exc)
        failures.append(f"{endpoint}={classification}")
        logger.debug(
            "[health] HTTP_HEALTH_ENDPOINT_FAILED endpoint=%s class=%s",
            endpoint,
            classification,
        )

    # Socket fallback check
    try:
        with socket.create_connection((API_HOST, API_PORT), timeout=3):
            logger.warning(
                "[health] HTTP_HEALTH_FAILED_SOCKET_REACHABLE host=%s port=%s "
                "failures=%s",
                API_HOST,
                API_PORT,
                ",".join(failures),
            )
            return True
    except Exception as exc:
        log = logger.info if startup_grace else logger.warning
        classification = _api_failure_classification(exc)
        log(
            "[health] %s host=%s port=%s failures=%s socket=%s",
            (
                "API_STARTUP_GRACE"
                if startup_grace
                else "API_HEALTH_FAILED"
            ),
            API_HOST,
            API_PORT,
            ",".join(failures),
            classification,
        )
        return False


def check_delegated_database_health() -> dict[str, str]:
    """Consume the API-owned DB probe without exposing response evidence."""
    url = (
        f"http://{API_HOST}:{API_PORT}"
        f"{DELEGATED_DB_HEALTH_ENDPOINT}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "ASTRA-Supervisor/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read(4097)
    except urllib.error.HTTPError as exc:
        body = exc.read(4097)
    except Exception:
        return {
            "state": "DB_HEALTH_UNAVAILABLE",
            "classification": "API_UNREACHABLE",
        }

    if len(body) > 4096:
        return {
            "state": "DB_HEALTH_UNAVAILABLE",
            "classification": "INVALID_HEALTH_RESPONSE",
        }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "state": "DB_HEALTH_UNAVAILABLE",
            "classification": "INVALID_HEALTH_RESPONSE",
        }
    state = payload.get("state") if isinstance(payload, dict) else None
    classification = (
        payload.get("classification") if isinstance(payload, dict) else None
    )
    if (
        state not in _DB_HEALTH_STATES
        or not isinstance(classification, str)
        or _SAFE_CLASSIFICATION.fullmatch(classification) is None
    ):
        return {
            "state": "DB_HEALTH_UNAVAILABLE",
            "classification": "INVALID_HEALTH_RESPONSE",
        }
    return {"state": state, "classification": classification}


def _resolved_database_path() -> Path:
    path = Path(DB_PATH)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _connect_database_read_only(path: Path, *, timeout: float):
    return sqlite3.connect(path.as_uri() + "?mode=ro", timeout=timeout, uri=True)


def check_database_health() -> bool:
    """Verify live SQLite integrity without requesting write access."""
    abs_db = _resolved_database_path()
    parent = abs_db.parent

    if not parent.is_dir() or not os.access(parent, os.R_OK | os.X_OK):
        logger.critical(
            "[database] DB_PARENT_INACCESSIBLE path=%s parent=%s",
            abs_db,
            parent,
        )
        return False

    if not abs_db.is_file():
        logger.warning(
            "[database] DB_FILE_MISSING path=%s; initialization remains the "
            "responsibility of the first writer",
            abs_db,
        )
        return True

    connection = None
    phase = "connect"
    try:
        connection = _connect_database_read_only(abs_db, timeout=5.0)
        cursor = connection.cursor()
        phase = "query_only"
        cursor.execute("PRAGMA query_only = ON;")
        cursor.execute("PRAGMA query_only;")
        query_only = cursor.fetchone()
        if not query_only or int(query_only[0]) != 1:
            logger.critical(
                "[database] SQLITE_QUERY_ONLY_FAILED path=%s result=%r",
                abs_db,
                query_only,
            )
            return False
        phase = "quick_check"
        cursor.execute("PRAGMA quick_check;")
        results = cursor.fetchall()

        if len(results) == 1 and str(results[0][0]).lower() == "ok":
            logger.debug("[database] SQLite read-only PRAGMA quick_check PASSED path=%s", abs_db)
            return True
        logger.critical(
            "[database] SQLITE_QUICK_CHECK_FAILED path=%s result_count=%s",
            abs_db,
            len(results),
        )
        return False
    except sqlite3.OperationalError as exc:
        classification = (
            "SQLITE_READ_ONLY_CONNECT_FAILED "
            if phase == "connect"
            else ""
        )
        logger.critical(
            "[database] %sSQLITE_OPERATIONAL_LOCK_OR_ACCESS_ERROR "
            "path=%s phase=%s detail=%s",
            classification,
            abs_db,
            phase,
            exc,
        )
        return False
    except sqlite3.DatabaseError as exc:
        logger.critical(
            "[database] SQLITE_DATABASE_CORRUPTION path=%s phase=%s detail=%s",
            abs_db,
            phase,
            exc,
        )
        return False
    except Exception as exc:
        classification = (
            "SQLITE_READ_ONLY_CONNECT_FAILED"
            if phase == "connect"
            else "SQLITE_HEALTHCHECK_EXCEPTION"
        )
        logger.critical(
            "[database] %s path=%s phase=%s exception_type=%s",
            classification,
            abs_db,
            phase,
            type(exc).__name__,
        )
        return False
    finally:
        if connection is not None:
            connection.close()


def get_last_scheduler_run_time(timeframe: str) -> datetime | None:
    """Gets the timestamp of the last successful run for a timeframe."""
    # 1. Check SQLite DB
    abs_db = _resolved_database_path()

    if abs_db.is_file():
        connection = None
        try:
            connection = _connect_database_read_only(abs_db, timeout=3.0)
            cursor = connection.cursor()
            cursor.execute("PRAGMA query_only = ON;")
            cursor.execute("""
                SELECT timestamp FROM scheduler_runs 
                WHERE timeframe=? AND status='SUCCESS' 
                ORDER BY id DESC LIMIT 1
            """, (timeframe,))
            row = cursor.fetchone()

            if row and row[0]:
                return datetime.fromisoformat(row[0])
        except Exception:
            pass
        finally:
            if connection is not None:
                connection.close()

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
    global _scheduler_disabled_logged
    scheduler_enabled = os.environ.get(
        "ASTRA_SCHEDULER_ENABLED", "true"
    ).strip().lower() not in {"0", "false", "no", "off"}
    if not scheduler_enabled:
        if not _scheduler_disabled_logged:
            logger.info("[scheduler] SCHEDULER_MONITORING_DISABLED")
            _scheduler_disabled_logged = True
        return
    _scheduler_disabled_logged = False
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


def run_monitor_cycle(*, startup_grace: bool) -> dict[str, str]:
    """Run one daemon cycle using only delegated database evidence."""
    api_ok = check_api_health(startup_grace=startup_grace)
    if not api_ok:
        if startup_grace:
            logger.info(
                "[startup] API_STARTUP_GRACE API_UNREACHABLE; "
                "database health unavailable until API startup completes"
            )
        else:
            logger.error(
                "[alert] API_UNREACHABLE; astra-api appears DOWN or "
                "unresponsive; systemd restart policy remains authoritative."
            )
        result = {
            "api": "API_UNREACHABLE",
            "database": "DB_HEALTH_UNAVAILABLE",
        }
    else:
        database_health = check_delegated_database_health()
        state = database_health["state"]
        classification = database_health["classification"]
        result = {"api": "API_HEALTH_PASS", "database": state}
        if state == "DB_HEALTH_PASS":
            logger.debug(
                "[database] DB_HEALTH_PASS classification=%s",
                classification,
            )
        elif state == "DB_HEALTH_FAILED":
            logger.critical(
                "[alert] DB_HEALTH_FAILED classification=%s; no automatic "
                "database or service mutation was attempted.",
                classification,
            )
        else:
            logger.warning(
                "[database] DB_HEALTH_UNAVAILABLE classification=%s; "
                "database health was not declared healthy.",
                classification,
            )

    check_scheduler_freshness()
    return result


def run_supervisor():
    logger.info("Starting ASTRA Supervisor Process Monitor...")
    logger.info(f"Target API: http://{API_HOST}:{API_PORT} | Interval: {INTERVAL_SECONDS}s | DB: {DB_PATH}")
    started_at = time.monotonic()

    while _running:
        try:
            run_monitor_cycle(
                startup_grace=(
                    time.monotonic() - started_at < STARTUP_GRACE_SECONDS
                )
            )

        except Exception as e:
            logger.error(f"[supervisor] Unhandled exception in main monitor loop: {e}", exc_info=True)

        # Sleep in small increments for fast shutdown response
        for _ in range(INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("ASTRA Supervisor Process Monitor stopped.")


def run_check_once() -> int:
    """Run one observational cycle; scheduler freshness is advisory only."""
    api_ok = check_api_health()
    db_ok = check_database_health()
    try:
        check_scheduler_freshness()
    except Exception as exc:
        logger.warning(
            "[check-once] SCHEDULER_FRESHNESS_CHECK_FAILED exception_type=%s",
            type(exc).__name__,
        )
    exit_code = 0 if api_ok and db_ok else 1
    logger.info(
        "[check-once] API=%s DB=%s scheduler=advisory exit=%s",
        "PASS" if api_ok else "FAIL",
        "PASS" if db_ok else "FAIL",
        exit_code,
    )
    return exit_code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ASTRA diagnostic health monitor")
    parser.add_argument(
        "--check-once",
        action="store_true",
        help="run one API/DB/scheduler diagnostic cycle and exit",
    )
    args = parser.parse_args(argv)
    if args.check_once:
        return run_check_once()
    run_supervisor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
