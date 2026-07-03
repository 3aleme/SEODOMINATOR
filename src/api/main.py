"""SEODOMINATOR FastAPI dashboard — keyword input UI and step execution endpoints."""

import asyncio
import json
import traceback
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config.settings import load_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="SEODOMINATOR", docs_url="/docs")
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
_CHECKPOINT_DIR = Path("outputs")
_RUN_LABEL = "run_nodb"

_STEP_NAMES = {
    1:  "step1_keyword_expansion",
    2:  "step2_serp_intel",
    3:  "step3_competitor_analysis",
    4:  "step4_content_blueprint",
    5:  "step5_deep_write",
    6:  "step6_seo_optimization",
    7:  "step7_media_generation",
    8:  "step8_internal_linking",
    9:  "step9_technical_seo",
    10: "step10_publish",
    11: "step11_amplify_distribute",
    12: "step12_track_report",
}


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _save_checkpoint(step_name: str, value) -> None:
    try:
        path = _CHECKPOINT_DIR / _RUN_LABEL / f"{step_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(value, f, default=str, indent=2)
    except Exception as exc:
        logger.warning(f"Checkpoint save failed for {step_name}: {exc}")


def _load_checkpoint(step_name: str):
    try:
        path = _CHECKPOINT_DIR / _RUN_LABEL / f"{step_name}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        logger.warning(f"Checkpoint load failed for {step_name}: {exc}")
    return None


def _require_checkpoint(step_name: str):
    data = _load_checkpoint(step_name)
    if data is None:
        raise HTTPException(
            status_code=400,
            detail=f"Missing checkpoint: {step_name}. Run the preceding step first."
        )
    return data


def _step_response(step_name: str, result) -> dict:
    value = result.value if hasattr(result, "value") else result
    _save_checkpoint(step_name, value)
    return {"status": "ok", "data": value}


