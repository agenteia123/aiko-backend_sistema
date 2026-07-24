"""Authentication utilities."""

import logging
from fastapi import HTTPException, Header, Depends
from typing import Optional

from config.settings import settings


logger = logging.getLogger(__name__)


async def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Header(None),
) -> str:
    """Verify API key from headers."""
    key = x_api_key or api_key
    
    if not key:
        # Allow unauthenticated for development
        if settings.DEBUG:
            logger.warning("⚠️  No API key provided (DEBUG mode enabled)")
            return "debug-key"
        raise HTTPException(status_code=401, detail="API key required")
    
    # In production, verify against settings
    if key != settings.API_KEY:
        if not settings.DEBUG:
            raise HTTPException(status_code=403, detail="Invalid API key")
        logger.warning(f"Invalid API key attempted: {key[:10]}...")
    
    return key


def create_api_key() -> str:
    """Generate a new API key."""
    import secrets
    return f"aiko-{secrets.token_hex(32)}"
