"""KMS-backed encryption utilities for sensitive borrower data.

Wraps AWS KMS for envelope encryption. For local development,
falls back to Fernet symmetric encryption.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Encryption Port
# ---------------------------------------------------------------------------
class Encryptor(Protocol):
    """Abstract port for encryption — domain code depends on this."""

    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...


# ---------------------------------------------------------------------------
# Local (Fernet) Encryptor — for dev/test
# ---------------------------------------------------------------------------
class LocalEncryptor:
    """Fernet-based symmetric encryption for local development."""

    def __init__(self, key: bytes | None = None) -> None:
        from cryptography.fernet import Fernet

        self._fernet = Fernet(key or Fernet.generate_key())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# KMS Encryptor — for production
# ---------------------------------------------------------------------------
class KMSEncryptor:
    """Envelope encryption using AWS KMS."""

    def __init__(self, kms_client: Any, key_id: str) -> None:
        self._kms = kms_client
        self._key_id = key_id

    def encrypt(self, plaintext: str) -> str:
        response = self._kms.encrypt(
            KeyId=self._key_id,
            Plaintext=plaintext.encode("utf-8"),
        )
        return base64.b64encode(response["CiphertextBlob"]).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        response = self._kms.decrypt(
            CiphertextBlob=base64.b64decode(ciphertext),
        )
        return response["Plaintext"].decode("utf-8")
