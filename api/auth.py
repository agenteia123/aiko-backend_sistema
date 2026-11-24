"""JWT authentication for the private Aiko API."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from config.settings import settings


def _require_jwt_secret() -> str:
    secret = settings.JWT_SECRET
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="El backend no tiene configurado un JWT_SECRET seguro.",
        )
    return secret


def create_access_token(subject: str) -> tuple[str, int]:
    """Create a short-lived access token for the configured Aiko user."""
    secret = _require_jwt_secret()
    lifetime = max(1, settings.JWT_EXPIRATION_HOURS)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=lifetime)
    token = jwt.encode(
        {
            "sub": subject,
            "type": "access",
            "iat": now,
            "exp": expires_at,
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, lifetime * 3600


def decode_access_token(token: str) -> str:
    """Return the authenticated user id or reject the token."""
    try:
        payload = jwt.decode(
            token,
            _require_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require_sub": True, "require_exp": True},
        )
    except HTTPException:
        raise
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida.") from exc

    subject = payload.get("sub")
    if payload.get("type") != "access" or not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="Token de acceso inválido.")
    return subject


async def verify_api_key(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """Compatibility dependency name; now accepts only a Bearer access token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token de acceso requerido.")
    return decode_access_token(token)
