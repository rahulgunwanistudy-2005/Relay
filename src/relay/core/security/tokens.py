"""Opaque token generation and hashing.

Callers keep the raw token (returned to the client once) and persist only its
SHA-256 hash. Lookups hash the presented token and compare.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def generate_token() -> str:
    """A URL-safe random token with ~256 bits of entropy."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()
