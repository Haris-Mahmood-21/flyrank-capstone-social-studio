"""Post ingestion service.

Handles two source types:
  - markdown: stores raw_content directly from the request body
  - url: fetches the URL with httpx, strips HTML tags to plain text,
         stores as raw_content
"""

import logging
from html.parser import HTMLParser

import httpx

from app.models.post import Post, SourceType
from app.schemas.post import PostCreate

logger = logging.getLogger(__name__)

_SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside"})
_BLOCK_TAGS = frozenset({"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr"})


class _TextExtractor(HTMLParser):
    """Minimal HTML→plain-text converter using only stdlib."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._depth: dict[str, int] = {}

    def _in_skip(self) -> bool:
        return any(self._depth.get(t, 0) > 0 for t in _SKIP_TAGS)

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        if tag in _SKIP_TAGS:
            self._depth[tag] = self._depth.get(tag, 0) + 1
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._depth[tag] = max(0, self._depth.get(tag, 1) - 1)

    def handle_data(self, data: str) -> None:
        if not self._in_skip() and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        return " ".join(chunk for chunk in self._chunks if chunk.strip())


def _strip_html(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


async def fetch_url_content(url: str) -> str:
    """Fetch a URL and return its content as plain text."""
    logger.info("Fetching URL for ingestion: %s", url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = client.get(url)
        response = await response  # type: ignore[assignment]
        response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" in content_type:
        return _strip_html(response.text)
    return response.text


def build_post(payload: PostCreate, raw_content: str) -> Post:
    """Construct an unsaved Post ORM object from validated input."""
    return Post(
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        raw_content=raw_content,
        title=payload.title,
    )


async def ingest(payload: PostCreate) -> Post:
    """
    Ingest a post from markdown or URL.

    Returns an unsaved Post ORM object. The caller is responsible for
    adding it to the session and committing.
    """
    if payload.source_type == SourceType.MARKDOWN:
        raw_content = payload.raw_content or ""
    else:
        raw_content = await fetch_url_content(payload.source_ref or "")

    logger.info(
        "Ingested post '%s' (%s, %d chars)",
        payload.title,
        payload.source_type.value,
        len(raw_content),
    )
    return build_post(payload, raw_content)
