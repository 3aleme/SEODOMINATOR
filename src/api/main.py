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
    2:  "step2_keyword_clustering",
    3:  "step3_serp_intel",
    4:  "step4_competitor_analysis",
    5:  "step5_content_blueprint",
    6:  "step6_deep_write",
    7:  "step7_seo_optimization",
    8:  "step8_media_generation",
    9:  "step9_internal_linking",
    10: "step10_technical_seo",
    11: "step11_publish",
    12: "step12_amplify_distribute",
    13: "step13_track_report",
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
    return {str(num): (_CHECKPOINT_DIR / _RUN_LABEL / f"{name}.json").exists()
            for num, name in _STEP_NAMES.items()}


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


# Step 1 — Google Ads keyword fetch (no LLM)
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


# Step 2 — LLM keyword clustering
@app.post("/api/run/step2")
async def run_step2():
    try:
        keyword_ideas = _require_checkpoint("step1_keyword_expansion")
        from src.pipeline.step2_keyword_clustering.step2_keyword_clustering import Step2KeywordClustering
        settings = load_settings()
        step = Step2KeywordClustering(settings=settings)
        result = await _run(step.run, keyword_ideas)
        return _step_response("step2_keyword_clustering", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step2 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 3 — SERP Intel
@app.post("/api/run/step3")
async def run_step3():
    try:
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        from src.pipeline.step3_serp_intel.step3_serp_intel import Step3SerpIntel
        settings = load_settings()
        step = Step3SerpIntel(settings=settings)
        result = await _run(step.run, keyword_clusters)
        return _step_response("step3_serp_intel", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step3 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 4 — Competitor Analysis
@app.post("/api/run/step4")
async def run_step4():
    try:
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        serp_intel = _require_checkpoint("step3_serp_intel")
        from src.pipeline.step4_competitor_analysis.step4_competitor_analysis import Step4CompetitorAnalysis
        settings = load_settings()
        step = Step4CompetitorAnalysis(settings=settings)
        result = await _run(step.run, keyword_clusters, serp_intel)
        return _step_response("step4_competitor_analysis", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step4 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 5 — Content Blueprint
@app.post("/api/run/step5")
async def run_step5():
    try:
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        serp_intel = _require_checkpoint("step3_serp_intel")
        competitor_analysis = _require_checkpoint("step4_competitor_analysis")
        from src.pipeline.step5_content_blueprint.step5_content_blueprint import Step5ContentBlueprint
        settings = load_settings()
        step = Step5ContentBlueprint(settings=settings)
        result = await _run(step.run, keyword_clusters, serp_intel, competitor_analysis)
        return _step_response("step5_content_blueprint", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step5 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 6 — Deep Write
@app.post("/api/run/step6")
async def run_step6():
    try:
        blueprint = _require_checkpoint("step5_content_blueprint")
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        from src.pipeline.step6_deep_write.step6_deep_write import Step6DeepWrite
        settings = load_settings()
        step = Step6DeepWrite(settings=settings)
        result = await _run(step.run, blueprint, keyword_clusters)
        return _step_response("step6_deep_write", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step6 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 7 — SEO Optimization
@app.post("/api/run/step7")
async def run_step7():
    try:
        article = _require_checkpoint("step6_deep_write")
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        from src.pipeline.step7_seo_optimization.step7_seo_optimization import Step7SeoOptimization
        settings = load_settings()
        step = Step7SeoOptimization(settings=settings)
        result = await _run(step.run, article, keyword_clusters)
        return _step_response("step7_seo_optimization", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step7 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 8 — Media Generation
@app.post("/api/run/step8")
async def run_step8():
    try:
        seo_output = _require_checkpoint("step7_seo_optimization")
        from src.pipeline.step8_media_generation.step8_media_generation import Step8MediaGeneration
        settings = load_settings()
        step = Step8MediaGeneration(settings=settings)
        result = await _run(step.run, seo_output)
        return _step_response("step8_media_generation", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step8 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 9 — Internal Linking
@app.post("/api/run/step9")
async def run_step9():
    try:
        seo_output = _require_checkpoint("step7_seo_optimization")
        media = _load_checkpoint("step8_media_generation")
        from src.pipeline.step9_internal_linking.step9_internal_linking import Step9InternalLinking
        settings = load_settings()
        step = Step9InternalLinking(settings=settings)
        result = await _run(step.run, seo_output, media)
        return _step_response("step9_internal_linking", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step9 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 10 — Technical SEO
@app.post("/api/run/step10")
async def run_step10():
    try:
        linked_article = _require_checkpoint("step9_internal_linking")
        seo_output = _require_checkpoint("step7_seo_optimization")
        from src.pipeline.step10_technical_seo.step10_technical_seo import Step10TechnicalSeo
        settings = load_settings()
        step = Step10TechnicalSeo(settings=settings)
        result = await _run(step.run, linked_article, seo_output)
        return _step_response("step10_technical_seo", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step10 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 11 — Publish
@app.post("/api/run/step11")
async def run_step11():
    try:
        linked_article = _require_checkpoint("step9_internal_linking")
        seo_output = _require_checkpoint("step7_seo_optimization")
        tech_seo = _require_checkpoint("step10_technical_seo")
        media = _load_checkpoint("step8_media_generation")
        from src.pipeline.step11_publish.step11_publish import Step11Publish
        settings = load_settings()
        step = Step11Publish(settings=settings)

        def _do_run():
            return step.run(linked_article, seo_output, tech_seo, media, run_id=None)

        result = await _run(_do_run)
        return _step_response("step11_publish", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step11 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 12 — Amplify & Distribute
@app.post("/api/run/step12")
async def run_step12():
    try:
        published_url = _require_checkpoint("step11_publish")
        seo_output = _require_checkpoint("step7_seo_optimization")
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        from src.pipeline.step12_amplify_distribute.step12_amplify_distribute import Step12AmplifyDistribute
        settings = load_settings()
        step = Step12AmplifyDistribute(settings=settings)
        url_str = published_url if isinstance(published_url, str) else str(published_url)
        result = await _run(step.run, url_str, seo_output, keyword_clusters)
        return _step_response("step12_amplify_distribute", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step12 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))


# Step 13 — Track & Report
@app.post("/api/run/step13")
async def run_step13():
    try:
        published_url = _load_checkpoint("step11_publish")
        keyword_clusters = _require_checkpoint("step2_keyword_clustering")
        pipeline_result = {
            "keyword_ideas":       _load_checkpoint("step1_keyword_expansion"),
            "keyword_clusters":    keyword_clusters,
            "serp_intel":          _load_checkpoint("step3_serp_intel"),
            "competitor_analysis": _load_checkpoint("step4_competitor_analysis"),
            "blueprint":           _load_checkpoint("step5_content_blueprint"),
            "article":             _load_checkpoint("step6_deep_write"),
            "seo_output":          _load_checkpoint("step7_seo_optimization"),
            "media":               _load_checkpoint("step8_media_generation"),
            "linked_article":      _load_checkpoint("step9_internal_linking"),
            "tech_seo":            _load_checkpoint("step10_technical_seo"),
            "published_url":       published_url,
            "social_posts":        _load_checkpoint("step12_amplify_distribute"),
        }
        from src.pipeline.step13_track_report.step13_track_report import Step13TrackReport
        settings = load_settings()
        step = Step13TrackReport(settings=settings)
        url_str = published_url if isinstance(published_url, str) else None

        def _do_run():
            return step.run(url_str, keyword_clusters, pipeline_result, run_id=None)

        result = await _run(_do_run)
        return _step_response("step13_track_report", result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"run/step13 failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exc))
