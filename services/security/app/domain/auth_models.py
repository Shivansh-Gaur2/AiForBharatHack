"""Domain models for authentication & user management.

Simple JWT-based auth for local/hackathon use. In production, this would
be replaced by AWS Cognito or a dedicated identity provider.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class UserRole(StrEnum):
    BORROWER = "BORROWER"
    FIELD_AGENT = "FIELD_AGENT"
    CREDIT_OFFICER = "CREDIT_OFFICER"
    ADMIN = "ADMIN"


@dataclass
class User:
    """Registered user account."""

    user_id: str
    email: str
    password_hash: str
    salt: str
    full_name: str
    roles: list[UserRole] = field(default_factory=lambda: [UserRole.CREDIT_OFFICER])
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None


def _hash_password(password: str, salt: str) -> str:
    """SHA-256 password hashing with salt. Good enough for local dev."""
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def create_user(
    email: str,
    password: str,
    full_name: str,
    roles: list[UserRole] | None = None,
) -> User:
    """Factory: create a new user with a hashed password."""
    salt = os.urandom(16).hex()
    return User(
        user_id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=_hash_password(password, salt),
        salt=salt,
        full_name=full_name,
        roles=roles or [UserRole.CREDIT_OFFICER],
    )


def verify_password(user: User, password: str) -> bool:
    """Check a plaintext password against the stored hash."""
    return _hash_password(password, user.salt) == user.password_hash
