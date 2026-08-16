"""Security primitives: password hashing and opaque token handling.

No web-framework imports — usable from services and tests alike.
"""

from relay.core.security.passwords import hash_password, needs_rehash, verify_password
from relay.core.security.tokens import generate_token, hash_token, normalize_email

__all__ = [
    "generate_token",
    "hash_password",
    "hash_token",
    "needs_rehash",
    "normalize_email",
    "verify_password",
]
