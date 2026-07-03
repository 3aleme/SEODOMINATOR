"""
Step 7: Media Generation

Generates a hero image + 1-2 in-article images using the multi-provider cascade:
  xAI Aurora → Gemini Imagen → DALL-E 3 → Stability AI

Uploads all images to Vercel Blob and returns URLs + alt text.

Input:  seo_output (Step 6)
Output: image URLs, alt text, local paths
"""

import base64
import re
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from src.pipeline.prompts import (
    SEO_EXPERT_SYSTEM,
    hero_image_prompt_gen,
    in_article_image_prompt_gen,
    image_alt_text_prompt,
    make_cache_block,
    make_text_block,
)
from src.pipeline.stage_result import StageResult
from src.provider import get_llm_client
from src.utils.agent_config import load_agent_config, resolve_model
from src.utils.logger import get_logger

logger = get_logger(__name__)

_OUTPUT_DIR = Path("outputs/images")

_XAI_IMAGES_URL   = "https://api.x.ai/v1/images/generations"
_DALLE_URL         = "https://api.openai.com/v1/images/generations"
_STABILITY_URL     = "https://api.stability.ai/v2beta/stable-image/generate/core"
_GEMINI_IMG_URL    = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict"
_BLOB_UPLOAD_URL   = "https://blob.vercel-storage.com/blog/{filename}"