async def _run(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


# ── Request models ────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    url: str

class Step1Request(BaseModel):
    keywords: List[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(_TEMPLATE_PATH.read_text())


@app.get("/api/status")
async def status():
    """Return which step checkpoints currently exist."""
    result = {}
    for num, name in _STEP_NAMES.items():
        path = _CHECKPOINT_DIR / _RUN_LABEL / f"{name}.json"
        result[str(num)] = path.exists()
    return result


@app.post("/api/suggest-keywords")
async def suggest_keywords(body: SuggestRequest):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        from src.pipeline.step1_keyword_expansion.keyword_suggester import suggest_from_url
        settings = load_settings()
        keywords = await _run(suggest_from_url, body.url, settings)
        return {"keywords": keywords}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"suggest-keywords failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step1")
async def run_step1(body: Step1Request):
    if not body.keywords:
        raise HTTPException(status_code=400, detail="At least one keyword is required.")
    try:
        from src.pipeline.step1_keyword_expansion.step1_keyword_expansion import Step1KeywordExpansion
        settings = load_settings()
        step = Step1KeywordExpansion(settings=settings)
        result = await _run(step.run, body.keywords)
        return _step_response("step1_keyword_expansion", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step1 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step2")
async def run_step2():
    try:
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        from src.pipeline.step2_serp_intel.step2_serp_intel import Step2SerpIntel
        settings = load_settings()
        step = Step2SerpIntel(settings=settings)
        result = await _run(step.run, keyword_clusters)
        return _step_response("step2_serp_intel", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step2 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step3")
async def run_step3():
    try:
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        serp_intel = _require_checkpoint("step2_serp_intel")
        from src.pipeline.step3_competitor_analysis.step3_competitor_analysis import Step3CompetitorAnalysis
        settings = load_settings()
        step = Step3CompetitorAnalysis(settings=settings)
        result = await _run(step.run, keyword_clusters, serp_intel)
        return _step_response("step3_competitor_analysis", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step3 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step4")
async def run_step4():
    try:
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        serp_intel = _require_checkpoint("step2_serp_intel")
        competitor_analysis = _require_checkpoint("step3_competitor_analysis")
        from src.pipeline.step4_content_blueprint.step4_content_blueprint import Step4ContentBlueprint
        settings = load_settings()
        step = Step4ContentBlueprint(settings=settings)
        result = await _run(step.run, keyword_clusters, serp_intel, competitor_analysis)
        return _step_response("step4_content_blueprint", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step4 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step5")
async def run_step5():
    try:
        blueprint = _require_checkpoint("step4_content_blueprint")
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        from src.pipeline.step5_deep_write.step5_deep_write import Step5DeepWrite
        settings = load_settings()
        step = Step5DeepWrite(settings=settings)
        result = await _run(step.run, blueprint, keyword_clusters)
        return _step_response("step5_deep_write", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step5 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step6")
async def run_step6():
    try:
        article = _require_checkpoint("step5_deep_write")
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        from src.pipeline.step6_seo_optimization.step6_seo_optimization import Step6SeoOptimization
        settings = load_settings()
        step = Step6SeoOptimization(settings=settings)
        result = await _run(step.run, article, keyword_clusters)
        return _step_response("step6_seo_optimization", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step6 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step7")
async def run_step7():
    try:
        seo_output = _require_checkpoint("step6_seo_optimization")
        from src.pipeline.step7_media_generation.step7_media_generation import Step7MediaGeneration
        settings = load_settings()
        step = Step7MediaGeneration(settings=settings)
        result = await _run(step.run, seo_output)
        return _step_response("step7_media_generation", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step7 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step8")
async def run_step8():
    try:
        seo_output = _require_checkpoint("step6_seo_optimization")
        media = _load_checkpoint("step7_media_generation")
        from src.pipeline.step8_internal_linking.step8_internal_linking import Step8InternalLinking
        settings = load_settings()
        step = Step8InternalLinking(settings=settings)
        result = await _run(step.run, seo_output, media)
        return _step_response("step8_internal_linking", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step8 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step9")
async def run_step9():
    try:
        linked_article = _require_checkpoint("step8_internal_linking")
        seo_output = _require_checkpoint("step6_seo_optimization")
        from src.pipeline.step9_technical_seo.step9_technical_seo import Step9TechnicalSeo
        settings = load_settings()
        step = Step9TechnicalSeo(settings=settings)
        result = await _run(step.run, linked_article, seo_output)
        return _step_response("step9_technical_seo", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step9 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step10")
async def run_step10():
    try:
        linked_article = _require_checkpoint("step8_internal_linking")
        seo_output = _require_checkpoint("step6_seo_optimization")
        tech_seo = _require_checkpoint("step9_technical_seo")
        media = _load_checkpoint("step7_media_generation")
        from src.pipeline.step10_publish.step10_publish import Step10Publish
        settings = load_settings()
        step = Step10Publish(settings=settings)

        def _do_run():
            return step.run(linked_article, seo_output, tech_seo, media, run_id=None)

        result = await _run(_do_run)
        return _step_response("step10_publish", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step10 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step11")
async def run_step11():
    try:
        published_url = _require_checkpoint("step10_publish")
        seo_output = _require_checkpoint("step6_seo_optimization")
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        from src.pipeline.step11_amplify_distribute.step11_amplify_distribute import Step11AmplifyDistribute
        settings = load_settings()
        step = Step11AmplifyDistribute(settings=settings)
        # published_url checkpoint stores the URL string directly
        url_str = published_url if isinstance(published_url, str) else str(published_url)
        result = await _run(step.run, url_str, seo_output, keyword_clusters)
        return _step_response("step11_amplify_distribute", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step11 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run/step12")
async def run_step12():
    try:
        published_url = _load_checkpoint("step10_publish")
        keyword_clusters = _require_checkpoint("step1_keyword_expansion")
        pipeline_result = {
            "keyword_clusters":    keyword_clusters,
            "serp_intel":          _load_checkpoint("step2_serp_intel"),
            "competitor_analysis": _load_checkpoint("step3_competitor_analysis"),
            "blueprint":           _load_checkpoint("step4_content_blueprint"),
            "article":             _load_checkpoint("step5_deep_write"),
            "seo_output":          _load_checkpoint("step6_seo_optimization"),
            "media":               _load_checkpoint("step7_media_generation"),
            "linked_article":      _load_checkpoint("step8_internal_linking"),
            "tech_seo":            _load_checkpoint("step9_technical_seo"),
            "published_url":       published_url,
            "social_posts":        _load_checkpoint("step11_amplify_distribute"),
        }
        from src.pipeline.step12_track_report.step12_track_report import Step12TrackReport
        settings = load_settings()
        step = Step12TrackReport(settings=settings)
        url_str = published_url if isinstance(published_url, str) else None

        def _do_run():
            return step.run(url_str, keyword_clusters, pipeline_result, run_id=None)

        result = await _run(_do_run)
        return _step_response("step12_track_report", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step12 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))
