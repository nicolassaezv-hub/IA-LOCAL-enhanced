"""Shared HTTP runtime security primitives for ASTRA's local APIs."""

from __future__ import annotations

import hmac
import os
from enum import Enum
from typing import Mapping

API_KEY_ENV = "ASTRA_API_KEY"
DEFAULT_BIND_HOST = "127.0.0.1"


class AuthResult(str, Enum):
    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    MISSING = "missing"
    INVALID = "invalid"


def configured_bind_host(env_name: str, environ: Mapping[str, str] | None = None) -> str:
    """Use loopback unless a bind address is explicitly configured."""
    source = os.environ if environ is None else environ
    value = source.get(env_name, "").strip()
    return value or DEFAULT_BIND_HOST


def authenticate_headers(
    headers: Mapping[str, str],
    environ: Mapping[str, str] | None = None,
) -> AuthResult:
    """Validate Bearer or X-API-Key credentials without ever returning the secret."""
    source = os.environ if environ is None else environ
    expected = source.get(API_KEY_ENV, "")
    if not expected:
        return AuthResult.NOT_CONFIGURED

    authorization = headers.get("authorization", "") or headers.get("Authorization", "")
    supplied = ""
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied:
        supplied = headers.get("x-api-key", "") or headers.get("X-API-Key", "")
    if not supplied:
        return AuthResult.MISSING
    return AuthResult.OK if hmac.compare_digest(supplied, expected) else AuthResult.INVALID


def configured_cors_origins(environ: Mapping[str, str] | None = None) -> frozenset[str]:
    """Return explicit origins only; wildcard CORS is intentionally unsupported."""
    source = os.environ if environ is None else environ
    origins = {
        origin.strip().rstrip("/")
        for origin in source.get("ASTRA_CORS_ORIGINS", "").split(",")
        if origin.strip() and origin.strip() != "*"
    }
    return frozenset(origins)
