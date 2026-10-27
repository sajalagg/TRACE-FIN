from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt_hex: Optional[str] = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a per-user salt.

    Never stores plaintext passwords. Pass a deterministic `salt_hex` only in
    reproducible database seeding scripts; leave `None` in normal registration
    to generate a cryptographically strong 16-byte random salt.
    """
    if not password:
        raise ValueError("Password must not be empty.")
    actual_salt = salt_hex if salt_hex is not None else secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        actual_salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${actual_salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a candidate password against a stored PBKDF2-HMAC-SHA256 hash in constant time."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 4 or not parts[0].startswith("pbkdf2_"):
        return False
    algo = parts[0].replace("pbkdf2_", "", 1)
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt_hex = parts[2]
    expected_hex = parts[3]

    candidate_derived = hashlib.pbkdf2_hmac(
        algo,
        password.encode("utf-8"),
        salt_hex.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(candidate_derived, expected_hex)


def generate_session_token() -> tuple[str, str]:
    """Generate a URL-safe random session token and its SHA-256 storage digest.

    Returns `(raw_token_for_client, sha256_token_hash_for_db)`.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def hash_session_token(raw_token: str) -> str:
    """Compute the SHA-256 hex digest of a raw bearer token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
