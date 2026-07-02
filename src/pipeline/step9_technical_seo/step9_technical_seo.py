"""
Step 9: Technical SEO

Pure-logic stage — no LLM calls.
Builds canonical URL, OG/Twitter meta tags, XML sitemap entry,
validates heading hierarchy, and assembles the full JSON-LD payload.

Input:  linked_article (Step 8), seo_output (Step 6)
Output: technical SEO metadata package ready for Step 10
"""

import re
from datetime import datetime, timezone

from src.pipeline.stage_result import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SITE_BASE = "https://cycolaps.com"
_BLOG_BASE = f"{_SITE_BASE}/blog"


class Step9TechnicalSeo:
    def __init__(self, settings=None):
        self._settings = settings

    def run(self, linked_article: dict, seo_output: dict) -> StageResult:
        """
        Args:
            linked_article: Output of Step 8.
            seo_output:     Output of Step 6 (for article_schema).

        Returns:
            {
                "canonical_url": str,
                "og_tags": dict,
                "twitter_tags": dict,
                "sitemap_entry": str,       # XML <url> block
                "heading_hierarchy_valid": bool,
                "heading_issues": [str],
                "json_ld_article": dict,    # Article schema
                "json_ld_faq": dict,        # FAQPage schema (empty dict if no FAQs)
                "robots_meta": str,
                "slug": str,
            }
        """
        slug = linked_article.get("new_article_slug", "")
        title = linked_article.get("seo_title", "")
        description = linked_article.get("meta_description", "")
        hero_image_url = linked_article.get("hero_image_url", "")
        content = linked_article.get("content", "")
        faq_schema = linked_article.get("faq_schema") or seo_output.get("faq_schema", [])
        article_schema = seo_output.get("article_schema", {})

        if not slug:
            raise ValueError("Step 9 requires new_article_slug from Step 8 output")

        canonical_url = f"{_BLOG_BASE}/{slug}"
        logger.info(f"Step 9: Building technical SEO package for '{slug}'")

        og_tags = _build_og_tags(title, description, hero_image_url, canonical_url)
        twitter_tags = _build_twitter_tags(title, description, hero_image_url)
        sitemap_entry = _build_sitemap_entry(canonical_url)
        heading_valid, heading_issues = _validate_heading_hierarchy(content)

        if heading_issues:
            for issue in heading_issues:
                logger.warning(f"Heading issue: {issue}")
        else:
            logger.info("Heading hierarchy valid.")

        json_ld_article = _build_article_json_ld(
            title, description, canonical_url, hero_image_url, article_schema
        )
        json_ld_faq = _build_faq_json_ld(faq_schema)

        logger.info(
            f"Step 9 complete. canonical={canonical_url} "
            f"heading_valid={heading_valid} faq_entities={len(faq_schema)}"
        )

        return StageResult(
            value={
                "canonical_url": canonical_url,
                "og_tags": og_tags,
                "twitter_tags": twitter_tags,
                "sitemap_entry": sitemap_entry,
                "heading_hierarchy_valid": heading_valid,
                "heading_issues": heading_issues,
                "json_ld_article": json_ld_article,
                "json_ld_faq": json_ld_faq,
                "robots_meta": "index, follow",
                "slug": slug,
            },
            tokens_in=0,
            tokens_out=0,
        )


# ── Builders ──────────────────────────────────────────────────────────────────

def _build_og_tags(title: str, description: str, image_url: str, canonical_url: str) -> dict:
    return {
        "og:type": "article",
        "og:title": title,
        "og:description": description,
        "og:url": canonical_url,
        "og:image": image_url,
        "og:site_name": "Cycolaps",
    }


def _build_twitter_tags(title: str, description: str, image_url: str) -> dict:
    return {
        "twitter:card": "summary_large_image",
        "twitter:title": title,
        "twitter:description": description,
        "twitter:image": image_url,
    }


def _build_sitemap_entry(url: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"<url>\n"
        f"  <loc>{url}</loc>\n"
        f"  <lastmod>{today}</lastmod>\n"
        f"  <changefreq>monthly</changefreq>\n"
        f"  <priority>0.8</priority>\n"
        f"</url>"
    )


def _validate_heading_hierarchy(content: str) -> tuple[bool, list[str]]:
    """Verify no H1 skips (H2→H4), no multiple H1s, article starts with H1."""
    headings = re.findall(r"^(#{1,6})\s+.+", content, re.MULTILINE)
    if not headings:
        return True, []

    levels = [len(h) for h in headings]
    issues: list[str] = []

    if levels[0] != 1:
        issues.append(f"Article does not start with H1 (first heading is H{levels[0]})")

    h1_count = levels.count(1)
    if h1_count > 1:
        issues.append(f"Multiple H1 headings found ({h1_count} total)")

    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            issues.append(
                f"Heading jump: H{levels[i-1]} → H{levels[i]} at heading #{i + 1}"
            )

    return len(issues) == 0, issues


def _build_article_json_ld(
    title: str, description: str, url: str, image_url: str, article_schema: dict
) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article_schema.get("headline", title),
        "description": article_schema.get("description", description),
        "url": url,
        "image": image_url,
        "publisher": {
            "@type": "Organization",
            "name": "Cycolaps",
            "url": _SITE_BASE,
        },
        "datePublished": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "keywords": article_schema.get("keywords", []),
    }


def _build_faq_json_ld(faq_schema: list) -> dict:
    if not faq_schema:
        return {}
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item.get("answer", ""),
                },
            }
            for item in faq_schema
            if item.get("question")
        ],
    }
