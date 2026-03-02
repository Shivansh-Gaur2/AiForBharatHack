"""FastAPI routes for authentication — login, register, token validation."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..domain.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Service injection (set from main.py)
# ---------------------------------------------------------------------------
_auth_service: AuthService | None = None


def set_auth_service(svc: AuthService) -> None:
    global _auth_service
    _auth_service = svc


def get_auth_service() -> AuthService:
    if _auth_service is None:
        raise RuntimeError("AuthService not initialised")
    return _auth_service


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    roles: list[str] = Field(default_factory=lambda: ["CREDIT_OFFICER"])


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserDTO(BaseModel):
    user_id: str
    email: str
    full_name: str
    roles: list[str]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AuthResponse(BaseModel):
    user: UserDTO
    token: str


class TokenValidationResponse(BaseModel):
    valid: bool
    user_id: str | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)


class TokenRequest(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest):
    """Register a new user account."""
    svc = get_auth_service()
    try:
        user = await svc.register(
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            roles=req.roles,
        )
        _, token = await svc.login(req.email, req.password)
        return AuthResponse(
            user=UserDTO(
                user_id=user.user_id,
                email=user.email,
                full_name=user.full_name,
                roles=[r.value for r in user.roles],
                is_active=user.is_active,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            ),
            token=token,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Authenticate and receive a JWT token."""
    svc = get_auth_service()
    try:
        user, token = await svc.login(req.email, req.password)
        return AuthResponse(
            user=UserDTO(
                user_id=user.user_id,
                email=user.email,
                full_name=user.full_name,
                roles=[r.value for r in user.roles],
                is_active=user.is_active,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            ),
            token=token,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(req: TokenRequest):
    """Validate a JWT token and return the decoded payload."""
    svc = get_auth_service()
    try:
        payload = svc.validate_token(req.token)
        return TokenValidationResponse(
            valid=True,
            user_id=payload.get("sub"),
            email=payload.get("email"),
            roles=payload.get("cognito:groups", []),
        )
    except AuthenticationError:
        return TokenValidationResponse(valid=False)


@router.get("/me", response_model=UserDTO)
async def get_current_user():
    """Placeholder — in production, extract user from the Authorization header."""
    raise HTTPException(
        status_code=501,
        detail="Use /validate with a token to get user info",
    )
