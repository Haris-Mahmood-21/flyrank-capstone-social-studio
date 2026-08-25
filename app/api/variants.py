"""Variants router — generate, view, edit, approve, reject, schedule."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import new_correlation_id
from app.core.security import get_current_user
from app.models.constraint_profile import ConstraintProfile
from app.models.post import Post
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.models.user import User
from app.models.variant import Variant, VariantStatus
from app.schemas.schedule import ScheduleCreate, ScheduleSlotResponse
from app.schemas.variant import GenerateRequest, GenerateResponse, VariantResponse, VariantUpdate
from app.services.generation import (
    ConstraintViolationError,
    generate_variants,
    validate_against_profile,
)

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
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found",
        )
    return variant


@router.patch("/variants/{variant_id}", response_model=VariantResponse)
async def update_variant(
    variant_id: uuid.UUID,
    payload: VariantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Variant:
    """Edit variant content/hashtags. Re-validates against platform constraints."""
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    # If it's already approved, editing bumps it back to DRAFT or we could block edits.
    # The spec just says edit content, let's allow it but re-validate.
    new_content = payload.content if payload.content is not None else variant.content
    new_hashtags = payload.hashtags if payload.hashtags is not None else variant.hashtags

    prof_result = await db.execute(
        select(ConstraintProfile).where(ConstraintProfile.platform_key == variant.platform_key)
    )
    profile = prof_result.scalar_one_or_none()
    if profile:
        try:
            validate_against_profile(new_content, new_hashtags, profile)
        except ConstraintViolationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

    variant.content = new_content
    variant.hashtags = new_hashtags

    if payload.content is not None or payload.hashtags is not None:
        if variant.status == VariantStatus.APPROVED:
            variant.status = VariantStatus.DRAFT  # require re-approval

    await db.commit()
    await db.refresh(variant)
    return variant


@router.post("/variants/{variant_id}/approve", response_model=VariantResponse)
async def approve_variant(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Variant:
    """Approve a variant."""
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    variant.status = VariantStatus.APPROVED
    await db.commit()
    await db.refresh(variant)
    return variant


@router.post("/variants/{variant_id}/reject", response_model=VariantResponse)
async def reject_variant(
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Variant:
    """Reject a variant."""
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    variant.status = VariantStatus.REJECTED
    await db.commit()
    await db.refresh(variant)
    return variant


@router.post(
    "/variants/{variant_id}/schedule",
    response_model=ScheduleSlotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_variant(
    variant_id: uuid.UUID,
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScheduleSlot:
    """
    Schedule an approved variant for publication.
    Enforces that unapproved variants cannot be scheduled.
    """
    result = await db.execute(select(Variant).where(Variant.id == variant_id))
    variant = result.scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    if variant.status != VariantStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot schedule variant with status {variant.status.value}",
        )

    if payload.scheduled_for < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot schedule in the past",
        )

    # Core idempotency key requirement
    idemp_key = f"{variant_id}:{payload.scheduled_for.isoformat()}"

    slot = ScheduleSlot(
        variant_id=variant_id,
        scheduled_for=payload.scheduled_for,
        idempotency_key=idemp_key,
        status=SlotStatus.PENDING,
    )
    db.add(slot)

    try:
        await db.commit()
        await db.refresh(slot)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A schedule slot for this variant already exists.",
        ) from exc

    return slot
