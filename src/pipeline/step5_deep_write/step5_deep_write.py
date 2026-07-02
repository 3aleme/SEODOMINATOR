"""
Step 5: Deep Write (Multi-Pass)

Three sequential LLM passes:
  Pass 1 — Expert Draft: write full article from blueprint
  Pass 2 — Quality Review: assess depth, accuracy, completeness
  Pass 3 — Revision: apply review feedback, produce final article

Input:  blueprint (Step 4), keyword_clusters (Step 1)
Output: final markdown article + word count + pass metadata
"""

import json

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    deep_write_pass1_prompt,
    deep_write_pass2_review_prompt,
    deep_write_pass3_revision_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Step5DeepWrite:
    """Three-pass article writing: Expert Draft → Quality Review → Revision."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = _cfg.get("model", self._client.model)
        self._temperature = _cfg.get("temperature", 0.7)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, blueprint: dict, keyword_clusters: dict) -> dict:
        """
        Args:
            blueprint:        Output of Step 4.
            keyword_clusters: Output of Step 1 (for supporting keywords).

        Returns:
            {
                "content": str,          # final markdown article
                "word_count": int,
                "primary_keyword": str,
                "supporting_keywords": [str],
                "recommended_title": str,
                "pass1_word_count": int,
                "review": dict,          # quality review output
                "passes_bar": bool,
            }
        """
        primary_keyword = blueprint.get("primary_keyword", "")
        supporting_keywords = blueprint.get("supporting_keywords", [])
        if not primary_keyword:
            raise ValueError("Step 5 requires primary_keyword in blueprint")

        tokens_in = 0
        tokens_out = 0

        # ── Pass 1: Expert Draft ──────────────────────────────────────────────
        logger.info(f"Pass 1: Writing expert draft for '{primary_keyword}'...")
        p1_prompt = deep_write_pass1_prompt(blueprint, primary_keyword, supporting_keywords)
        p1_response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(p1_prompt)]}],
        )
        draft = p1_response.content[0].text.strip()
        tokens_in += p1_response.usage.input_tokens
        tokens_out += p1_response.usage.output_tokens

        p1_word_count = len(draft.split())
        logger.info(f"Pass 1 complete. Draft: {p1_word_count} words.")

        # ── Pass 2: Quality Review ────────────────────────────────────────────
        logger.info("Pass 2: Running quality review...")
        p2_prompt = deep_write_pass2_review_prompt(draft, blueprint, primary_keyword)
        p2_response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(p2_prompt)]}],
        )
        raw_review = p2_response.content[0].text.strip()
        tokens_in += p2_response.usage.input_tokens
        tokens_out += p2_response.usage.output_tokens

        try:
            review = json.loads(raw_review)
        except json.JSONDecodeError:
            logger.warning("Review JSON parse failed — treating draft as passing.")
            review = {"passes_bar": True, "revision_instructions": [], "overall_quality": 7}

        passes_bar = review.get("passes_bar", True)
        quality = review.get("overall_quality", 7)
        logger.info(f"Pass 2 complete. Quality: {quality}/10. Passes bar: {passes_bar}")

        # ── Pass 3: Revision ──────────────────────────────────────────────────
        revision_needed = (
            not passes_bar
            or quality < 8
            or review.get("revision_instructions")
            or review.get("missing_sections")
        )

        if revision_needed:
            logger.info("Pass 3: Applying revisions...")
            p3_prompt = deep_write_pass3_revision_prompt(draft, review)
            p3_response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=[make_cache_block(self._system_prompt)],
                messages=[{"role": "user", "content": [make_text_block(p3_prompt)]}],
            )
            final_article = p3_response.content[0].text.strip()
            tokens_in += p3_response.usage.input_tokens
            tokens_out += p3_response.usage.output_tokens
            logger.info("Pass 3 complete.")
        else:
            logger.info("Pass 3 skipped — draft already meets quality bar.")
            final_article = draft

        word_count = len(final_article.split())
        logger.info(f"Step 5 complete. Final article: {word_count} words.")

        return StageResult(
            value={
                "content": final_article,
                "word_count": word_count,
                "primary_keyword": primary_keyword,
                "supporting_keywords": supporting_keywords,
                "recommended_title": blueprint.get("recommended_title", ""),
                "pass1_word_count": p1_word_count,
                "review": review,
                "passes_bar": passes_bar or not revision_needed,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
