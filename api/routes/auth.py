"""Single-user login endpoint for the private Aiko installation."""

import hmac
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import create_access_token
from config.settings import settings
from utils import SimpleRateLimiter


router = APIRouter()
_login_limiter = SimpleRateLimiter(max_requests=8, window_seconds=60)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


@router.post("/login")
async def login(request: Request, credentials: LoginRequest):
    """Authenticate the one configured user and issue a short-lived JWT."""
    if not settings.AUTH_USERNAME or not settings.AUTH_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail="Configura AUTH_USERNAME y AUTH_PASSWORD en el entorno privado del backend.",
        )

    if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
        raise HTTPException(
            status_code=503,
            detail="Configura un JWT_SECRET aleatorio de al menos 32 caracteres.",
        )

    client_host: Optional[str] = request.client.host if request.client else None
    rate_limit_key = client_host or "unknown-client"
    if not _login_limiter.is_allowed(rate_limit_key):
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera un minuto y vuelve a intentar.",
        )

    username_ok = hmac.compare_digest(
        credentials.username.encode("utf-8"), settings.AUTH_USERNAME.encode("utf-8")
    )
    password_ok = hmac.compare_digest(
        credentials.password.encode("utf-8"), settings.AUTH_PASSWORD.encode("utf-8")
    )
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    token, expires_in = create_access_token(settings.AUTH_USER_ID)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user_id": settings.AUTH_USER_ID,
    }
