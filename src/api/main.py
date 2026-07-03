"""SEODOMINATOR FastAPI dashboard — keyword input UI and step execution endpoints."""

import asyncio
import json
import traceback
from pathlib import Path
from typing import List

_CHECKPOINT_DIR = Path("outputs")



from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config.settings import load_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="SEODOMINATOR", docs_url="/docs")
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


# ── Checkpoint helper ─────────────────────────────────────────────────────────

def _save_checkpoint(run_label: str, step_name: str, value) -> None:
    try:
        path = _CHECKPOINT_DIR / run_label / f"{step_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(value, f, default=str, indent=2)
    except Exception as exc:
        logger.warning(f"Checkpoint save failed for {step_name}: {exc}")


# ── Request / Response models ─────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    url: str

class Step1Request(BaseModel):
    keywords: List[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(_TEMPLATE_PATH.read_text())


@app.post("/api/suggest-keywords")
async def suggest_keywords(body: SuggestRequest):
    """Fetch a competitor URL and return 10 suggested keywords via LLM."""
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        from src.pipeline.step1_keyword_expansion.keyword_suggester import suggest_from_url
        settings = load_settings()
        loop = asyncio.get_event_loop()
        keywords = await loop.run_in_executor(None, suggest_from_url, body.url, settings)
        return {"keywords": keywords}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"suggest-keywords failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step1")
async def run_step1(body: Step1Request):
    """Run Step 1: Keyword Expansion for the given seed keywords."""
    if not body.keywords:
        raise HTTPException(status_code=400, detail="At least one keyword is required.")
    try:
        from src.pipeline.step1_keyword_expansion.step1_keyword_expansion import Step1KeywordExpansion
        settings = load_settings()
        step = Step1KeywordExpansion(settings=settings)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, step.run, body.keywords)
        value = result.value if hasattr(result, "value") else result
        _save_checkpoint("run_nodb", "step1_keyword_expansion", value)
        return {"status": "ok", "data": value}
    except Exception as exc:
        logger.error(f"run/step1 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))
