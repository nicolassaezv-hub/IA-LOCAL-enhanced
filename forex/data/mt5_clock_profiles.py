"""Authoritative, provenance-bound MT5 server clock profiles."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class MT5ServerClockProfile:
    """Clock authority required to interpret one MT5 server's bar times."""

    profile_id: str
    version: int
    server_identity: str
    timezone: str
    authority_type: str
    source_identity: str
    effective_from: str | None
    effective_to: str | None
    evidence_hash: str


_IFC_EVIDENCE_RECORD = "\n".join((
    "server_identity=IFCMarkets-Demo",
    "timezone=Europe/Berlin",
    "authority_type=BROKER_DOCUMENTATION_AND_LIVE_TERMINAL",
    "source_identity=IFC_MARKETS_PLATFORM_CET_CEST_AND_TERMINAL_AUDIT_2026_08_30",
    "terminal_audit_date=2026-08-30",
    "observed_server_offset=+02:00",
))

IFC_MARKETS_DEMO_CLOCK_PROFILE = MT5ServerClockProfile(
    profile_id="ifcmarkets-demo-europe-berlin",
    version=1,
    server_identity="IFCMarkets-Demo",
    timezone="Europe/Berlin",
    authority_type="BROKER_DOCUMENTATION_AND_LIVE_TERMINAL",
    source_identity=(
        "IFC_MARKETS_PLATFORM_CET_CEST_AND_TERMINAL_AUDIT_2026_08_30"
    ),
    effective_from=None,
    effective_to=None,
    evidence_hash=sha256(_IFC_EVIDENCE_RECORD.encode("utf-8")).hexdigest(),
)

_CLOCK_PROFILES = {
    IFC_MARKETS_DEMO_CLOCK_PROFILE.server_identity:
        IFC_MARKETS_DEMO_CLOCK_PROFILE,
}


def resolve_mt5_server_clock_profile(
    server_identity: object,
) -> MT5ServerClockProfile | None:
    """Resolve only an exact, explicitly authorized MT5 server identity."""
    if not isinstance(server_identity, str):
        return None
    return _CLOCK_PROFILES.get(server_identity.strip())


__all__ = [
    "IFC_MARKETS_DEMO_CLOCK_PROFILE",
    "MT5ServerClockProfile",
    "resolve_mt5_server_clock_profile",
]
