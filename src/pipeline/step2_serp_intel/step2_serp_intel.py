"""
Step 2: SERP Intelligence

Input:  dict — keyword clusters from Step 1
Output: dict — per-cluster SERP intel (recommended format, word count, difficulty, CPC proxy)

No LLM call — derives recommendations from the keyword data signals already in the clusters.
"""

import json
from typing import Dict, List

from src.pipeline.stage_result import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Keyword pattern → content format
_FORMAT_RULES: List[tuple] = [
    (["how to", "tutorial", "guide", "step by step", "steps to", "steps for"], "step-by-step guide"),
    (["best ", "top ", "alternatives", "vs ", " vs", "comparison", "compare"], "listicle / comparison"),
    ([" vs ", " versus "], "comparison article"),
    (["what is", "what are", "explained", "meaning", "definition", "overview", "introduction"], "explainer / pillar page"),
    (["buy", "price", "cost", "review", "reviews", "cheap", "affordable", "discount"], "buyer guide"),
]

_WORD_COUNT_MAP = {
    "LOW": (1500, 2000),
    "MEDIUM": (2500, 3500),
    "HIGH": (3500, 5000),
    "UNSPECIFIED": (2000, 3000),
}

_DIFFICULTY_MAP = {
    "LOW": 3,
    "MEDIUM": 6,
    "HIGH": 9,
    "UNSPECIFIED": 5,
}


class Step2SerpIntel:
    """Derives SERP intelligence from keyword cluster data — no external API calls."""

    def __init__(self, settings=None):
        self._settings = settings

    def run(self, keyword_clusters: dict) -> dict:
        """
        Args:
            keyword_clusters: Output of Step 1.

        Returns:
            {
                "clusters": [
                    {
                        "cluster_name": str,
                        "primary_keyword": str,
                        "content_format": str,
                        "content_angle": str,
                        "min_word_count": int,
                        "target_word_count": int,
                        "difficulty_score": int,
                        "competition": str,
                        "avg_monthly_searches": int,
                        "ranking_rationale": str,
                    }
                ],
                "primary_target": dict  # the highest-opportunity cluster to build around
            }
        """
        clusters = keyword_clusters.get("clusters", [])
        top_names = set(keyword_clusters.get("top_cluster_names", []))

        intel_clusters = []
        for cluster in clusters:
            primary_kw = cluster.get("primary_keyword", "")
            competition = cluster.get("competition", "MEDIUM")
            intent = cluster.get("intent", "informational")
            volume = cluster.get("avg_monthly_searches", 0)
            opp_score = cluster.get("opportunity_score", 50)

            content_format = _detect_format(primary_kw, intent)
            min_wc, target_wc = _word_counts(competition, opp_score)
            difficulty = _DIFFICULTY_MAP.get(competition, 5)
            content_angle = _derive_angle(primary_kw, intent, competition)
            rationale = _build_rationale(primary_kw, content_format, competition, intent)

            intel_clusters.append({
                "cluster_name": cluster.get("cluster_name", ""),
                "primary_keyword": primary_kw,
                "supporting_keywords": cluster.get("supporting_keywords", []),
                "intent": intent,
                "paa_questions": cluster.get("paa_questions", []),
                "opportunity_score": opp_score,
                "content_format": content_format,
                "content_angle": content_angle,
                "min_word_count": min_wc,
                "target_word_count": target_wc,
                "difficulty_score": difficulty,
                "competition": competition,
                "avg_monthly_searches": volume,
                "ranking_rationale": rationale,
                "is_top_target": cluster.get("cluster_name", "") in top_names,
            })

        # Sort: top targets first, then by opportunity score
        intel_clusters.sort(key=lambda c: (not c["is_top_target"], -c["opportunity_score"]))

        primary_target = intel_clusters[0] if intel_clusters else {}
        logger.info(
            f"Step 2 complete. Primary target: '{primary_target.get('primary_keyword', 'N/A')}' "
            f"→ {primary_target.get('content_format', 'N/A')}, "
            f"~{primary_target.get('target_word_count', 0)} words"
        )

        return StageResult(
            value={
                "clusters": intel_clusters,
                "primary_target": primary_target,
            },
            tokens_in=0,
            tokens_out=0,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_format(keyword: str, intent: str) -> str:
    kw_lower = keyword.lower()
    for patterns, fmt in _FORMAT_RULES:
        if any(p in kw_lower for p in patterns):
            return fmt
    # Fall back to intent
    if intent == "transactional" or intent == "commercial":
        return "buyer guide"
    if intent == "informational":
        return "explainer / pillar page"
    return "step-by-step guide"


def _word_counts(competition: str, opportunity_score: int) -> tuple:
    min_wc, base_target = _WORD_COUNT_MAP.get(competition, (2000, 3000))
    # High-opportunity topics need more depth
    if opportunity_score >= 75:
        target_wc = base_target + 500
    elif opportunity_score <= 25:
        target_wc = base_target - 300
    else:
        target_wc = base_target
    return min_wc, max(min_wc, target_wc)


def _derive_angle(keyword: str, intent: str, competition: str) -> str:
    kw_lower = keyword.lower()
    if "2024" in kw_lower or "2025" in kw_lower:
        return "most up-to-date guide for 2025"
    if competition == "HIGH":
        return "comprehensive, expert-level deep dive that beats shallow competitors"
    if intent == "informational":
        return "beginner-friendly yet technically accurate explainer with real examples"
    if intent == "commercial" or intent == "transactional":
        return "honest, data-backed buyer guide with clear recommendations"
    return "authoritative, well-structured resource that answers every related question"


def _build_rationale(keyword: str, content_format: str, competition: str, intent: str) -> str:
    return (
        f"'{keyword}' has {competition.lower()} competition with {intent} intent. "
        f"A {content_format} is the format Google rewards here because it directly matches "
        f"what searchers need. We'll need to outperform existing content on depth and structure."
    )
