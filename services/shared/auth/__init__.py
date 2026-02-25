"""Cognito JWT validation and RBAC middleware.

Validates JWT tokens issued by Amazon Cognito User Pools and
extracts user roles for authorization decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
class UserRole(StrEnum):
    BORROWER = "BORROWER"
    FIELD_AGENT = "FIELD_AGENT"
    CREDIT_OFFICER = "CREDIT_OFFICER"
    ADMIN = "ADMIN"


# ---------------------------------------------------------------------------
# Auth context (populated after token validation)
# ---------------------------------------------------------------------------
@dataclass
class AuthContext:
    user_id: str
    roles: list[UserRole]
    cognito_groups: list[str]
    email: str | None = None

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: UserRole) -> bool:
        return any(r in self.roles for r in roles)


# ---------------------------------------------------------------------------
# Token validator
# ---------------------------------------------------------------------------
class CognitoTokenValidator:
    """Validates Cognito JWT tokens.

    In production, this verifies the token signature against Cognito's JWKS
    endpoint.  For local development / testing, validation can be skipped.
    """

    def __init__(
        self,
        user_pool_id: str,
        region: str,
        app_client_id: str,
        *,
        skip_verification: bool = False,
    ) -> None:
        self._user_pool_id = user_pool_id
        self._region = region
        self._app_client_id = app_client_id
        self._skip_verification = skip_verification
        self._jwks: dict[str, Any] | None = None

    def validate_token(self, token: str) -> AuthContext:
        """Validate a JWT token and return an AuthContext.

        Raises ``PermissionError`` if the token is invalid.
        """
        if self._skip_verification:
            # Local dev / test — decode without verification
            import base64
            import json

            try:
                payload_segment = token.split(".")[1]
                # Add padding
                payload_segment += "=" * (4 - len(payload_segment) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_segment))
            except Exception as exc:
                raise PermissionError(f"Invalid token format: {exc}") from exc
        else:
            payload = self._verify_token(token)

        return AuthContext(
            user_id=payload.get("sub", ""),
            roles=[
                UserRole(g)
                for g in payload.get("cognito:groups", [])
                if g in UserRole.__members__
            ],
            cognito_groups=payload.get("cognito:groups", []),
            email=payload.get("email"),
        )

    def _verify_token(self, token: str) -> dict[str, Any]:
        """Full JWT verification against Cognito JWKS (production path)."""
        try:
            import jwt  # PyJWT
            from jwt import PyJWKClient

            jwks_url = (
                f"https://cognito-idp.{self._region}.amazonaws.com/"
                f"{self._user_pool_id}/.well-known/jwks.json"
            )
            jwk_client = PyJWKClient(jwks_url)
            signing_key = jwk_client.get_signing_key_from_jwt(token)

            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._app_client_id,
                issuer=f"https://cognito-idp.{self._region}.amazonaws.com/{self._user_pool_id}",
            )
        except Exception as exc:
            logger.warning("Token verification failed: %s", exc)
            raise PermissionError(f"Token verification failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Require-role decorator (for FastAPI dependency injection)
# ---------------------------------------------------------------------------
def require_role(*required_roles: UserRole):
    """FastAPI dependency factory that checks authorization."""

    def _check(auth: AuthContext) -> AuthContext:
        if not auth.has_any_role(*required_roles):
            raise PermissionError(
                f"Requires one of: {[r.value for r in required_roles]}"
            )
        return auth

    return _check
