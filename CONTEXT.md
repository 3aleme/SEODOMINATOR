# Project Navigation Context

Welcome to SEODOMINATOR. This document explains how to navigate the repository and make changes.

## Architecture
The system is divided into 12 discrete pipeline steps located in `src/pipeline/`.

To make changes to a specific part of the pipeline, navigate to its folder:
- `step1_keyword_expansion`: Expands and clusters seed keywords.
- `step2_serp_intel`: Analyzes SERP competition and recommends format.
- `step3_competitor_analysis`: Deep-dives into top-ranking competitor content.
- `step4_content_blueprint`: Creates the structural outline for the article.
- `step5_deep_write`: Multi-pass drafting of the article.
- `step6_seo_optimization`: Keywords injection, meta tags, schemas.
- `step7_media_generation`: Hero and in-article images.
- `step8_internal_linking`: Bidirectional internal link injection.
- `step9_technical_seo`: Canonical URLs, XML sitemaps, Open Graph.
- `step10_publish`: Upsert to Neon DB.
- `step11_amplify_distribute`: Social media snippets.
- `step12_track_report`: Google Search Console tracking.

## How to work on a step
1. Open the step's folder (e.g., `src/pipeline/step5_deep_write/`).
2. Read `CONTEXT.md` to understand the goal and position in the workflow.
3. Read `DEVPLAN.md` to understand what needs to be implemented.
4. If there's an `agent_config.json`, review the LLM prompt and skills required.
5. Implement the code in the `.py` file inside the folder.
