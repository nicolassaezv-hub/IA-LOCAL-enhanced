"""Strict session evidence for IFCMarkets-Demo EURUSD on native MT5 time."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import pandas as pd

from forex.data.mt5_clock_profiles import IFC_MARKETS_DEMO_CLOCK_PROFILE
from forex.data.session_authority import (
    SessionAuthorityDescriptor,
    SessionState,
)


IFC_SESSION_TIMEZONE = "Europe/Berlin"
IFC_QUOTE_SESSION_EFFECTIVE_FROM = pd.Timestamp(
    "2026-03-29 00:00:00", tz=IFC_SESSION_TIMEZONE
)
IFC_QUOTE_SESSION_EFFECTIVE_TO = pd.Timestamp(
    "2026-10-25 00:00:00", tz=IFC_SESSION_TIMEZONE
)
IFC_UNAUTHORIZED_HOLIDAY_DATES = frozenset({
    "2020-12-25",
    "2021-01-01",
})


@dataclass(frozen=True)
class IFCClosureEvidence:
    """One reviewed IFC closure interval and its immutable source identity."""

    evidence_id: str
    source_identity: str
    publication_or_capture: str
    start_local: str
    end_local: str
    version: str = "1"

    @property
    def evidence_hash(self) -> str:
        record = "\n".join((
            f"evidence_id={self.evidence_id}",
            f"source_identity={self.source_identity}",
            f"publication_or_capture={self.publication_or_capture}",
            f"timezone={IFC_SESSION_TIMEZONE}",
            f"start_local={self.start_local}",
            f"end_local={self.end_local}",
            f"version={self.version}",
        ))
        return sha256(record.encode("utf-8")).hexdigest()

    def contains(self, local_timestamp: pd.Timestamp) -> bool:
        start = pd.Timestamp(self.start_local, tz=IFC_SESSION_TIMEZONE)
        end = pd.Timestamp(self.end_local, tz=IFC_SESSION_TIMEZONE)
        return start <= local_timestamp < end

    def provenance(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "source_identity": self.source_identity,
            "publication_or_capture": self.publication_or_capture,
            "timezone": IFC_SESSION_TIMEZONE,
            "start_local": self.start_local,
            "end_local": self.end_local,
            "version": self.version,
            "evidence_hash": self.evidence_hash,
        }


IFC_CLOSURE_EVIDENCE = (
    IFCClosureEvidence(
        "ifc-2018-christmas",
        "IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2018_2019",
        "published=2018-12-13;web_archive_capture=2019-01-27",
        "2018-12-25 00:00:00",
        "2018-12-26 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2018-2019-new-year",
        "IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2018_2019",
        "published=2018-12-13;web_archive_capture=2019-01-27",
        "2018-12-31 00:00:00",
        "2019-01-02 07:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2019-christmas",
        "IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2019_2020",
        "published=2019-12-18;web_archive_capture=2020-01-08",
        "2019-12-25 00:00:00",
        "2019-12-26 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2019-2020-new-year",
        "IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2019_2020",
        "published=2019-12-18;web_archive_capture=2020-01-08",
        "2019-12-31 00:00:00",
        "2020-01-02 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2023-christmas",
        "IFC_CHRISTMAS_NEW_YEAR_2023_2024",
        "published=2023-12-12",
        "2023-12-22 22:00:00",
        "2023-12-26 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2023-2024-new-year",
        "IFC_CHRISTMAS_NEW_YEAR_2023_2024",
        "published=2023-12-12",
        "2023-12-30 00:00:00",
        "2024-01-02 09:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2024-christmas",
        "IFC_CHRISTMAS_NEW_YEAR_2024_2025",
        "published=2024-12-12",
        "2024-12-24 22:00:00",
        "2024-12-26 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2024-2025-new-year",
        "IFC_CHRISTMAS_NEW_YEAR_2024_2025",
        "published=2024-12-12",
        "2024-12-31 07:00:00",
        "2025-01-02 09:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2025-christmas",
        "IFC_CHRISTMAS_TRADING_SCHEDULE_2025",
        "published=2025-12-15",
        "2025-12-24 19:00:00",
        "2025-12-26 00:00:00",
    ),
    IFCClosureEvidence(
        "ifc-2025-2026-new-year",
        "IFC_NEW_YEAR_TRADING_SCHEDULE_2025_2026",
        "published=2025-12-22",
        "2025-12-31 07:00:00",
        "2026-01-02 09:00:00",
    ),
)

_QUOTE_SESSION_EVIDENCE = "\n".join((
    "server=IFCMarkets-Demo",
    "symbol=EURUSD",
    "source=SymbolInfoSessionQuote",
    "observed=2026-08-30",
    "monday_thursday=00:00-00:00",
    "friday=00:00-22:00",
    "saturday_sunday=NO_SESSION",
    f"clock_profile_hash={IFC_MARKETS_DEMO_CLOCK_PROFILE.evidence_hash}",
))
_BUNDLE_HASH = sha256(
    ("\n".join((
        _QUOTE_SESSION_EVIDENCE,
        *(item.evidence_hash for item in IFC_CLOSURE_EVIDENCE),
    ))).encode("utf-8")
).hexdigest()


class IFCForexSessionAuthority:
    """Quote-session and reviewed-holiday authority for one exact MT5 feed."""

    descriptor = SessionAuthorityDescriptor(
        authority_id="ifcmarkets-demo-eurusd-session-v1",
        authority_type="BROKER_QUOTE_SESSION_AND_REVIEWED_HOLIDAYS",
        source_identity="IFC_EURUSD_SESSION_EVIDENCE_BUNDLE_2026_08_30",
        asset_class="FOREX",
        timezone=IFC_SESSION_TIMEZONE,
        effective_from="2018-01-01T00:00:00+00:00",
        effective_to="2026-12-31T23:59:59+00:00",
        version="1",
        evidence_hash=_BUNDLE_HASH,
        provider="MT5",
        symbol="EURUSD",
        clock_profile_id=IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id,
        server_identity=IFC_MARKETS_DEMO_CLOCK_PROFILE.server_identity,
    )

    def _local(self, timestamp: Any) -> pd.Timestamp:
        moment = pd.Timestamp(timestamp)
        if pd.isna(moment) or moment.tzinfo is None:
            raise ValueError("IFC session timestamps must be timezone-aware")
        return moment.tz_convert(IFC_SESSION_TIMEZONE)

    def holiday_evidence(self, timestamp: Any) -> IFCClosureEvidence | None:
        local = self._local(timestamp)
        if local.date().isoformat() in IFC_UNAUTHORIZED_HOLIDAY_DATES:
            return None
        return next(
            (item for item in IFC_CLOSURE_EVIDENCE if item.contains(local)),
            None,
        )

    def classify_timestamp(self, timestamp: Any) -> SessionState:
        local = self._local(timestamp)
        if local.date().isoformat() in IFC_UNAUTHORIZED_HOLIDAY_DATES:
            return SessionState.UNKNOWN
        if self.holiday_evidence(local) is not None:
            return SessionState.CLOSED
        if not (
            IFC_QUOTE_SESSION_EFFECTIVE_FROM
            <= local
            < IFC_QUOTE_SESSION_EFFECTIVE_TO
        ):
            return SessionState.UNKNOWN
        weekday = local.dayofweek
        if weekday <= 3:
            return SessionState.OPEN
        if weekday == 4:
            close = local.normalize() + pd.Timedelta(hours=22)
            return SessionState.OPEN if local < close else SessionState.CLOSED
        return SessionState.CLOSED

    def evidence_for_timestamp(self, timestamp: Any) -> dict[str, str] | None:
        evidence = self.holiday_evidence(timestamp)
        if evidence is not None:
            return evidence.provenance()
        local = self._local(timestamp)
        if (
            IFC_QUOTE_SESSION_EFFECTIVE_FROM
            <= local
            < IFC_QUOTE_SESSION_EFFECTIVE_TO
            and local.dayofweek == 4
            and local.hour >= 22
        ):
            return {
                "evidence_id": "ifc-eurusd-quote-session-2026-08-30",
                "source_identity": "MT5_SYMBOL_INFO_SESSION_QUOTE_EURUSD",
                "timezone": IFC_SESSION_TIMEZONE,
                "version": "1",
                "evidence_hash": sha256(
                    _QUOTE_SESSION_EVIDENCE.encode("utf-8")
                ).hexdigest(),
            }
        return None


IFC_FOREX_SESSION_AUTHORITY = IFCForexSessionAuthority()


__all__ = [
    "IFC_CLOSURE_EVIDENCE",
    "IFC_FOREX_SESSION_AUTHORITY",
    "IFC_QUOTE_SESSION_EFFECTIVE_FROM",
    "IFC_QUOTE_SESSION_EFFECTIVE_TO",
    "IFC_SESSION_TIMEZONE",
    "IFC_UNAUTHORIZED_HOLIDAY_DATES",
    "IFCClosureEvidence",
    "IFCForexSessionAuthority",
]
