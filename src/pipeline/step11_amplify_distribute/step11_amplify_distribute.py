"""
Step 11: Amplify & Distribute

Generates native-feeling social posts for Twitter, LinkedIn, Reddit, and Bluesky,
plus a newsletter snippet — all driven by the published article.

Input:  published_url (Step 10), seo_output (Step 6), keyword_clusters (Step 1)
Output: dict of platform → post text + newsletter_snippet
"""

import re

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    social_post_prompt,
    newsletter_snippet_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PLATFORMS = ["twitter", "linkedin", "reddit", "bluesky"]
_MAX_TOKENS = 512


class Step11AmplifyDistribute:
    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.2)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, published_url: str, seo_output: dict, keyword_clusters: dict) -> StageResult:
        """
        Args:
            published_url:    URL string returned by Step 10.
            seo_output:       Output of Step 6 (title, meta_description, tags, content).
            keyword_clusters: Output of Step 1 (for keyword list extraction).

        Returns:
            {
                "twitter": str,
                "linkedin": str,
                "reddit": str,
                "bluesky": str,
                "newsletter_snippet": str,
                "published_url": str,
            }
        """
        title = seo_output.get("seo_title", "")
        content = seo_output.get("optimized_content", "")
        excerpt = seo_output.get("meta_description", "") or _make_excerpt(content)
        keywords = _extract_keywords(seo_output, keyword_clusters)

        if not published_url:
            raise ValueError("Step 11 requires a published_url from Step 10")

        logger.info(f"Step 11: Generating social content for '{title}'")

        tokens_in = 0
        tokens_out = 0
        posts: dict = {}

        # ── Social posts ──────────────────────────────────────────────────────
        for platform in _PLATFORMS:
            logger.info(f"Generating {platform} post...")
            prompt = social_post_prompt(platform, title, published_url, keywords, excerpt)
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system=[make_cache_block(self._system_prompt)],
                    messages=[{"role": "user", "content": [make_text_block(prompt)]}],
                )
                posts[platform] = response.content[0].text.strip()
                tokens_in += response.usage.input_tokens
                tokens_out += response.usage.output_tokens
                logger.info(f"{platform} post generated ({len(posts[platform])} chars).")
            except Exception as exc:
                logger.warning(f"{platform} post generation failed: {exc}")
                posts[platform] = ""

        # ── Newsletter snippet ────────────────────────────────────────────────
        logger.info("Generating newsletter snippet...")
        try:
            nl_prompt = newsletter_snippet_prompt(title, content, published_url)
            nl_response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=[make_cache_block(self._system_prompt)],
                messages=[{"role": "user", "content": [make_text_block(nl_prompt)]}],
            )
            newsletter = nl_response.content[0].text.strip()
            tokens_in += nl_response.usage.input_tokens
            tokens_out += nl_response.usage.output_tokens
            logger.info(f"Newsletter snippet generated ({len(newsletter)} chars).")
        except Exception as exc:
            logger.warning(f"Newsletter snippet generation failed: {exc}")
            newsletter = ""

        covered = [p for p in _PLATFORMS if posts.get(p)]
        logger.info(f"Step 11 complete. Platforms covered: {covered}")

        return StageResult(
            value={
                **posts,
                "newsletter_snippet": newsletter,
                "published_url": published_url,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_keywords(seo_output: dict, keyword_clusters: dict) -> list:
    keywords = list(seo_output.get("seo_tags", []))
    if not keywords and keyword_clusters:
        for cluster in keyword_clusters.get("clusters", [])[:2]:
            kw = cluster.get("primary_keyword", "")
            if kw:
                keywords.append(kw)
            keywords.extend(cluster.get("supporting_keywords", [])[:3])
    return keywords[:10]


def _make_excerpt(content: str, max_chars: int = 300) -> str:
    text = re.sub(r"#+ ", "", content)
    text = re.sub(r"\*{1,2}|_{1,2}", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    return text[:cut] + "…"
