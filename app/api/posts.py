"""Posts router — POST /posts, GET /posts/{id}."""

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
from app.schemas.post import PostCreate, PostResponse
from app.services import ingestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Post:
    """Ingest a blog post from a URL or pasted markdown."""
    cid = new_correlation_id()
    logger.info(
        "Ingesting post title='%s' source_type=%s cid=%s",
        payload.title,
        payload.source_type.value,
        cid,
    )
    try:
        post = await ingestion.ingest(payload)
    except Exception as exc:
        logger.error("Ingestion failed: %s cid=%s", exc, cid)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch source content: {exc}",
        ) from exc

    db.add(post)
    await db.commit()
    await db.refresh(post)
    logger.info("Post created id=%s cid=%s", post.id, cid)
    return post


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Post:
    """Retrieve a post by ID."""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )
    return post
