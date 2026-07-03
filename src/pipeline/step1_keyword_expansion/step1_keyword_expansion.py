"""
Step 1: Keyword Idea Fetch

Calls Google Ads Keyword Planner with seed keywords and returns raw keyword ideas
with search volume, competition, and trend data. No LLM involved.

Input:  List[str] — seed keywords from user
Output: dict — { seed_keywords, keyword_ideas: [{keyword, avg_monthly_searches,
                 competition, trend_score}], total_fetched }
"""

from dataclasses import dataclass
from typing import List, Sequence

from src.pipeline.stage_result import StageResult
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
    """Fetches raw keyword ideas from Google Ads Keyword Planner."""

    def __init__(self, settings=None):
        self._settings = settings

    def run(self, seed_keywords: List[str]) -> StageResult:
        """
        Args:
            seed_keywords: User-provided seed keywords.

        Returns:
            {
                "seed_keywords": [str],
                "keyword_ideas": [
                    {
                        "keyword": str,
                        "avg_monthly_searches": int,
                        "competition": str,
                        "trend_score": float,
                    }
                ],
                "total_fetched": int,
            }
        """
        logger.info(f"Fetching keyword ideas for {len(seed_keywords)} seeds via Google Ads API...")
        ideas = self._fetch_keyword_ideas(seed_keywords)
        logger.info(f"Fetched {len(ideas)} keyword ideas.")

        value = {
            "seed_keywords": seed_keywords,
            "keyword_ideas": [k.to_dict() for k in ideas],
            "total_fetched": len(ideas),
        }
        return StageResult(value=value, tokens_in=0, tokens_out=0)

    def _fetch_keyword_ideas(
        self,
        seed_keywords: Sequence[str],
        min_monthly_searches: int = 100,
        top_n: int = 50,
        language_code: str = "languageConstants/1000",
        geo_target: str = "geoTargetConstants/2840",
    ) -> List[KeywordIdea]:
        _rate_limiter.acquire()
        try:
            from google.ads.googleads.client import GoogleAdsClient
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
    if not monthly_volumes or avg == 0:
        return 0.0
    vols = [int(v.monthly_searches or 0) for v in monthly_volumes]
    if len(vols) < 2:
        return 50.0
    recent = sum(vols[-3:]) / min(3, len(vols))
    return min(100.0, round((recent / avg) * 50, 1))
