"""
Step 10: Publish

Upserts the article to the Cycolaps Neon DB, executes backward link updates
on existing posts, and logs the internal link graph to the SEODOMINATOR DB.

Input:  linked_article (Step 8), seo_output (Step 6), tech_seo (Step 9),
        media (Step 7, optional), run_id
Output: published URL string ("https://cycolaps.com/blog/{slug}")
"""

import json
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from src.pipeline.stage_result import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SITE_BASE = "https://cycolaps.com"
_BLOG_BASE = f"{_SITE_BASE}/blog"


class Step11Publish:
    def __init__(self, settings=None):
        self._settings = settings

    def run(
        self,
        linked_article: dict,
        seo_output: dict,
        tech_seo: dict,
        media: Optional[dict],
        run_id: Optional[int],
    ) -> StageResult:
        """
        Args:
            linked_article: Output of Step 8 (article content + linking metadata).
            seo_output:     Output of Step 6 (optimized content, SEO fields).
            tech_seo:       Output of Step 9 (canonical URL, OG tags, JSON-LD).
            media:          Output of Step 7 (optional, image URLs).
            run_id:         Current pipeline run ID for SEODOMINATOR DB logging.

        Returns:
            StageResult whose .value is the published URL string.
        """
        slug = linked_article.get("new_article_slug", "")
        if not slug:
            raise ValueError("Step 10 requires new_article_slug from Step 8")

        published_url = f"{_BLOG_BASE}/{slug}"

        cycolaps_url = getattr(self._settings, "cycolaps_database_url", "") if self._settings else ""
        seodom_url = getattr(self._settings, "database_url", "") if self._settings else ""

        # ── 1. Upsert post to Cycolaps Neon DB ───────────────────────────────
        post_id = None
        if cycolaps_url:
            post_id = self._upsert_post(cycolaps_url, linked_article, seo_output, tech_seo, media, slug, published_url)
        else:
            logger.warning("CYCOLAPS_DATABASE_URL not set — skipping Cycolaps publish")

        # ── 2. Execute backward link updates ─────────────────────────────────
        backward_updates = linked_article.get("backward_link_updates", [])
        links_applied = 0
        if cycolaps_url and backward_updates:
            links_applied = self._apply_backward_links(cycolaps_url, backward_updates)
            logger.info(f"Applied backward links to {links_applied} existing posts.")
        elif backward_updates:
            logger.warning("Skipping backward link updates — no Cycolaps DB URL")

        # ── 3. Log internal links to SEODOMINATOR DB ─────────────────────────
        forward_links = linked_article.get("forward_links", [])
        if seodom_url and forward_links and run_id:
            self._log_internal_links(seodom_url, slug, forward_links, run_id)
        elif forward_links:
            logger.warning("Skipping internal link logging — no SEODOMINATOR DB URL or run_id")

        logger.info(
            f"Step 10 complete. published_url={published_url} "
            f"post_id={post_id} backward_updates={links_applied} forward_links={len(forward_links)}"
        )

        return StageResult(value=published_url, tokens_in=0, tokens_out=0)

    def _upsert_post(
        self,
        db_url: str,
        linked_article: dict,
        seo_output: dict,
        tech_seo: dict,
        media: Optional[dict],
        slug: str,
        published_url: str,
    ) -> Optional[str]:
        now = datetime.now(timezone.utc)
        m = media or {}

        content   = linked_article.get("content", "")
        title     = linked_article.get("seo_title") or seo_output.get("seo_title", "")
        meta_desc = linked_article.get("meta_description") or seo_output.get("meta_description", "")
        tags      = linked_article.get("seo_tags") or seo_output.get("seo_tags", [])
        image     = linked_article.get("hero_image_url") or m.get("hero_image_url") or "/blog/ai.png"
        category  = linked_article.get("primary_keyword") or seo_output.get("primary_keyword") or "AI"
        word_count = linked_article.get("word_count") or seo_output.get("word_count") or 0

        excerpt   = _extract_excerpt(content)
        read_time = f"{max(1, round(word_count / 200))} min read"

        # Merge article + FAQ schemas into a single jsonb value
        json_ld = linked_article.get("json_ld") or tech_seo.get("json_ld_article") or {}
        faq     = linked_article.get("faq_schema") or tech_seo.get("json_ld_faq")
        if faq:
            json_ld = {"article": json_ld, "faq": faq}

        sql = """
            INSERT INTO posts (
                slug, title, content, excerpt, meta_description,
                image, tags, json_ld,
                category, read_time, published, date, updated_at
            )
            VALUES (
                %(slug)s, %(title)s, %(content)s, %(excerpt)s, %(meta_description)s,
                %(image)s, %(tags)s, %(json_ld)s,
                %(category)s, %(read_time)s, TRUE, %(date)s, %(updated_at)s
            )
            ON CONFLICT (slug) DO UPDATE SET
                title            = EXCLUDED.title,
                content          = EXCLUDED.content,
                excerpt          = EXCLUDED.excerpt,
                meta_description = EXCLUDED.meta_description,
                image            = EXCLUDED.image,
                tags             = EXCLUDED.tags,
                json_ld          = EXCLUDED.json_ld,
                category         = EXCLUDED.category,
                read_time        = EXCLUDED.read_time,
                published        = TRUE,
                updated_at       = EXCLUDED.updated_at
            RETURNING slug
        """
        params = {
            "slug":             slug,
            "title":            title,
            "content":          content,
            "excerpt":          excerpt,
            "meta_description": meta_desc,
            "image":            image,
            "tags":             tags,
            "json_ld":          psycopg2.extras.Json(json_ld) if json_ld else None,
            "category":         category,
            "read_time":        read_time,
            "date":             now.strftime("%Y-%m-%d"),
            "updated_at":       now,
        }

        try:
            conn = psycopg2.connect(db_url)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    returned_slug = row[0] if row else None
            conn.close()
            logger.info(f"Upserted post slug='{returned_slug}' to Cycolaps DB.")
            return returned_slug
        except Exception as exc:
            logger.error(f"Cycolaps DB upsert failed: {exc}")
            raise

    def _apply_backward_links(self, db_url: str, backward_updates: list) -> int:
        """
        For each existing post in backward_updates, replace original sentences
        with link-injected versions using atomic per-post transactions.
        """
        applied = 0
        try:
            conn = psycopg2.connect(db_url)
            for update in backward_updates:
                post_slug = update.get("post_slug", "")
                link_updates = update.get("link_updates", [])
                if not post_slug or not link_updates:
                    continue
                try:
                    with conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT content FROM posts WHERE slug = %s FOR UPDATE",
                                (post_slug,),
                            )
                            row = cur.fetchone()
                            if not row:
                                logger.warning(f"Post '{post_slug}' not found for backward linking")
                                continue

                            content = row[0]
                            changed = False
                            for lu in link_updates:
                                original = lu.get("original_sentence", "")
                                replacement = lu.get("replacement_sentence", "")
                                if original and replacement and original in content:
                                    content = content.replace(original, replacement, 1)
                                    changed = True

                            if changed:
                                cur.execute(
                                    "UPDATE posts SET content = %s, updated_at = %s WHERE slug = %s",
                                    (content, datetime.now(timezone.utc).isoformat(), post_slug),
                                )
                                applied += 1
                                logger.info(f"Backward links applied to '{post_slug}'")
                            else:
                                logger.info(f"No sentence matches found in '{post_slug}' — skipped")
                except Exception as exc:
                    logger.warning(f"Backward link update failed for '{post_slug}': {exc}")
                    continue
            conn.close()
        except Exception as exc:
            logger.error(f"Backward link DB connection failed: {exc}")
        return applied

    def _log_internal_links(self, db_url: str, source_slug: str, forward_links: list, run_id: int) -> None:
        """Upsert each forward link into the SEODOMINATOR internal_links table."""
        if not forward_links:
            return
        try:
            from src.storage.database import Database
            # Use raw psycopg2 for simplicity — SQLAlchemy session is for ORM use
            conn = psycopg2.connect(db_url)
            sql = """
                INSERT INTO internal_links (source_slug, target_slug, anchor_text, created_by_run)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source_slug, target_slug) DO NOTHING
            """
            with conn:
                with conn.cursor() as cur:
                    for link in forward_links:
                        cur.execute(sql, (
                            source_slug,
                            link.get("target_slug", ""),
                            link.get("anchor_text", ""),
                            run_id,
                        ))
            conn.close()
            logger.info(f"Logged {len(forward_links)} internal links to SEODOMINATOR DB.")
        except Exception as exc:
            logger.warning(f"Internal link logging failed: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_excerpt(content: str, max_chars: int = 200) -> str:
    import re
    text = re.sub(r"#+ ", "", content)
    text = re.sub(r"\*{1,2}|_{1,2}", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    return text[:cut] + "…"
