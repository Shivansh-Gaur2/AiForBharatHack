"""FastAPI middleware for JWT authentication and RBAC.

Integrates the CognitoTokenValidator with FastAPI's dependency injection
to provide request-level authentication and role-based authorization.

Usage in routes:
    from services.shared.auth.middleware import require_auth, require_roles

    @router.get("/protected")
    async def protected(auth: AuthContext = Depends(require_auth)):
        ...

    @router.get("/admin-only")
    async def admin_only(auth: AuthContext = Depends(require_roles(UserRole.ADMIN))):
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import AuthContext, CognitoTokenValidator, UserRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level validator (set once at app startup)
# ---------------------------------------------------------------------------
_validator: CognitoTokenValidator | None = None


def configure_auth(
    user_pool_id: str = "local",
    region: str = "ap-south-1",
    app_client_id: str = "local",
    *,
    skip_verification: bool = True,
) -> None:
    """Wire up the auth middleware.  Call once from main.py."""
    global _validator
    _validator = CognitoTokenValidator(
        user_pool_id=user_pool_id,
        region=region,
        app_client_id=app_client_id,
        skip_verification=skip_verification,
    )
    logger.info(
        "Auth configured (pool=%s, skip_verification=%s)",
        user_pool_id,
        skip_verification,
    )


def get_validator() -> CognitoTokenValidator:
    if _validator is None:
        raise RuntimeError("Auth not configured — call configure_auth() first")
    return _validator


# ---------------------------------------------------------------------------
# Bearer-token extraction
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


async def _extract_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """Extract and validate the JWT from the Authorization header."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        validator = get_validator()
        return validator.validate_token(credentials.credentials)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from None


# ---------------------------------------------------------------------------
# Public dependency: require_auth
# ---------------------------------------------------------------------------
require_auth = _extract_auth


# ---------------------------------------------------------------------------
# Role-gated dependency factory
# ---------------------------------------------------------------------------
def require_roles(
    *roles: UserRole,
) -> Callable[..., AuthContext]:
    """Create a FastAPI dependency that checks the caller has one of the given roles.

    Example::

        @router.get("/admin")
        async def admin_endpoint(auth: AuthContext = Depends(require_roles(UserRole.ADMIN))):
            ...
    """

    async def _check(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        if not auth.has_any_role(*roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {[r.value for r in roles]}",
            )
        return auth

    return _check


# ---------------------------------------------------------------------------
# Optional auth (for endpoints accessible to both authed and anonymous)
# ---------------------------------------------------------------------------
async def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext | None:
    """Return AuthContext if a valid token is present, else None."""
    if credentials is None:
        return None
    try:
        validator = get_validator()
        return validator.validate_token(credentials.credentials)
    except PermissionError:
        return None


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------
def audit_context(auth: AuthContext, action: str) -> dict:
    """Build a dict suitable for audit log entries."""
    return {
        "user_id": auth.user_id,
        "roles": [r.value for r in auth.roles],
        "action": action,
    }
