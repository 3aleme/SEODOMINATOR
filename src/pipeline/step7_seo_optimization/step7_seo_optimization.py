"""
Step 6: SEO Optimization

Natural keyword integration, meta description, semantic tags, FAQ schema,
Article schema, and JSON-LD structured data.

Input:  article dict (Step 5), keyword_clusters (Step 1)
Output: SEO-optimized article + title + meta + tags + JSON-LD
"""

import json
import re

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    seo_optimization_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Step7SeoOptimization:
    """Optimizes the article for SEO: keyword density, meta, tags, and structured data."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.2)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, article: dict, keyword_clusters: dict) -> dict:
        """
        Args:
            article:          Output of Step 5.
            keyword_clusters: Output of Step 1.

        Returns:
            {
                "optimized_content": str,
                "seo_title": str,
                "meta_description": str,
                "seo_tags": [str],
                "keyword_density": float,
                "word_count": int,
                "json_ld": {
                    "article": dict,
                    "faq": dict,
                },
                "faq_schema": [{"question": str, "answer": str}],
                "primary_keyword": str,
                "supporting_keywords": [str],
                "recommended_title": str,
            }
        """
        content = article.get("content", "")
        primary_keyword = article.get("primary_keyword", "")
        supporting_keywords = article.get("supporting_keywords", [])
        if not content or not primary_keyword:
            raise ValueError("Step 6 requires content and primary_keyword from Step 5")

        logger.info(f"Running SEO optimization for '{primary_keyword}'...")

        prompt = seo_optimization_prompt(content, primary_keyword, supporting_keywords)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )

        raw = response.content[0].text.strip()
        try:
            seo = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"SEO JSON parse failed: {raw[:300]}")
            raise RuntimeError(f"Step 6 JSON parse failed: {exc}") from exc

        optimized_content = seo.get("optimized_content", content)
        seo_title = seo.get("seo_title", article.get("recommended_title", ""))
        meta_description = seo.get("meta_description", "")
        seo_tags = seo.get("seo_tags", [])
        faq_schema = seo.get("faq_schema", [])
        article_schema_data = seo.get("article_schema", {})

        # Compute keyword density
        word_count = len(optimized_content.split())
        kw_count = _count_keyword(optimized_content, primary_keyword)
        keyword_density = round((kw_count / word_count) * 100, 2) if word_count else 0.0
        seo["keyword_density"] = keyword_density

        if keyword_density < 0.5:
            logger.warning(f"Keyword density low: {keyword_density}% for '{primary_keyword}'")
        elif keyword_density > 2.5:
            logger.warning(f"Keyword density high (risk of stuffing): {keyword_density}%")
        else:
            logger.info(f"Keyword density: {keyword_density}% ✓")

        json_ld = _build_json_ld(seo_title, meta_description, primary_keyword, faq_schema, article_schema_data)

        result = {
            "optimized_content": optimized_content,
            "seo_title": seo_title,
            "meta_description": meta_description,
            "seo_tags": seo_tags,
            "keyword_density": keyword_density,
            "word_count": word_count,
            "faq_schema": faq_schema,
            "json_ld": json_ld,
            "primary_keyword": primary_keyword,
            "supporting_keywords": supporting_keywords,
            "recommended_title": article.get("recommended_title", seo_title),
        }

        logger.info(
            f"Step 6 complete. Title: '{seo_title}' | "
            f"Meta: {len(meta_description)} chars | "
            f"Tags: {len(seo_tags)} | KD: {keyword_density}%"
        )
        return StageResult(
            value=result,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _count_keyword(text: str, keyword: str) -> int:
    """Count non-overlapping occurrences of keyword in text (case-insensitive)."""
    return len(re.findall(re.escape(keyword.lower()), text.lower()))


def _build_json_ld(
    title: str,
    description: str,
    keyword: str,
    faq_schema: list,
    article_schema_data: dict,
) -> dict:
    article_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "keywords": article_schema_data.get("keywords", [keyword]),
        "author": {"@type": "Organization", "name": "Cycolaps"},
        "publisher": {
            "@type": "Organization",
            "name": "Cycolaps",
            "url": "https://cycolaps.com",
        },
    }

    result = {"article": article_ld}

    if faq_schema:
        result["faq"] = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item.get("answer", ""),
                    },
                }
                for item in faq_schema
            ],
        }

    return result
