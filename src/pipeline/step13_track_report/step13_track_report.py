"""
Step 12: Track & Report

Records the published post in the SEODOMINATOR keyword_tracking table and
attempts to pull an initial baseline from Google Search Console.
GSC data for newly published posts is typically unavailable immediately —
the baseline query is best-effort and failures are logged, not raised.

Input:  published_url (Step 10), keyword_clusters (Step 1),
        full pipeline result dict, run_id
Output: tracking summary dict
"""

import json
from datetime import datetime, timezone
from typing import Optional, Any

import psycopg2

from src.pipeline.stage_result import StageResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Step13TrackReport:
    def __init__(self, settings=None):
        self._settings = settings

    def run(
        self,
        published_url: Optional[str],
        keyword_clusters: dict,
        pipeline_result: dict,
        run_id: Optional[int],
    ) -> StageResult:
        """
        Args:
            published_url:    URL string from Step 10 (may be None on dry runs).
            keyword_clusters: Output of Step 1.
            pipeline_result:  Full result dict from the orchestrator (for summary).
            run_id:           Current pipeline run ID.

        Returns:
            {
                "published_url": str,
                "keywords_tracked": [str],
                "tracking_ids": [int],
                "gsc_baseline": dict,       # may be empty for new posts
                "run_summary": dict,
            }
        """
        if not published_url:
            logger.warning("Step 12: No published_url — skipping tracking registration.")
            return StageResult(
                value={"published_url": None, "keywords_tracked": [], "tracking_ids": [], "gsc_baseline": {}, "run_summary": {}},
                tokens_in=0,
                tokens_out=0,
            )

        keywords = _extract_keywords(keyword_clusters)
        logger.info(f"Step 12: Registering tracking for {len(keywords)} keywords → {published_url}")

        seodom_url = getattr(self._settings, "database_url", "") if self._settings else ""

        # ── 1. Insert/update keyword_tracking rows ────────────────────────────
        tracking_ids: list[int] = []
        if seodom_url and keywords and run_id:
            tracking_ids = self._register_keywords(seodom_url, keywords, published_url, run_id)
        else:
            logger.warning("Skipping keyword tracking DB write — missing DB URL, keywords, or run_id")

        # ── 2. GSC baseline query (best-effort) ───────────────────────────────
        gsc_baseline: dict = {}
        gsc_creds = getattr(self._settings, "gsc_credentials_path", "") if self._settings else ""
        gsc_site = getattr(self._settings, "gsc_site_url", "https://cycolaps.com") if self._settings else "https://cycolaps.com"

        if gsc_creds and keywords:
            gsc_baseline = self._query_gsc_baseline(gsc_creds, gsc_site, keywords, published_url)
        else:
            logger.info("GSC credentials not configured — skipping baseline query.")

        # ── 3. Build run summary ──────────────────────────────────────────────
        run_summary = _build_run_summary(pipeline_result, published_url, keywords)
        _log_run_summary(run_summary)

        logger.info(
            f"Step 12 complete. tracked={len(tracking_ids)} keywords, "
            f"gsc_data_points={len(gsc_baseline)}"
        )

        return StageResult(
            value={
                "published_url": published_url,
                "keywords_tracked": keywords,
                "tracking_ids": tracking_ids,
                "gsc_baseline": gsc_baseline,
                "run_summary": run_summary,
            },
            tokens_in=0,
            tokens_out=0,
        )

    def _register_keywords(
        self, db_url: str, keywords: list, published_url: str, run_id: int
    ) -> list:
        tracking_ids = []
        sql = """
            INSERT INTO keyword_tracking
                (keyword, published_url, target_position, impressions, clicks, ctr, created_at)
            VALUES (%s, %s, 1, 0, 0, 0.0, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """
        try:
            conn = psycopg2.connect(db_url)
            now = datetime.now(timezone.utc)
            with conn:
                with conn.cursor() as cur:
                    for kw in keywords:
                        cur.execute(sql, (kw, published_url, now))
                        row = cur.fetchone()
                        if row:
                            tracking_ids.append(row[0])
            conn.close()
            logger.info(f"Registered {len(tracking_ids)} new keyword tracking rows.")
        except Exception as exc:
            logger.warning(f"Keyword tracking DB write failed: {exc}")
        return tracking_ids

    def _query_gsc_baseline(
        self, creds_path: str, site_url: str, keywords: list, published_url: str
    ) -> dict:
        """Pull impressions/clicks/position for keywords from Google Search Console."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
            service = build("searchconsole", "v1", credentials=credentials)

            # GSC needs at least 3 days of data — newly published posts won't appear
            today = datetime.now(timezone.utc)
            start_date = today.strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")

            response = service.searchanalytics().query(
                siteUrl=site_url,
                body={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["query"],
                    "dimensionFilterGroups": [{
                        "filters": [{
                            "dimension": "page",
                            "operator": "equals",
                            "expression": published_url,
                        }]
                    }],
                    "rowLimit": 25,
                },
            ).execute()

            rows = response.get("rows", [])
            baseline = {}
            for row in rows:
                query = row.get("keys", [""])[0]
                baseline[query] = {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0.0),
                    "position": row.get("position"),
                }

            if not baseline:
                logger.info("GSC baseline: no data yet (expected for newly published posts).")
            else:
                logger.info(f"GSC baseline pulled for {len(baseline)} queries.")

            return baseline

        except ImportError:
            logger.warning("google-auth or google-api-python-client not installed — GSC skipped.")
            return {}
        except Exception as exc:
            logger.warning(f"GSC baseline query failed: {exc}")
            return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_keywords(keyword_clusters: dict) -> list:
    keywords = []
    for cluster in keyword_clusters.get("clusters", []):
        pk = cluster.get("primary_keyword", "")
        if pk:
            keywords.append(pk)
        keywords.extend(cluster.get("supporting_keywords", []))
    return list(dict.fromkeys(keywords))  # deduplicate, preserve order


def _build_run_summary(pipeline_result: dict, published_url: str, keywords: list) -> dict:
    article = pipeline_result.get("article") or {}
    seo = pipeline_result.get("seo_output") or {}
    linked = pipeline_result.get("linked_article") or {}
    media = pipeline_result.get("media") or {}
    social = pipeline_result.get("social_posts") or {}

    return {
        "published_url": published_url,
        "title": seo.get("seo_title", ""),
        "word_count": linked.get("word_count") or article.get("word_count", 0),
        "keyword_density": linked.get("keyword_density") or seo.get("keyword_density", 0.0),
        "internal_links": linked.get("forward_link_count", 0),
        "backward_link_updates": len(linked.get("backward_link_updates", [])),
        "images_generated": len(media.get("image_urls", [])),
        "social_platforms": [p for p in ["twitter", "linkedin", "reddit", "bluesky"] if social.get(p)],
        "keywords_targeted": keywords[:5],
        "quality_score": (article.get("review") or {}).get("overall_quality"),
        "passes_quality_bar": article.get("passes_bar"),
    }


def _log_run_summary(summary: dict) -> None:
    logger.info("─── Run Summary ──────────────────────────────────────")
    logger.info(f"  Published URL   : {summary['published_url']}")
    logger.info(f"  Title           : {summary['title']}")
    logger.info(f"  Word count      : {summary['word_count']}")
    logger.info(f"  Keyword density : {summary['keyword_density']:.2f}%")
    logger.info(f"  Internal links  : {summary['internal_links']} forward, {summary['backward_link_updates']} backward updates")
    logger.info(f"  Images          : {summary['images_generated']}")
    logger.info(f"  Social posts    : {summary['social_platforms']}")
    logger.info(f"  Quality score   : {summary['quality_score']}/10")
    logger.info("──────────────────────────────────────────────────────")
