"""Symmetric encryption helpers for sensitive secrets (e.g. user-provided API keys).

Uses Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from
``settings.SECRET_KEY`` via PBKDF2-HMAC-SHA256. The derivation salt is fixed
across the deployment so the same SECRET_KEY yields a stable Fernet key — this
is required so previously-encrypted values remain decryptable after a process
restart. Rotate SECRET_KEY only with a migration plan.

Public API:
    encrypt_secret(plaintext) -> str   # "fernet:<token>"
    decrypt_secret(stored) -> str | None
    mask_secret(plaintext) -> str       # "sk-***xxxx" for safe display
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fixed deployment-wide salt: distinct from per-record salts because Fernet
# tokens already carry their own per-encryption IV. Changing this invalidates
# every stored ciphertext.
_KDF_SALT = b"rag_backend.multimodal.api_key.v1"
_KDF_ITERATIONS = 200_000

_CIPHER_PREFIX = "fernet:"

_fernet_singleton: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet_singleton
    if _fernet_singleton is not None:
        return _fernet_singleton

    secret = (getattr(settings, "SECRET_KEY", "") or "").encode("utf-8")
    if not secret:
        raise RuntimeError(
            "SECRET_KEY is not configured; cannot encrypt/decrypt secrets"
        )

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    _fernet_singleton = Fernet(key)
    return _fernet_singleton


def encrypt_secret(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return a storable string with the cipher prefix."""
    if plaintext is None:
        return ""
    token = _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{_CIPHER_PREFIX}{token}"


def decrypt_secret(stored: Optional[str]) -> Optional[str]:
    """Decrypt a value previously produced by :func:`encrypt_secret`.

    Returns ``None`` if ``stored`` is empty, malformed, or unreadable
    (corrupted, wrong SECRET_KEY, etc.). Callers should treat ``None`` as
    "no usable secret" and fall back accordingly.
    """
    if not stored:
        return None

    # Defensive: tolerate the historic ``f"encrypted_{key}"`` placeholder so a
    # stale row from before G4 does not crash a request. The placeholder cannot
    # be safely recovered; surface it as None and let the caller decide.
    if stored.startswith("encrypted_"):
        logger.warning(
            "Found legacy 'encrypted_' placeholder; treating as missing. "
            "User must re-enter their API key."
        )
        return None

    if not stored.startswith(_CIPHER_PREFIX):
        logger.warning("Stored secret has no recognized cipher prefix; ignoring.")
        return None

    token = stored[len(_CIPHER_PREFIX):].encode("ascii")
    try:
        return _get_fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt stored secret (InvalidToken).")
        return None


def mask_secret(plaintext: Optional[str]) -> str:
    """Return a display-safe masked form: keeps the first 3 and last 4 chars.

    Examples:
        ``sk-abcdefghij1234`` -> ``sk-***1234``
        ``short`` -> ``***``
    """
    if not plaintext:
        return ""
    if len(plaintext) <= 7:
        return "***"
    return f"{plaintext[:3]}***{plaintext[-4:]}"
