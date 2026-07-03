"""
Step 2: Keyword Clustering

Takes the raw keyword ideas from Step 1 and uses an LLM to classify intent,
cluster related keywords, score opportunities, and extract PAA questions.

Input:  dict — Step 1 output (seed_keywords, keyword_ideas, total_fetched)
Output: dict — keyword clusters with intent, volumes, competition, PAA questions
"""

import json

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    keyword_intent_classification_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Step2KeywordClustering:
    """Clusters raw keyword ideas into intent-classified opportunity groups via LLM."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.2)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, keyword_data: dict) -> StageResult:
        """
        Args:
            keyword_data: Output from Step 1 — { seed_keywords, keyword_ideas, total_fetched }

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
        seed_keywords = keyword_data.get("seed_keywords", [])
        keyword_ideas = keyword_data.get("keyword_ideas", [])
        total_fetched = keyword_data.get("total_fetched", len(keyword_ideas))

        logger.info(f"Clustering {len(keyword_ideas)} keyword ideas via LLM...")
        prompt = keyword_intent_classification_prompt(seed_keywords, keyword_ideas)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(prompt)]}],
        )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        raw = response.content[0].text.strip()

        try:
            clusters = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"LLM returned invalid JSON: {raw[:300]}")
            raise RuntimeError(f"Step 2 JSON parse failed: {exc}") from exc

        clusters["seed_keywords"] = seed_keywords
        clusters["total_ideas_fetched"] = total_fetched

        logger.info(
            f"Step 2 complete: {len(clusters.get('clusters', []))} clusters. "
            f"Top: {clusters.get('top_cluster_names', [])}"
        )
        return StageResult(value=clusters, tokens_in=tokens_in, tokens_out=tokens_out)
