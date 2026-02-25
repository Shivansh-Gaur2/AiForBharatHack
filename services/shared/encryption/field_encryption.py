"""Field-level encryption utilities for sensitive borrower data.

Provides decorators and helpers to encrypt/decrypt individual fields
in domain entities before persistence (Req 9.1).

Sensitive fields: aadhaar_number, pan_number, bank_account_number,
phone_number, address details, and any PII fields.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from . import Encryptor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sensitivity classification
# ---------------------------------------------------------------------------
class SensitivityLevel(StrEnum):
    """Data sensitivity classification for encryption decisions."""

    PUBLIC = "PUBLIC"            # No encryption needed
    INTERNAL = "INTERNAL"       # Encrypted at rest only
    CONFIDENTIAL = "CONFIDENTIAL"  # Encrypted at rest + field-level
    RESTRICTED = "RESTRICTED"   # Encrypted everywhere + access-logged


# Mapping of known PII field names to sensitivity levels
PII_FIELD_MAP: dict[str, SensitivityLevel] = {
    "aadhaar_number": SensitivityLevel.RESTRICTED,
    "pan_number": SensitivityLevel.RESTRICTED,
    "bank_account_number": SensitivityLevel.RESTRICTED,
    "ifsc_code": SensitivityLevel.CONFIDENTIAL,
    "phone_number": SensitivityLevel.CONFIDENTIAL,
    "email": SensitivityLevel.CONFIDENTIAL,
    "address": SensitivityLevel.CONFIDENTIAL,
    "village": SensitivityLevel.INTERNAL,
    "district": SensitivityLevel.INTERNAL,
    "state": SensitivityLevel.INTERNAL,
    "date_of_birth": SensitivityLevel.CONFIDENTIAL,
    "full_name": SensitivityLevel.INTERNAL,
    "annual_income": SensitivityLevel.CONFIDENTIAL,
    "monthly_income": SensitivityLevel.CONFIDENTIAL,
}


# ---------------------------------------------------------------------------
# Field-level encryption wrapper
# ---------------------------------------------------------------------------
@dataclass
class EncryptedField:
    """Wrapper for a field that has been encrypted."""

    ciphertext: str
    field_name: str
    sensitivity: SensitivityLevel
    hash_value: str  # SHA-256 hash for equality checks without decrypting

    def to_dict(self) -> dict[str, str]:
        return {
            "ciphertext": self.ciphertext,
            "field_name": self.field_name,
            "sensitivity": self.sensitivity.value,
            "hash_value": self.hash_value,
        }

    @staticmethod
    def from_dict(data: dict[str, str]) -> EncryptedField:
        return EncryptedField(
            ciphertext=data["ciphertext"],
            field_name=data["field_name"],
            sensitivity=SensitivityLevel(data["sensitivity"]),
            hash_value=data["hash_value"],
        )


class FieldEncryptor:
    """Encrypts / decrypts individual fields using the configured Encryptor."""

    def __init__(self, encryptor: Encryptor) -> None:
        self._encryptor = encryptor

    def encrypt_field(
        self,
        field_name: str,
        value: str,
        sensitivity: SensitivityLevel | None = None,
    ) -> EncryptedField:
        """Encrypt a single field value."""
        if sensitivity is None:
            sensitivity = PII_FIELD_MAP.get(field_name, SensitivityLevel.INTERNAL)

        ciphertext = self._encryptor.encrypt(value)
        hash_value = hashlib.sha256(value.encode()).hexdigest()

        return EncryptedField(
            ciphertext=ciphertext,
            field_name=field_name,
            sensitivity=sensitivity,
            hash_value=hash_value,
        )

    def decrypt_field(self, encrypted: EncryptedField) -> str:
        """Decrypt a single encrypted field."""
        return self._encryptor.decrypt(encrypted.ciphertext)

    def encrypt_dict(
        self,
        data: dict[str, Any],
        fields_to_encrypt: list[str] | None = None,
    ) -> dict[str, Any]:
        """Encrypt specified fields in a dictionary.

        If fields_to_encrypt is None, encrypts all fields found in PII_FIELD_MAP.
        """
        result = dict(data)
        target_fields = fields_to_encrypt or [
            k for k in data if k in PII_FIELD_MAP
        ]
        for field_name in target_fields:
            if field_name in result and isinstance(result[field_name], str):
                encrypted = self.encrypt_field(field_name, result[field_name])
                result[field_name] = encrypted.to_dict()
        return result

    def decrypt_dict(
        self,
        data: dict[str, Any],
        fields_to_decrypt: list[str] | None = None,
    ) -> dict[str, Any]:
        """Decrypt specified fields in a dictionary.

        If fields_to_decrypt is None, decrypts all fields that look encrypted.
        """
        result = dict(data)
        for key, value in result.items():
            if not isinstance(value, dict):
                continue
            if "ciphertext" not in value:
                continue
            if fields_to_decrypt and key not in fields_to_decrypt:
                continue
            try:
                encrypted = EncryptedField.from_dict(value)
                result[key] = self.decrypt_field(encrypted)
            except (KeyError, ValueError):
                logger.warning("Could not decrypt field %s", key)
        return result

    def mask_field(self, value: str, visible_chars: int = 4) -> str:
        """Mask a sensitive field for display (e.g., '****1234')."""
        if len(value) <= visible_chars:
            return "*" * len(value)
        masked_len = len(value) - visible_chars
        return "*" * masked_len + value[-visible_chars:]
