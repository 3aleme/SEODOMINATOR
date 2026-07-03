"""
Step 4: Content Blueprint

Generates a detailed structured outline before writing begins — H1-H4 hierarchy,
key points per section, required data/stats, FAQ questions, and title candidates.

Input:  keyword_clusters (Step 1), serp_intel (Step 2), competitor_analysis (Step 3)
Output: structured JSON blueprint
"""

import json

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    content_blueprint_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Step5ContentBlueprint:
    """Generates a comprehensive content outline using SERP intel and competitor analysis."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.2)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, keyword_clusters: dict, serp_intel: dict, competitor_analysis: dict) -> dict:
        """
        Args:
            keyword_clusters:    Output of Step 1.
            serp_intel:          Output of Step 2.
            competitor_analysis: Output of Step 3.

        Returns:
            {
                "title_candidates": [{"title": str, "click_appeal_score": int, "rationale": str}],
                "recommended_title": str,
                "meta_description_hint": str,
                "outline": [
                    {
                        "level": "H1|H2|H3|H4",
                        "heading": str,
                        "key_points": [str],
                        "required_data": [str],
                        "estimated_words": int,
                    }
                ],
                "faq_section": [{"question": str, "answer_hint": str}],
                "target_word_count": int,
                "unique_angle": str,
                "primary_keyword": str,
                "supporting_keywords": [str],
                "paa_questions": [str],
            }
        """
        primary = serp_intel.get("primary_target", {})
        primary_keyword = primary.get("primary_keyword", "")
        if not primary_keyword:
            raise ValueError("Step 4 requires a primary_keyword from serp_intel")

        # Pull the matching cluster for supporting keywords + PAA
        clusters = keyword_clusters.get("clusters", [])
        matching_cluster = next(
            (c for c in clusters if c.get("primary_keyword") == primary_keyword),
            clusters[0] if clusters else {}
        )
        supporting_keywords = matching_cluster.get("supporting_keywords", [])
        paa_questions = matching_cluster.get("paa_questions", [])
        gap_analysis = competitor_analysis.get("gap_analysis", {})

        logger.info(f"Generating content blueprint for: '{primary_keyword}'")

        prompt = content_blueprint_prompt(
            primary_keyword=primary_keyword,
            supporting_keywords=supporting_keywords,
            paa_questions=paa_questions,
            serp_intel=primary,
            gap_analysis=gap_analysis,
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )

        raw = response.content[0].text.strip()
        try:
            blueprint = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"Blueprint JSON parse failed: {raw[:300]}")
            raise RuntimeError(f"Step 4 JSON parse failed: {exc}") from exc

        # Attach context fields needed by downstream steps
        blueprint["primary_keyword"] = primary_keyword
        blueprint["supporting_keywords"] = supporting_keywords
        blueprint["paa_questions"] = paa_questions

        total_words = sum(s.get("estimated_words", 0) for s in blueprint.get("outline", []))
        logger.info(
            f"Step 4 complete. Blueprint: {len(blueprint.get('outline', []))} sections, "
            f"~{total_words} estimated words. Title: '{blueprint.get('recommended_title', 'N/A')}'"
        )

        return StageResult(
            value=blueprint,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
