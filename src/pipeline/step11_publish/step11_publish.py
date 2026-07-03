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
    ) -> Optional[int]:
        now = datetime.now(timezone.utc).isoformat()
        m = media or {}
        hero_image_url = linked_article.get("hero_image_url") or m.get("hero_image_url", "/blog/ai.png")
        hero_alt_text = linked_article.get("hero_alt_text") or m.get("hero_alt_text", "")

        content = linked_article.get("content", "")
        title = linked_article.get("seo_title", "")
        meta_desc = linked_article.get("meta_description", "")
        tags = json.dumps(linked_article.get("seo_tags", []))
        word_count = linked_article.get("word_count", 0)
        keyword_density = linked_article.get("keyword_density", 0.0)

        og_tags = json.dumps(tech_seo.get("og_tags", {}))
        twitter_tags = json.dumps(tech_seo.get("twitter_tags", {}))
        canonical_url = tech_seo.get("canonical_url", published_url)
        json_ld_article = json.dumps(tech_seo.get("json_ld_article", {}))
        json_ld_faq = json.dumps(tech_seo.get("json_ld_faq", {}))

        excerpt = _extract_excerpt(content)

        sql = """
            INSERT INTO posts (
                slug, title, content, excerpt, meta_description,
                seo_title, tags, hero_image_url, hero_alt_text,
                canonical_url, og_tags, twitter_tags,
                json_ld_article, json_ld_faq,
                word_count, keyword_density,
                published, date, updated_at
            )
            VALUES (
                %(slug)s, %(title)s, %(content)s, %(excerpt)s, %(meta_description)s,
                %(seo_title)s, %(tags)s, %(hero_image_url)s, %(hero_alt_text)s,
                %(canonical_url)s, %(og_tags)s, %(twitter_tags)s,
                %(json_ld_article)s, %(json_ld_faq)s,
                %(word_count)s, %(keyword_density)s,
                TRUE, %(date)s, %(updated_at)s
            )
            ON CONFLICT (slug) DO UPDATE SET
                title           = EXCLUDED.title,
                content         = EXCLUDED.content,
                excerpt         = EXCLUDED.excerpt,
                meta_description = EXCLUDED.meta_description,
                seo_title       = EXCLUDED.seo_title,
                tags            = EXCLUDED.tags,
                hero_image_url  = EXCLUDED.hero_image_url,
                hero_alt_text   = EXCLUDED.hero_alt_text,
                canonical_url   = EXCLUDED.canonical_url,
                og_tags         = EXCLUDED.og_tags,
                twitter_tags    = EXCLUDED.twitter_tags,
                json_ld_article = EXCLUDED.json_ld_article,
                json_ld_faq     = EXCLUDED.json_ld_faq,
                word_count      = EXCLUDED.word_count,
                keyword_density = EXCLUDED.keyword_density,
                published       = TRUE,
                updated_at      = EXCLUDED.updated_at
            RETURNING id
        """
        params = {
            "slug": slug,
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "meta_description": meta_desc,
            "seo_title": title,
            "tags": tags,
            "hero_image_url": hero_image_url,
            "hero_alt_text": hero_alt_text,
            "canonical_url": canonical_url,
            "og_tags": og_tags,
            "twitter_tags": twitter_tags,
            "json_ld_article": json_ld_article,
            "json_ld_faq": json_ld_faq,
            "word_count": word_count,
            "keyword_density": keyword_density,
            "date": now,
            "updated_at": now,
        }

        try:
            conn = psycopg2.connect(db_url)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    post_id = row[0] if row else None
            conn.close()
            logger.info(f"Upserted post id={post_id} slug='{slug}' to Cycolaps DB.")
            return post_id
        except Exception as exc:
            logger.error(f"Cycolaps DB upsert failed: {exc}")
            return None

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
