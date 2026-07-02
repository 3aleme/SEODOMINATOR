"""
Step 1: Keyword Expansion

Takes seed keywords → Google Ads API for keyword ideas → LLM classifies intent,
clusters related keywords, scores opportunities, extracts PAA questions.

Input:  List[str] — seed keywords from user
Output: dict — keyword clusters with intent, volumes, competition, PAA questions
"""

import json
from dataclasses import dataclass, field
from typing import List, Sequence

from google.ads.googleads.client import GoogleAdsClient

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    keyword_intent_classification_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

_rate_limiter = RateLimiter(calls=5, period=60.0)


@dataclass
class KeywordIdea:
    keyword: str
    avg_monthly_searches: int
    competition: str        # LOW | MEDIUM | HIGH | UNSPECIFIED
    trend_score: float      # 0-100 upward trend score

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "avg_monthly_searches": self.avg_monthly_searches,
            "competition": self.competition,
            "trend_score": self.trend_score,
        }


class Step1KeywordExpansion:
    """Expands seed keywords into ranked, intent-classified clusters."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)

    def run(self, seed_keywords: List[str]) -> dict:
        """
        Args:
            seed_keywords: User-provided seed keywords.

        Returns:
            {
                "clusters": [
                    {
                        "cluster_name": str,
                        "primary_keyword": str,
                        "supporting_keywords": [str],
                        "intent": str,
                        "opportunity_score": int,
                        "avg_monthly_searches": int,
                        "competition": str,
                        "paa_questions": [str],
                    }
                ],
                "top_cluster_names": [str],
                "seed_keywords": [str],
                "total_ideas_fetched": int,
            }
        """
        logger.info(f"Expanding {len(seed_keywords)} seed keywords via Google Ads API...")
        ideas = self._fetch_keyword_ideas(seed_keywords)
        logger.info(f"Fetched {len(ideas)} keyword ideas. Running LLM cluster analysis...")

        ideas_dicts = [k.to_dict() for k in ideas]
        prompt = keyword_intent_classification_prompt(seed_keywords, ideas_dicts)

        response = self._client.messages.create(
            model=self._client.model,
            max_tokens=4096,
            system=[make_cache_block(SEO_EXPERT_SYSTEM)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        raw = response.content[0].text.strip()

        try:
            clusters = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"LLM returned invalid JSON: {raw[:300]}")
            raise RuntimeError(f"Step 1 JSON parse failed: {exc}") from exc

        clusters["seed_keywords"] = seed_keywords
        clusters["total_ideas_fetched"] = len(ideas)

        logger.info(
            f"Step 1 complete: {len(clusters.get('clusters', []))} clusters found. "
            f"Top: {clusters.get('top_cluster_names', [])}"
        )
        return StageResult(value=clusters, tokens_in=tokens_in, tokens_out=tokens_out)

    def _fetch_keyword_ideas(
        self,
        seed_keywords: Sequence[str],
        min_monthly_searches: int = 100,
        top_n: int = 50,
        language_code: str = "languageConstants/1000",
        geo_target: str = "geoTargetConstants/2840",
    ) -> List[KeywordIdea]:
        """Call Google Ads Keyword Planner and return raw ideas."""
        _rate_limiter.acquire()
        try:
            ads_client = GoogleAdsClient.load_from_dict(self._settings.google_ads_config())
            svc = ads_client.get_service("KeywordPlanIdeaService")
            request = ads_client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self._settings.google_ads_customer_id
            request.keyword_seed.keywords.extend(seed_keywords)
            request.include_adult_keywords = False
            request.language = language_code
            request.geo_target_constants.append(geo_target)

            ideas = svc.generate_keyword_ideas(request=request)
            results = self._parse_ideas(ideas, min_monthly_searches)
            results.sort(key=lambda r: r.avg_monthly_searches, reverse=True)
            return results[:top_n]
        except Exception as exc:
            raise RuntimeError(f"Google Ads keyword fetch failed: {exc}") from exc

    @staticmethod
    def _parse_ideas(ideas, min_monthly_searches: int) -> List[KeywordIdea]:
        results: List[KeywordIdea] = []
        for idea in ideas:
            monthly = int(idea.keyword_idea_metrics.avg_monthly_searches or 0)
            if monthly < min_monthly_searches:
                continue
            competition = idea.keyword_idea_metrics.competition.name
            vols = idea.keyword_idea_metrics.monthly_search_volumes
            trend = _trend_score(vols, monthly)
            results.append(KeywordIdea(
                keyword=idea.text,
                avg_monthly_searches=monthly,
                competition=competition,
                trend_score=trend,
            ))
        return results


def _trend_score(monthly_volumes, avg: int) -> float:
    """Upward-trend score: ratio of recent 3 months to historical average (0-100)."""
    if not monthly_volumes or avg == 0:
        return 0.0
    vols = [int(v.monthly_searches or 0) for v in monthly_volumes]
    if len(vols) < 2:
        return 50.0
    recent = sum(vols[-3:]) / min(3, len(vols))
    return min(100.0, round((recent / avg) * 50, 1))
