"""
Step 8: Internal Linking (Bidirectional)

Forward links:  injects 3-5 links from the new article → existing published posts
Backward links: for each existing post, finds 0-2 places to link back → new article

Input:  seo_output (Step 6), media (Step 7, optional)
Output: article with forward links injected + list of backward link updates for Step 10
"""

import json
import re
from typing import List, Optional

import psycopg2
import psycopg2.extras

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    forward_link_injection_prompt,
    backward_link_injection_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SITE_BASE = "https://cycolaps.com"


class Step8InternalLinking:
    """Bidirectional internal linking engine."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)

    def run(self, seo_output: dict, media: Optional[dict] = None) -> dict:
        """
        Args:
            seo_output: Output of Step 6 (contains optimized_content, seo_title, etc.)
            media:      Output of Step 7 (optional — used for embedding in-article images).

        Returns:
            {
                "content": str,                    # article with forward links injected
                "seo_title": str,
                "meta_description": str,
                "seo_tags": [str],
                "keyword_density": float,
                "word_count": int,
                "json_ld": dict,
                "faq_schema": list,
                "primary_keyword": str,
                "supporting_keywords": [str],
                "hero_image_url": str,
                "in_article_images": list,
                "forward_links": [dict],           # links injected into new article
                "forward_link_count": int,
                "backward_link_updates": [dict],   # updates for existing posts (Step 10 executes)
                "new_article_slug": str,
            }
        """
        content = seo_output.get("optimized_content", "")
        title = seo_output.get("seo_title", "")
        keyword = seo_output.get("primary_keyword", "")

        if not content or not title:
            raise ValueError("Step 8 requires optimized_content and seo_title")

        slug = _slugify(title)
        excerpt = _extract_excerpt(content)
        tokens_in = 0
        tokens_out = 0

        # ── Fetch existing posts from Cycolaps DB ─────────────────────────────
        logger.info("Fetching existing posts from Cycolaps DB for internal linking...")
        existing_posts = self._fetch_existing_posts()

        if not existing_posts:
            logger.warning("No existing posts found — skipping internal linking")
            result = _passthrough(seo_output, media, slug, [], [], content)
            return StageResult(value=result, tokens_in=0, tokens_out=0)

        logger.info(f"Found {len(existing_posts)} existing posts to consider for linking.")

        # ── Forward links: new article → existing posts ───────────────────────
        logger.info("Identifying forward linking opportunities...")
        forward_links, t_in, t_out = self._find_forward_links(content, existing_posts)
        tokens_in += t_in
        tokens_out += t_out

        linked_content = content
        if forward_links:
            linked_content = self._inject_forward_links(content, forward_links, slug)
            logger.info(f"Injected {len(forward_links)} forward links into new article.")

        # ── Backward links: existing posts → new article ──────────────────────
        logger.info("Scanning existing posts for backward link opportunities...")
        backward_updates = []
        for post in existing_posts[:20]:  # limit to 20 posts to control token cost
            updates, t_in, t_out = self._find_backward_links(
                new_title=title,
                new_slug=slug,
                new_excerpt=excerpt,
                existing_post=post,
            )
            tokens_in += t_in
            tokens_out += t_out
            if updates:
                backward_updates.append({
                    "post_slug": post["slug"],
                    "post_title": post["title"],
                    "link_updates": updates,
                })

        logger.info(f"Step 8 complete. Forward: {len(forward_links)} links. Backward updates for {len(backward_updates)} posts.")

        result = _passthrough(seo_output, media, slug, forward_links, backward_updates, linked_content)
        return StageResult(value=result, tokens_in=tokens_in, tokens_out=tokens_out)

    def _fetch_existing_posts(self) -> List[dict]:
        db_url = self._settings.cycolaps_database_url if self._settings else ""
        if not db_url:
            logger.warning("CYCOLAPS_DATABASE_URL not set — cannot fetch existing posts")
            return []
        try:
            conn = psycopg2.connect(db_url)
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        "SELECT slug, title, excerpt, content FROM posts WHERE published = TRUE ORDER BY date DESC LIMIT 100"
                    )
                    rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Failed to fetch existing posts: {exc}")
            return []

    def _find_forward_links(self, content: str, existing_posts: List[dict]) -> tuple:
        prompt = forward_link_injection_prompt(content, existing_posts)
        response = self._client.messages.create(
            model=self._client.model,
            max_tokens=2048,
            system=[make_cache_block(SEO_EXPERT_SYSTEM)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )
        raw = response.content[0].text.strip()
        try:
            data = json.loads(raw)
            return data.get("forward_links", []), response.usage.input_tokens, response.usage.output_tokens
        except json.JSONDecodeError:
            logger.warning("Forward link JSON parse failed")
            return [], response.usage.input_tokens, response.usage.output_tokens

    def _find_backward_links(self, new_title: str, new_slug: str, new_excerpt: str, existing_post: dict) -> tuple:
        prompt = backward_link_injection_prompt(new_title, new_slug, new_excerpt, existing_post)
        response = self._client.messages.create(
            model=self._client.model,
            max_tokens=512,
            system=[make_cache_block(SEO_EXPERT_SYSTEM)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )
        raw = response.content[0].text.strip()
        try:
            data = json.loads(raw)
            links = data.get("backward_links", [])
            return links, response.usage.input_tokens, response.usage.output_tokens
        except json.JSONDecodeError:
            return [], response.usage.input_tokens, response.usage.output_tokens

    def _inject_forward_links(self, content: str, forward_links: List[dict], new_slug: str) -> str:
        """Replace original sentences with link-injected versions in the content."""
        for link in forward_links:
            original = link.get("sentence_context", "")
            replacement = link.get("replacement_sentence", "")
            target_slug = link.get("target_slug", "")
            if not original or not replacement or not target_slug:
                continue
            # Insert actual URL into markdown link placeholder
            target_url = f"{_SITE_BASE}/blog/{target_slug}"
            replacement = replacement.replace("(url)", f"({target_url})")
            content = content.replace(original, replacement, 1)
        return content


# ── Helpers ───────────────────────────────────────────────────────────────────

def _passthrough(seo_output: dict, media: Optional[dict], slug: str, forward_links: list, backward_updates: list, content: str) -> dict:
    """Build the Step 8 output dict."""
    m = media or {}
    return {
        "content": content,
        "seo_title": seo_output.get("seo_title", ""),
        "meta_description": seo_output.get("meta_description", ""),
        "seo_tags": seo_output.get("seo_tags", []),
        "keyword_density": seo_output.get("keyword_density", 0.0),
        "word_count": len(content.split()),
        "json_ld": seo_output.get("json_ld", {}),
        "faq_schema": seo_output.get("faq_schema", []),
        "primary_keyword": seo_output.get("primary_keyword", ""),
        "supporting_keywords": seo_output.get("supporting_keywords", []),
        "hero_image_url": m.get("hero_image_url", "/blog/ai.png"),
        "hero_alt_text": m.get("hero_alt_text", ""),
        "in_article_images": m.get("in_article_images", []),
        "image_urls": m.get("image_urls", []),
        "forward_links": forward_links,
        "forward_link_count": len(forward_links),
        "backward_link_updates": backward_updates,
        "new_article_slug": slug,
    }


def _slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:80]


def _extract_excerpt(content: str, max_chars: int = 200) -> str:
    text = re.sub(r"#+ ", "", content)
    text = re.sub(r"\*{1,2}|_{1,2}", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    return text[:cut] + "…"
