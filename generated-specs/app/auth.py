"""Bearer tokens (HS256, JWT_SECRET). The tenant comes only from the "tenant_id" claim of a validated
token, never from a header such as X-Tenant-Id, and there is no default tenant."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

TENANT_CLAIM = "tenant_id"


def _b64decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def verify_jwt(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Claims of a valid HS256 token (signature, exp and nbf checked), else None."""
    parts = token.split(".")
    if len(parts) != 3 or not secret:
        return None
    try:
        if json.loads(_b64decode(parts[0])).get("alg") != "HS256":
            return None
        expected = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(parts[2])):
            return None
        claims = json.loads(_b64decode(parts[1]))
    except (ValueError, TypeError, AttributeError):
        return None
    now = time.time()
    if isinstance(claims.get("exp"), (int, float)) and now >= claims["exp"]:
        return None
    if isinstance(claims.get("nbf"), (int, float)) and now < claims["nbf"]:
        return None
    return claims if isinstance(claims, dict) else None


def sign_jwt(claims: Dict[str, Any], secret: str) -> str:
    """Signs an HS256 token (tests and local tooling; production tokens come from your identity provider)."""
    head = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64encode(json.dumps(claims).encode())
    sig = _b64encode(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def tenant_from_authorization(authorization: Optional[str], secret: Optional[str] = None) -> Optional[str]:
    """Tenant of a request: the TENANT_CLAIM of its validated bearer token, else None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    claims = verify_jwt(authorization[7:].strip(), os.environ.get("JWT_SECRET", "") if secret is None else secret)
    tenant = claims.get(TENANT_CLAIM) if claims else None
    return tenant if isinstance(tenant, str) and tenant.strip() else None
