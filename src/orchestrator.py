"""SEODOMINATOR pipeline orchestrator — chains all 13 stages end-to-end."""

import argparse
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.settings import load_settings
from src.pipeline.stage_result import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CHECKPOINT_DIR = Path("outputs")


class _StopRequested(Exception):
    pass


class SEODominator:
    """Runs the 13-stage SEODOMINATOR pipeline sequentially."""

    def __init__(self, settings=None, db=None, cancel_event: Optional[threading.Event] = None):
        self._settings = settings or load_settings()
        self._db = db
        self._cancel_event = cancel_event

    def run(
        self,
        keywords: List[str],
        steps: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute the pipeline for the given keywords.

        Args:
            keywords:  Seed keywords for this run.
            steps:     If provided, only run these stage names (e.g. ["step1", "step5"]).
            dry_run:   Skip publishing and DB writes if True.

        Returns:
            Dictionary with all stage outputs and metadata.
        """
        result: Dict[str, Any] = {
            "keywords":            keywords,
            "keyword_ideas":       None,    # Step 1
            "keyword_clusters":    None,    # Step 2
            "serp_intel":          None,    # Step 3
            "competitor_analysis": None,    # Step 4
            "blueprint":           None,    # Step 5
            "article":             None,    # Step 6
            "seo_output":          None,    # Step 7
            "media":               None,    # Step 8
            "linked_article":      None,    # Step 9
            "tech_seo":            None,    # Step 10
            "published_url":       None,    # Step 11
            "social_posts":        None,    # Step 12
            "tracking":            None,    # Step 13
            "stage_errors":        {},
        }

        def should_run(stage: str) -> bool:
            return steps is None or stage in steps

        run_id = self._start_run(keywords)

        try:
            # ── Step 1: Keyword Fetch ─────────────────────────────────────────
            if should_run("step1"):
                from src.pipeline.step1_keyword_expansion.step1_keyword_expansion import Step1KeywordExpansion
                step1 = Step1KeywordExpansion(settings=self._settings)
                result["keyword_ideas"] = self._run_step(
                    run_id, "step1_keyword_expansion",
                    lambda: step1.run(keywords)
                )
            else:
                result["keyword_ideas"] = self._load_checkpoint(run_id, "step1_keyword_expansion")

            # ── Step 2: Keyword Clustering ────────────────────────────────────
            if result["keyword_ideas"] and should_run("step2"):
                from src.pipeline.step2_keyword_clustering.step2_keyword_clustering import Step2KeywordClustering
                step2 = Step2KeywordClustering(settings=self._settings)
                result["keyword_clusters"] = self._run_step(
                    run_id, "step2_keyword_clustering",
                    lambda: step2.run(result["keyword_ideas"])
                )
            elif not should_run("step2"):
                result["keyword_clusters"] = self._load_checkpoint(run_id, "step2_keyword_clustering")

            # ── Step 3: SERP Intel ────────────────────────────────────────────
            if result["keyword_clusters"] and should_run("step3"):
                from src.pipeline.step3_serp_intel.step3_serp_intel import Step3SerpIntel
                step3 = Step3SerpIntel(settings=self._settings)
                result["serp_intel"] = self._run_step(
                    run_id, "step3_serp_intel",
                    lambda: step3.run(result["keyword_clusters"])
                )
            elif not should_run("step3"):
                result["serp_intel"] = self._load_checkpoint(run_id, "step3_serp_intel")

            # ── Step 4: Competitor Analysis ───────────────────────────────────
            if result["serp_intel"] and should_run("step4"):
                from src.pipeline.step4_competitor_analysis.step4_competitor_analysis import Step4CompetitorAnalysis
                step4 = Step4CompetitorAnalysis(settings=self._settings)
                result["competitor_analysis"] = self._run_step(
                    run_id, "step4_competitor_analysis",
                    lambda: step4.run(result["keyword_clusters"], result["serp_intel"])
                )
            elif not should_run("step4"):
                result["competitor_analysis"] = self._load_checkpoint(run_id, "step4_competitor_analysis")

            # ── Step 5: Content Blueprint ─────────────────────────────────────
            if result["competitor_analysis"] and should_run("step5"):
                from src.pipeline.step5_content_blueprint.step5_content_blueprint import Step5ContentBlueprint
                step5 = Step5ContentBlueprint(settings=self._settings)
                result["blueprint"] = self._run_step(
                    run_id, "step5_content_blueprint",
                    lambda: step5.run(result["keyword_clusters"], result["serp_intel"], result["competitor_analysis"])
                )
            elif not should_run("step5"):
                result["blueprint"] = self._load_checkpoint(run_id, "step5_content_blueprint")

            # ── Step 6: Deep Write ────────────────────────────────────────────
            if result["blueprint"] and should_run("step6"):
                from src.pipeline.step6_deep_write.step6_deep_write import Step6DeepWrite
                step6 = Step6DeepWrite(settings=self._settings)
                result["article"] = self._run_step(
                    run_id, "step6_deep_write",
                    lambda: step6.run(result["blueprint"], result["keyword_clusters"])
                )
            elif not should_run("step6"):
                result["article"] = self._load_checkpoint(run_id, "step6_deep_write")

            # ── Step 7: SEO Optimization ──────────────────────────────────────
            if result["article"] and should_run("step7"):
                from src.pipeline.step7_seo_optimization.step7_seo_optimization import Step7SeoOptimization
                step7 = Step7SeoOptimization(settings=self._settings)
                result["seo_output"] = self._run_step(
                    run_id, "step7_seo_optimization",
                    lambda: step7.run(result["article"], result["keyword_clusters"])
                )
            elif not should_run("step7"):
                result["seo_output"] = self._load_checkpoint(run_id, "step7_seo_optimization")

            # ── Step 8: Media Generation ──────────────────────────────────────
            if result["seo_output"] and should_run("step8") and not dry_run:
                from src.pipeline.step8_media_generation.step8_media_generation import Step8MediaGeneration
                step8 = Step8MediaGeneration(settings=self._settings)
                result["media"] = self._run_step(
                    run_id, "step8_media_generation",
                    lambda: step8.run(result["seo_output"])
                )
            elif not should_run("step8"):
                result["media"] = self._load_checkpoint(run_id, "step8_media_generation")

            # ── Step 9: Internal Linking ──────────────────────────────────────
            if result["seo_output"] and should_run("step9"):
                from src.pipeline.step9_internal_linking.step9_internal_linking import Step9InternalLinking
                step9 = Step9InternalLinking(settings=self._settings)
                result["linked_article"] = self._run_step(
                    run_id, "step9_internal_linking",
                    lambda: step9.run(result["seo_output"], result.get("media"))
                )
            elif not should_run("step9"):
                result["linked_article"] = self._load_checkpoint(run_id, "step9_internal_linking")

            # ── Step 10: Technical SEO ────────────────────────────────────────
            if result["linked_article"] and should_run("step10"):
                from src.pipeline.step10_technical_seo.step10_technical_seo import Step10TechnicalSeo
                step10 = Step10TechnicalSeo(settings=self._settings)
                result["tech_seo"] = self._run_step(
                    run_id, "step10_technical_seo",
                    lambda: step10.run(result["linked_article"], result["seo_output"])
                )
            elif not should_run("step10"):
                result["tech_seo"] = self._load_checkpoint(run_id, "step10_technical_seo")

            # ── Step 11: Publish ──────────────────────────────────────────────
            if result["tech_seo"] and should_run("step11") and not dry_run:
                from src.pipeline.step11_publish.step11_publish import Step11Publish
                step11 = Step11Publish(settings=self._settings)
                result["published_url"] = self._run_step(
                    run_id, "step11_publish",
                    lambda: step11.run(result["linked_article"], result["seo_output"], result["tech_seo"], result.get("media"), run_id)
                )
            elif not should_run("step11"):
                result["published_url"] = self._load_checkpoint(run_id, "step11_publish")

            # ── Step 12: Amplify & Distribute ─────────────────────────────────
            if result.get("published_url") and should_run("step12"):
                from src.pipeline.step12_amplify_distribute.step12_amplify_distribute import Step12AmplifyDistribute
                step12 = Step12AmplifyDistribute(settings=self._settings)
                result["social_posts"] = self._run_step(
                    run_id, "step12_amplify_distribute",
                    lambda: step12.run(result["published_url"], result["seo_output"], result["keyword_clusters"])
                )
            elif not should_run("step12"):
                result["social_posts"] = self._load_checkpoint(run_id, "step12_amplify_distribute")

            # ── Step 13: Track & Report ───────────────────────────────────────
            if should_run("step13") and not dry_run:
                from src.pipeline.step13_track_report.step13_track_report import Step13TrackReport
                step13 = Step13TrackReport(settings=self._settings)
                result["tracking"] = self._run_step(
                    run_id, "step13_track_report",
                    lambda: step13.run(
                        result.get("published_url"),
                        result["keyword_clusters"],
                        result,
                        run_id,
                    )
                )

            self._finish_run(run_id, result)
            self._log_summary(result)

        except _StopRequested:
            self._mark_run_status(run_id, "stopped")
            logger.info(f"Run {run_id} stopped by user.")

        return result

    # ── Step execution ─────────────────────────────────────────────────────────

    def _run_step(self, run_id: Optional[int], step_name: str, fn) -> Any:
        if self._cancel_event and self._cancel_event.is_set():
            raise _StopRequested()

        step_id = self._start_step(run_id, step_name)
        try:
            raw = fn()
            if isinstance(raw, StageResult):
                value, tokens_in, tokens_out = raw.value, raw.tokens_in, raw.tokens_out
            else:
                value, tokens_in, tokens_out = raw, None, None

            output_str = self._serialise(value)
            self._finish_step(step_id, output=output_str, tokens_in=tokens_in, tokens_out=tokens_out)
            self._save_checkpoint(run_id, step_name, value)
            logger.info(f"[green]✓ {step_name}[/green]")
            return value

        except _StopRequested:
            self._finish_step(step_id, error="stopped by user")
            raise
        except Exception as exc:
            logger.error(f"[red]✗ {step_name} failed: {exc}[/red]")
            self._finish_step(step_id, error=str(exc))
            return None

    # ── DB helpers ─────────────────────────────────────────────────────────────

    def _start_run(self, keywords: List[str]) -> Optional[int]:
        if self._db is None:
            return None
        try:
            from src.storage.models import Run
            with self._db.session() as session:
                run = Run(status="running", seed_keywords=json.dumps(keywords))
                session.add(run)
                session.flush()
                return run.id
        except Exception as exc:
            logger.warning(f"DB run start failed: {exc}")
            return None

    def _finish_run(self, run_id: Optional[int], result: dict) -> None:
        if self._db is None or run_id is None:
            return
        try:
            from src.storage.models import Run, BlogPost, StepLog
            from sqlalchemy import select
            with self._db.session() as session:
                run = session.get(Run, run_id)
                if run is None:
                    return
                failed = session.scalars(
                    select(StepLog).where(StepLog.run_id == run_id, StepLog.status == "failed")
                ).first()
                run.status = "failed" if failed else "done"
                run.finished_at = datetime.now(timezone.utc)

                seo = result.get("seo_output") or {}
                linked = result.get("linked_article") or {}
                if seo.get("seo_title") and seo.get("optimized_content"):
                    post = BlogPost(
                        run_id=run_id,
                        title=seo["seo_title"],
                        content=linked.get("content") or seo["optimized_content"],
                        seo_tags=json.dumps(seo.get("seo_tags") or []),
                        image_urls=json.dumps((result.get("media") or {}).get("image_urls") or []),
                        published_url=result.get("published_url"),
                        word_count=seo.get("word_count"),
                        keyword_density=seo.get("keyword_density"),
                        internal_links=linked.get("forward_link_count", 0),
                        is_published=bool(result.get("published_url")),
                    )
                    session.add(post)
        except Exception as exc:
            logger.warning(f"DB run finish failed: {exc}")

    def _mark_run_status(self, run_id: Optional[int], status: str) -> None:
        if self._db is None or run_id is None:
            return
        try:
            from src.storage.models import Run
            with self._db.session() as session:
                run = session.get(Run, run_id)
                if run:
                    run.status = status
                    run.finished_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning(f"DB status update failed: {exc}")

    def _start_step(self, run_id: Optional[int], step_name: str) -> Optional[int]:
        if self._db is None or run_id is None:
            return None
        try:
            from src.storage.models import StepLog
            with self._db.session() as session:
                step = StepLog(run_id=run_id, step_name=step_name, status="running")
                session.add(step)
                session.flush()
                return step.id
        except Exception as exc:
            logger.warning(f"DB step start failed: {exc}")
            return None

    def _finish_step(
        self,
        step_id: Optional[int],
        output: Optional[str] = None,
        error: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
    ) -> None:
        if self._db is None or step_id is None:
            return
        try:
            from src.storage.models import StepLog
            with self._db.session() as session:
                step = session.get(StepLog, step_id)
                if step is None:
                    return
                step.status = "failed" if error else "done"
                step.output = output
                step.error = error
                step.tokens_in = tokens_in
                step.tokens_out = tokens_out
                step.finished_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning(f"DB step finish failed: {exc}")

    # ── Checkpointing ──────────────────────────────────────────────────────────

    def _save_checkpoint(self, run_id: Optional[int], step_name: str, value: Any) -> None:
        try:
            _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
            run_label = f"run_{run_id}" if run_id else "run_nodb"
            path = _CHECKPOINT_DIR / run_label / f"{step_name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(value, f, default=str, indent=2)
        except Exception as exc:
            logger.warning(f"Checkpoint save failed for {step_name}: {exc}")

    def _load_checkpoint(self, run_id: Optional[int], step_name: str) -> Any:
        try:
            run_label = f"run_{run_id}" if run_id else "run_nodb"
            path = _CHECKPOINT_DIR / run_label / f"{step_name}.json"
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        except Exception as exc:
            logger.warning(f"Checkpoint load failed for {step_name}: {exc}")
        return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _serialise(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value[:10_000]
        try:
            return json.dumps(value, default=str)[:10_000]
        except Exception:
            return str(value)[:10_000]

    @staticmethod
    def _log_summary(result: dict) -> None:
        errors = result.get("stage_errors", {})
        url = result.get("published_url", "N/A (dry run or not reached)")
        if errors:
            logger.warning(f"Pipeline done with {len(errors)} error(s): {list(errors)}")
        else:
            logger.info(f"[bold green]Pipeline complete → {url}[/bold green]")


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SEODOMINATOR — 13-stage SEO pipeline")
    parser.add_argument("--keywords", nargs="+", required=True, help="Seed keywords for this run")
    parser.add_argument(
        "--steps", nargs="+", default=None,
        metavar="STAGE",
        help="Run only these stages: step1 step2 ... step13",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip publishing, image upload, and DB writes")
    parser.add_argument("--no-db", action="store_true", help="Skip local database logging entirely")
    args = parser.parse_args()

    settings = load_settings()
    db = None
    if not args.no_db and not args.dry_run:
        from src.storage.database import init_db
        db = init_db(settings.database_url)

    pipeline = SEODominator(settings=settings, db=db)
    result = pipeline.run(keywords=args.keywords, steps=args.steps, dry_run=args.dry_run)

    if result.get("published_url"):
        print(f"\n✓ Published: {result['published_url']}")
    if result.get("social_posts"):
        print("\n── Social posts ──")
        for platform, post in result["social_posts"].items():
            print(f"\n[{platform.upper()}]\n{post}")
    if result.get("stage_errors"):
        print(f"\n⚠  Stage errors: {result['stage_errors']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
