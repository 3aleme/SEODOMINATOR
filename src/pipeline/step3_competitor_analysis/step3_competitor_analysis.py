"""
Step 3: Competitor Analysis

Fetches top articles for the primary keyword and deeply analyzes them with an LLM
to produce a content gap matrix and beat strategy.

Input:  keyword_clusters (Step 1), serp_intel (Step 2)
Output: competitor matrix + content gaps + beat strategy per primary cluster
"""

import json
import time
from typing import List, Optional

import httpx
import trafilatura

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    competitor_article_analysis_prompt,
    content_gap_analysis_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

_scrape_limiter = RateLimiter(calls=3, period=5.0)  # 3 requests per 5 seconds


class Step3CompetitorAnalysis:
    """Fetches and LLM-analyzes top competitor articles for the primary keyword."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.2)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, keyword_clusters: dict, serp_intel: dict) -> dict:
        """
        Args:
            keyword_clusters: Output of Step 1.
            serp_intel:       Output of Step 2.

        Returns:
            {
                "primary_keyword": str,
                "competitor_articles": [
                    {
                        "url": str,
                        "word_count": int,
                        "heading_structure": [str],
                        "topics_covered": [str],
                        "strengths": [str],
                        "weaknesses": [str],
                        "missing_topics": [str],
                        "content_depth": str,
                        "overall_score": int,
                    }
                ],
                "gap_analysis": {
                    "universal_gaps": [str],
                    "outdated_info": [str],
                    "beat_strategy": str,
                    "unique_angles": [str],
                    "must_include_sections": [str],
                    "differentiators": [str],
                },
                "total_tokens_in": int,
                "total_tokens_out": int,
            }
        """
        primary = serp_intel.get("primary_target", {})
        keyword = primary.get("primary_keyword", "")
        if not keyword:
            raise ValueError("Step 3 requires a primary_keyword from serp_intel")

        logger.info(f"Fetching competitor articles for: '{keyword}'")
        urls = self._discover_urls(keyword)
        logger.info(f"Found {len(urls)} candidate URLs. Scraping content...")

        articles_data = []
        tokens_in = 0
        tokens_out = 0

        for url in urls[:8]:  # analyze up to 8 competitors
            content = self._scrape(url)
            if not content or len(content.split()) < 200:
                logger.warning(f"Skipping {url} — insufficient content")
                continue

            try:
                analysis, t_in, t_out = self._analyze_article(keyword, content, url)
                analysis["url"] = url
                articles_data.append(analysis)
                tokens_in += t_in
                tokens_out += t_out
                logger.info(f"Analyzed: {url} (score: {analysis.get('overall_score', 'N/A')})")
            except Exception as exc:
                logger.warning(f"Failed to analyze {url}: {exc}")

        if not articles_data:
            raise RuntimeError("No competitor articles could be scraped and analyzed")

        logger.info(f"Running content gap synthesis across {len(articles_data)} articles...")
        gap_analysis, t_in, t_out = self._synthesize_gaps(keyword, articles_data)
        tokens_in += t_in
        tokens_out += t_out

        result = {
            "primary_keyword": keyword,
            "competitor_articles": articles_data,
            "gap_analysis": gap_analysis,
            "total_tokens_in": tokens_in,
            "total_tokens_out": tokens_out,
        }

        logger.info(
            f"Step 3 complete. {len(articles_data)} competitors analyzed. "
            f"Beat strategy: {gap_analysis.get('beat_strategy', '')[:80]}..."
        )
        return StageResult(value=result, tokens_in=tokens_in, tokens_out=tokens_out)

    def _discover_urls(self, keyword: str) -> List[str]:
        """Discover competitor URLs via NewsAPI or SerpAPI."""
        urls = []

        if self._settings and self._settings.newsapi_key:
            urls.extend(self._newsapi_urls(keyword))

        if len(urls) < 5 and self._settings and self._settings.serpapi_key:
            urls.extend(self._serpapi_urls(keyword))

        # Deduplicate while preserving order
        seen = set()
        return [u for u in urls if not (u in seen or seen.add(u))]

    def _newsapi_urls(self, keyword: str) -> List[str]:
        try:
            resp = httpx.get(
                "https://newsapi.org/v2/everything",
                params={"q": keyword, "language": "en", "pageSize": 10, "sortBy": "relevancy"},
                headers={"X-Api-Key": self._settings.newsapi_key},
                timeout=15.0,
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [a["url"] for a in articles if a.get("url")]
        except Exception as exc:
            logger.warning(f"NewsAPI failed: {exc}")
            return []

    def _serpapi_urls(self, keyword: str) -> List[str]:
        try:
            resp = httpx.get(
                "https://serpapi.com/search",
                params={"q": keyword, "api_key": self._settings.serpapi_key, "num": 10, "hl": "en", "gl": "us"},
                timeout=15.0,
            )
            resp.raise_for_status()
            results = resp.json().get("organic_results", [])
            return [r["link"] for r in results if r.get("link")]
        except Exception as exc:
            logger.warning(f"SerpAPI failed: {exc}")
            return []

    def _scrape(self, url: str) -> Optional[str]:
        _scrape_limiter.acquire()
        try:
            resp = httpx.get(url, timeout=20.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SEODominator/1.0)"
            })
            resp.raise_for_status()
            return trafilatura.extract(resp.text, include_comments=False, include_tables=True)
        except Exception as exc:
            logger.warning(f"Scrape failed for {url}: {exc}")
            return None

    def _analyze_article(self, keyword: str, content: str, url: str) -> tuple:
        prompt = competitor_article_analysis_prompt(keyword, content, url)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )
        raw = response.content[0].text.strip()
        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            analysis = {"raw_analysis": raw, "overall_score": 5}
        return analysis, response.usage.input_tokens, response.usage.output_tokens

    def _synthesize_gaps(self, keyword: str, analyses: List[dict]) -> tuple:
        prompt = content_gap_analysis_prompt(keyword, analyses)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )
        raw = response.content[0].text.strip()
        try:
            gap = json.loads(raw)
        except json.JSONDecodeError:
            gap = {"beat_strategy": raw, "universal_gaps": [], "must_include_sections": []}
        return gap, response.usage.input_tokens, response.usage.output_tokens
