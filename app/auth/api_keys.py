"""GHARTS-native API key generation and verification.

API keys have the format ``gharts_<url-safe-base64-encoded-random-bytes>``.
The prefix makes them unambiguously distinguishable from JWTs in the
``Authorization: Bearer`` header.

Only the bcrypt hash is stored in the database.  The raw key is shown to
the administrator exactly once (at issuance or rotation) and must be treated
as a secret credential — like a GitHub PAT.

Hash algorithm choice: bcrypt with work factor 12.
- Resistant to GPU-accelerated brute-force (unlike plain SHA-256).
- 32 bytes of entropy (256 bits) in the raw key makes brute-force
  infeasible regardless of hash algorithm.
- The ``bcrypt`` package (already a transitive dependency via ``passlib``)
  is used directly rather than through passlib to avoid the passlib 1.7.4 /
  bcrypt 4+ incompatibility (passlib's backend detection runs a 73-byte
  self-test that bcrypt 4+ rejects).
- Our keys are 50 bytes (7-char prefix + 43-char base64), well within
  bcrypt's 72-byte limit.
"""

import base64
import secrets
from typing import Tuple

import bcrypt as _bcrypt

_PREFIX = "gharts_"
_KEY_BYTES = 32  # 256 bits of entropy


def generate_api_key() -> Tuple[str, str]:
    """Generate a new GHARTS API key and return ``(raw_key, hashed_key)``.

    The raw key must be shown to the caller exactly once and never stored.
    Only the hash should be persisted.

    Returns:
        A tuple of ``(raw_key, hashed_key)`` where *raw_key* is the
        bearer token value and *hashed_key* is the bcrypt digest to store.
    """
    raw_bytes = secrets.token_bytes(_KEY_BYTES)
    # URL-safe base64, no padding characters that could confuse HTTP headers
    raw_key = _PREFIX + base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()
    hashed = _bcrypt.hashpw(raw_key.encode(), _bcrypt.gensalt(rounds=12)).decode()
    return raw_key, hashed


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Return True if *raw_key* matches *hashed_key*.

    Constant-time comparison is performed by the bcrypt library.

    Args:
        raw_key: The bearer token value from the Authorization header.
        hashed_key: The bcrypt hash stored in the database.

    Returns:
        True if the key is valid, False otherwise.
    """
    if not raw_key or not hashed_key:
        return False
    try:
        return _bcrypt.checkpw(raw_key.encode(), hashed_key.encode())
    except Exception:
        return False


def is_api_key(token: str) -> bool:
    """Return True if *token* looks like a GHARTS API key (has the prefix).

    This check is used to route the bearer token to the API-key path
    instead of the JWT-validation path.  It does not validate the key itself.

    Args:
        token: The raw value from ``Authorization: Bearer <token>``.

    Returns:
        True if the token starts with the ``gharts_`` prefix.
    """
    return token.startswith(_PREFIX)
