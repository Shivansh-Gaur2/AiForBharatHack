"""Authentication & user management service.

Issues JWT tokens compatible with the shared CognitoTokenValidator
(which supports skip_verification mode for local development).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from jose import jwt

from .auth_models import User, UserRole, create_user, verify_password

logger = logging.getLogger(__name__)

# JWT configuration — symmetric signing for local dev
_JWT_SECRET = "rural-credit-advisor-dev-secret-key-2026"
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 24


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthService:
    """Handles user registration, login, and JWT issuance."""

    def __init__(self, user_repo) -> None:
        self._repo = user_repo

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        roles: list[str] | None = None,
    ) -> User:
        """Register a new user account."""
        email = email.lower().strip()
        if not email or not password:
            raise ValueError("Email and password are required")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        existing = await self._repo.find_user_by_email(email)
        if existing is not None:
            raise ValueError("A user with this email already exists")

        parsed_roles = [UserRole(r) for r in (roles or ["CREDIT_OFFICER"])]
        user = create_user(email, password, full_name, parsed_roles)
        await self._repo.save_user(user)

        logger.info("User registered: %s (%s)", email, user.user_id)
        return user

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> tuple[User, str]:
        """Authenticate and return (user, jwt_token)."""
        email = email.lower().strip()
        user = await self._repo.find_user_by_email(email)

        if user is None or not verify_password(user, password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Update last login timestamp
        user.last_login_at = datetime.now(UTC)
        await self._repo.update_user(user)

        token = self._issue_token(user)
        logger.info("User logged in: %s", email)
        return user, token

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def get_user(self, user_id: str) -> User | None:
        return await self._repo.find_user_by_id(user_id)

    def validate_token(self, token: str) -> dict:
        """Decode and validate a JWT token. Returns the payload."""
        try:
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
            return payload
        except jwt.JWTError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _issue_token(user: User) -> str:
        """Create a JWT token mimicking Cognito's payload shape."""
        now = datetime.now(UTC)
        payload = {
            "sub": user.user_id,
            "email": user.email,
            "name": user.full_name,
            "cognito:groups": [r.value for r in user.roles],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=_JWT_EXPIRY_HOURS)).timestamp()),
            "iss": "rural-credit-advisor",
        }
        return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
