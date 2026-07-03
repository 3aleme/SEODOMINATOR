"""URL-based keyword suggestion — fetches a competitor page and returns 10 target keywords."""

import json

import httpx
import trafilatura

from src.provider import get_llm_client
from src.utils.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEODominator/1.0)"}


def suggest_from_url(url: str, settings=None) -> list:
    """Fetch a URL, extract its content, and return 10 keyword suggestions via LLM."""
    logger.info(f"Fetching URL for keyword suggestions: {url}")
    try:
        resp = httpx.get(url, timeout=20.0, follow_redirects=True, headers=_HEADERS)
        resp.raise_for_status()
    except Exception as exc:
        raise ValueError(f"Could not fetch URL: {exc}") from exc

    text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
    if not text or len(text.split()) < 50:
        raise ValueError("Could not extract enough content from this URL.")

    excerpt = text[:3500]
    logger.info(f"Extracted {len(text.split())} words. Sending to LLM for keyword analysis...")

    client = get_llm_client(settings)
    prompt = (
        f"URL: {url}\n\n"
        f"Page content:\n{excerpt}\n\n"
        "You are an SEO strategist analyzing a competitor page.\n"
        "Suggest exactly 10 keywords we should target to compete with this page in search results.\n\n"
        "Return a smart mix of:\n"
        "- The primary keyword this page targets\n"
        "- Long-tail variations (3-5 word phrases, more specific)\n"
        "- Semantic variations (different phrasings for the same search intent)\n"
        "- Adjacent keywords the same audience also searches for\n\n"
        "Rules:\n"
        "- All keywords must be realistic search queries people actually type\n"
        "- Prefer keywords with commercial or informational intent\n"
        "- No brand names, no URLs, no generic filler like 'best tips'\n\n"
        'Return ONLY a JSON array of exactly 10 strings. Example: ["keyword one", "keyword two", ...]\n'
        "No explanation, no markdown, just the JSON array."
    )

    response = client.messages.create(
        model=client.model,
        max_tokens=512,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    )

    raw = response.content[0].text.strip()
    try:
        if "[" in raw:
            raw = raw[raw.index("[") : raw.rindex("]") + 1]
        keywords = json.loads(raw)
        if not isinstance(keywords, list):
            raise ValueError("LLM did not return a list")
        logger.info(f"Suggested {len(keywords)} keywords from URL.")
        return keywords[:10]
    except Exception as exc:
        logger.error(f"Keyword suggestion parse failed: {raw[:200]}")
        raise ValueError(f"Could not parse keyword suggestions: {exc}") from exc
