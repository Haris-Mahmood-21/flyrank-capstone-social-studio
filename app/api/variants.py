"""Variants router — generate, view, approve, reject."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import new_correlation_id
from app.core.security import get_current_user
from app.models.post import Post
from app.models.user import User
from app.models.variant import Variant
from app.schemas.variant import GenerateRequest, GenerateResponse, VariantResponse
from app.services.generation import ConstraintViolationError, generate_variants

logger = logging.getLogger(__name__)
router = APIRouter(tags=["variants"])


@router.post(
    "/posts/{post_id}/variants/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate(
    post_id: uuid.UUID,
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> GenerateResponse:
    """
    Generate AI variants for a post on each requested platform.

    All variants must pass their constraint profile; if any violates,
    the whole request is rejected with 422 and nothing is written to the DB.
    """
    cid = new_correlation_id()
    logger.info(
        "Generating variants for post=%s platforms=%s cid=%s",
        post_id,
        payload.platform_keys,
        cid,
    )

    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )

    try:
        variants = await generate_variants(post, payload.platform_keys, db)
    except ConstraintViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        logger.error("Generation failed: %s cid=%s", exc, cid)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    logger.info("Generated %d variants for post=%s cid=%s", len(variants), post_id, cid)
    return GenerateResponse(variants=[VariantResponse.model_validate(v) for v in variants])


@router.get("/variants/{variant_id}", response_model=VariantResponse)
async def get_variant(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Variant:
    """Retrieve a single variant by ID."""
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found",
        )
    return variant
