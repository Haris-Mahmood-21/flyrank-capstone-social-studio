"""Authentication router — POST /auth/login."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import new_correlation_id
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password and receive a Bearer JWT."""
    cid = new_correlation_id()
    logger.info("Login attempt for %s cid=%s", payload.email, cid)

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always run a hash verify to prevent user-enumeration via timing.
    # The dummy hash is a valid bcrypt string (hash of "sentinel") so passlib won't error.
    _dummy_hash = "$2b$12$ou/cdlk9QUexd4riyU9XxOD9vUt3/vXKXoATVkPzdiBnm9LqBDqca"
    stored_hash = user.hashed_password if user else _dummy_hash
    password_ok = verify_password(payload.password, stored_hash)

    if not password_ok or user is None:
        logger.warning("Failed login for %s cid=%s", payload.email, cid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(subject=user.email)
    logger.info("Login successful for %s cid=%s", payload.email, cid)
    return TokenResponse(access_token=token)
