"""Fail-closed interface for future authoritative market-session evidence."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

import pandas as pd


class SessionState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SessionAuthorityDescriptor:
    """Identity and validity bounds for an externally reviewed authority."""

    authority_id: str
    authority_type: str
    source_identity: str
    asset_class: str
    timezone: str
    effective_from: str
    effective_to: str | None
    version: str
    evidence_hash: str
    provider: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "authority_id",
            "authority_type",
            "source_identity",
            "asset_class",
            "timezone",
            "effective_from",
            "version",
            "evidence_hash",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Session authority {field} is invalid")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("Session authority provider is invalid")
        ZoneInfo(self.timezone)
        start = _aware_utc(self.effective_from)
        if self.effective_to is not None:
            end = _aware_utc(self.effective_to)
            if end < start:
                raise ValueError("Session authority effective range is invalid")
        digest = self.evidence_hash.lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Session authority evidence_hash is invalid")

    def applies_to(
        self,
        timestamp: Any,
        *,
        asset_class: str,
        provider: str | None,
    ) -> bool:
        moment = _aware_utc(timestamp)
        if self.asset_class.upper() != asset_class.upper():
            return False
        if self.provider is not None and (
            provider is None or self.provider.casefold() != provider.casefold()
        ):
            return False
        if moment < _aware_utc(self.effective_from):
            return False
        return self.effective_to is None or moment <= _aware_utc(self.effective_to)


def _aware_utc(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("Session authority timestamps must be timezone-aware")
    return timestamp.tz_convert("UTC")


@runtime_checkable
class SessionAuthority(Protocol):
    @property
    def descriptor(self) -> SessionAuthorityDescriptor | None: ...

    def classify_timestamp(self, timestamp: Any) -> SessionState: ...


class UnknownSessionAuthority:
    """Default authority: it never supplies evidence that can unblock a gap."""

    descriptor = None

    def classify_timestamp(self, timestamp: Any) -> SessionState:
        return SessionState.UNKNOWN


def classify_authorized_timestamp(
    authority: SessionAuthority | None,
    timestamp: Any,
    *,
    asset_class: str,
    provider: str | None = None,
) -> SessionState:
    """Return UNKNOWN for absent, malformed, inapplicable, or failing evidence."""
    if authority is None:
        return SessionState.UNKNOWN
    try:
        descriptor = authority.descriptor
        if not isinstance(descriptor, SessionAuthorityDescriptor):
            return SessionState.UNKNOWN
        if not descriptor.applies_to(
            timestamp, asset_class=asset_class, provider=provider
        ):
            return SessionState.UNKNOWN
        return SessionState(authority.classify_timestamp(timestamp))
    except Exception:
        return SessionState.UNKNOWN


__all__ = [
    "SessionAuthority",
    "SessionAuthorityDescriptor",
    "SessionState",
    "UnknownSessionAuthority",
    "classify_authorized_timestamp",
]