class Step8MediaGeneration:
    """Generates hero + in-article images and uploads them to Vercel Blob."""

    def __init__(self, settings=None):
        self._settings = settings
        self._client = get_llm_client(settings)
        _cfg = load_agent_config(__file__)
        self._model = resolve_model(_cfg, self._client)
        self._temperature = _cfg.get("temperature", 0.7)
        self._max_tokens = _cfg.get("max_tokens", 4096)
        self._system_prompt = _cfg.get("system_prompt", SEO_EXPERT_SYSTEM)

    def run(self, seo_output: dict) -> dict:
        """
        Args:
            seo_output: Output of Step 6.

        Returns:
            {
                "hero_image_url": str,
                "hero_alt_text": str,
                "in_article_images": [{"url": str, "alt_text": str, "section": str}],
                "image_urls": [str],          # all URLs in order: [hero, ...in-article]
                "local_paths": [str],
            }
        """
        title = seo_output.get("seo_title", "")
        keyword = seo_output.get("primary_keyword", "")
        content = seo_output.get("optimized_content", "")
        keywords = [keyword] + seo_output.get("supporting_keywords", [])[:3]

        if not content or not keyword:
            raise ValueError("Step 7 requires optimized_content and primary_keyword")

        tokens_in = 0
        tokens_out = 0
        local_paths = []
        image_urls = []

        # ── Hero image ────────────────────────────────────────────────────────
        logger.info("Generating hero image...")
        hero_prompt, t_in, t_out = self._craft_prompt(
            hero_image_prompt_gen(title, keyword, content[:600])
        )
        tokens_in += t_in
        tokens_out += t_out

        hero_bytes = self._generate(hero_prompt)
        hero_filename = f"hero_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
        hero_local = self._save(hero_bytes, hero_filename)
        local_paths.append(hero_local)

        hero_url = self._upload(hero_local, hero_filename)
        image_urls.append(hero_url)

        hero_alt, t_in, t_out = self._craft_prompt(
            image_alt_text_prompt(hero_prompt, title, keywords)
        )
        tokens_in += t_in
        tokens_out += t_out
        logger.info(f"Hero image: {hero_url}")

        # ── In-article images (up to 2) ───────────────────────────────────────
        in_article = []
        sections = _extract_h2_sections(content)[:2]

        for section_heading, section_body in sections:
            logger.info(f"Generating in-article image for section: '{section_heading}'")
            ia_prompt, t_in, t_out = self._craft_prompt(
                in_article_image_prompt_gen(section_heading, section_body, keyword)
            )
            tokens_in += t_in
            tokens_out += t_out

            try:
                ia_bytes = self._generate(ia_prompt)
                ia_filename = f"article_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
                ia_local = self._save(ia_bytes, ia_filename)
                local_paths.append(ia_local)

                ia_url = self._upload(ia_local, ia_filename)
                image_urls.append(ia_url)

                ia_alt, t_in, t_out = self._craft_prompt(
                    image_alt_text_prompt(ia_prompt, section_heading, keywords)
                )
                tokens_in += t_in
                tokens_out += t_out

                in_article.append({
                    "url": ia_url,
                    "alt_text": ia_alt.strip(),
                    "section": section_heading,
                })
                logger.info(f"In-article image: {ia_url}")
            except Exception as exc:
                logger.warning(f"In-article image failed for '{section_heading}': {exc}")

        result = {
            "hero_image_url": hero_url,
            "hero_alt_text": hero_alt.strip(),
            "in_article_images": in_article,
            "image_urls": image_urls,
            "local_paths": local_paths,
        }

        logger.info(f"Step 7 complete. {len(image_urls)} image(s) uploaded.")
        return StageResult(value=result, tokens_in=tokens_in, tokens_out=tokens_out)

    # ── Prompt crafting ────────────────────────────────────────────────────────

    def _craft_prompt(self, user_prompt: str) -> Tuple[str, int, int]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=[make_cache_block(self._system_prompt)],
            messages=[{"role": "user", "content": [make_text_block(user_prompt)]}],
        )
        return (
            response.content[0].text.strip(),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

    # ── Image generation cascade ───────────────────────────────────────────────

    def _generate(self, prompt: str) -> bytes:
        s = self._settings
        if s and s.xai_api_key:
            return self._gen_xai(prompt)
        if s and s.gemini_api_key:
            return self._gen_gemini(prompt)
        if s and s.openai_api_key:
            return self._gen_dalle(prompt)
        if s and s.stability_api_key:
            return self._gen_stability(prompt)
        raise RuntimeError(
            "No image generation key configured. Set XAI_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, or STABILITY_API_KEY."
        )

    def _gen_xai(self, prompt: str) -> bytes:
        resp = httpx.post(
            _XAI_IMAGES_URL,
            headers={"Authorization": f"Bearer {self._settings.xai_api_key}", "Content-Type": "application/json"},
            json={"model": "grok-2-image", "prompt": prompt, "n": 1, "response_format": "url"},
            timeout=60.0,
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        return httpx.get(url, timeout=30.0).content

    def _gen_gemini(self, prompt: str) -> bytes:
        url = f"{_GEMINI_IMG_URL}?key={self._settings.gemini_api_key}"
        resp = httpx.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            b64 = data["predictions"][0]["bytesBase64Encoded"]
            return base64.b64decode(b64)
        except Exception as exc:
            raise RuntimeError(f"Gemini response parse failed: {data}") from exc

    def _gen_dalle(self, prompt: str) -> bytes:
        resp = httpx.post(
            _DALLE_URL,
            headers={"Authorization": f"Bearer {self._settings.openai_api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1792x1024", "quality": "standard", "response_format": "url"},
            timeout=60.0,
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        return httpx.get(url, timeout=30.0).content

    def _gen_stability(self, prompt: str) -> bytes:
        resp = httpx.post(
            _STABILITY_URL,
            headers={"Authorization": f"Bearer {self._settings.stability_api_key}", "Accept": "image/*"},
            data={"prompt": prompt, "aspect_ratio": "16:9", "output_format": "png"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.content

    # ── Save + upload ──────────────────────────────────────────────────────────

    def _save(self, image_bytes: bytes, filename: str) -> str:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = _OUTPUT_DIR / filename
        path.write_bytes(image_bytes)
        return str(path.resolve())

    def _upload(self, local_path: str, filename: str) -> str:
        token = self._settings.blob_read_write_token if self._settings else ""
        if not token:
            logger.warning("BLOB_READ_WRITE_TOKEN not set — skipping upload, returning local path")
            return f"/outputs/images/{filename}"

        src = Path(local_path)
        if not src.exists():
            return f"/blog/ai.png"

        upload_url = _BLOB_UPLOAD_URL.format(filename=filename)
        resp = httpx.put(
            upload_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/png",
                "x-add-random-suffix": "0",
            },
            content=src.read_bytes(),
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["url"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_h2_sections(content: str) -> List[Tuple[str, str]]:
    """Extract (heading, body_text) pairs for H2 sections from markdown."""
    sections = []
    parts = re.split(r'\n## ', content)
    for part in parts[1:]:  # skip content before first H2
        lines = part.split('\n')
        heading = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()
        if body:
            sections.append((heading, body))
    return sections
