"""UTC-safe classification for durable scheduler run state."""
from __future__ import annotations

import os
from datetime import datetime, timezone


SCHEDULER_RUN_STALE_SECONDS = 60 * 60
SCHEDULER_RUN_STALE_ENV = "ASTRA_SCHEDULER_STALE_SECONDS"


def scheduler_run_stale_seconds() -> float:
    """Return the positive operational timeout configured for RUNNING cycles."""
    raw = os.getenv(SCHEDULER_RUN_STALE_ENV, str(SCHEDULER_RUN_STALE_SECONDS))
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{SCHEDULER_RUN_STALE_ENV} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{SCHEDULER_RUN_STALE_ENV} must be a positive number")
    return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp(moment: datetime | None = None) -> str:
    value = moment or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_utc_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_scheduler_run_stale(
    run: dict,
    *,
    now: datetime | None = None,
    stale_after_seconds: float | None = None,
) -> bool:
    """Return whether a RUNNING record has exceeded its safe active window."""
    if str(run.get("status", "")).lower() != "running":
        return False
    started_at = parse_utc_timestamp(run.get("started_at"))
    if started_at is None:
        return True
    reference = now or utc_now()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    timeout = (
        scheduler_run_stale_seconds()
        if stale_after_seconds is None
        else float(stale_after_seconds)
    )
    if timeout <= 0:
        raise ValueError("stale_after_seconds must be positive")
    return (reference.astimezone(timezone.utc) - started_at).total_seconds() >= timeout
