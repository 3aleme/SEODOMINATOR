# SEODOMINATOR — Implementation Plan

## Goal

Replace BridgeMindProject1 with **SEODOMINATOR** (`/home/hassan/Desktop/Coding/SEODOMINATOR`) — a 12-stage pipeline that takes a set of keywords provided via UI or CLI, and produces content that ranks #1 organically. Single-site target (Cycolaps). Publishes to the same Neon Postgres DB.

## Design Decisions (From Your Answers)

| Decision | Choice |
|---|---|
| Keyword source | Hardcoded set, entered via UI per run or passed via CLI at launch |
| SERP intelligence | Google Ads Keyword Planner API (existing) — no separate SERP scraper |
| Internal linking | New pipeline step: analyzes content + existing published blogs, injects links bidirectionally |
| Multi-client | No — single site (Cycolaps). Keywords are dynamic per run |
| Content refresh | No automatic refresh — publish once, track performance |
| Feedback loop | Yes — full Google Search Console integration from day 1 |

---

## What We Keep From BridgeMindProject1

These components are battle-tested and will be ported (adapted, not copied blindly):

| Component | Source File | Adaptation |
|---|---|---|
| LLM provider abstraction | [provider.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/provider.py) | Keep as-is — Anthropic/xAI/OpenAI unified interface |
| Google Ads Keyword API | [keyword_research.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/pipeline/keyword_research.py) | Expand: add competition data extraction, related keyword clustering |
| Image generation (multi-provider) | [image_prompter.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/pipeline/image_prompter.py) | Keep the xAI→Gemini→DALL-E→Stability cascade |
| DB session management | [database.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/storage/database.py) | Port as-is |
| Neon publisher | [publisher.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/pipeline/publisher.py) | Adapt: add internal link injection support |
| Settings / env loading | [settings.py](file:///home/hassan/Desktop/Coding/BridgeMindProject1/src/config/settings.py) | Extend with Google Search Console credentials |

---

## The 12-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEODOMINATOR PIPELINE                               │
│                                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ 1. KEYWORD   │──▶│ 2. SERP      │──▶│ 3. COMPETITOR│──▶│ 4. CONTENT   │ │
│  │ EXPANSION    │   │ INTEL        │   │ ANALYSIS     │   │ BLUEPRINT    │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│                                                                  │          │
│                                                                  ▼          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ 8. INTERNAL  │◀──│ 7. MEDIA     │◀──│ 6. SEO       │◀──│ 5. DEEP      │ │
│  │ LINKING      │   │ GENERATION   │   │ OPTIMIZATION │   │ WRITE        │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ 9. TECHNICAL │──▶│ 10. PUBLISH  │──▶│ 11. AMPLIFY  │──▶│ 12. TRACK    │ │
│  │ SEO          │   │              │   │              │   │ & REPORT     │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage Details

---

#### Stage 1: Keyword Expansion
**Input:** User-provided keywords (via UI form or `--keywords` CLI flag)
**What it does:**
- Takes the hardcoded keyword set from the run config
- Expands each seed into related long-tail variants using Google Ads Keyword Planner API
- Classifies intent: informational / commercial / transactional (via LLM)
- Clusters related keywords into groups (primary + supporting)
- Scores each by opportunity (volume × low competition × trend)
- Extracts "People Also Ask"-style questions from the keyword data

**Output:** Ranked keyword clusters with intent labels, volumes, competition scores

---

#### Stage 2: SERP Intelligence
**Input:** Top keyword clusters from Stage 1
**What it does:**
- For each primary keyword, uses the Google Ads API to pull:
  - Competition level and CPC (cost-per-click = commercial value proxy)
  - Monthly search volume trends (12-month)
  - Related keywords that current rankers also target
- Determines the **content format** most likely to rank (via LLM analysis of keyword patterns):
  - "how to X" → step-by-step guide
  - "best X" → listicle/comparison
  - "X vs Y" → comparison article
  - "what is X" → explainer/pillar page
- Estimates minimum word count needed based on keyword competition level

**Output:** SERP intel report per keyword: recommended format, depth, angle, estimated difficulty

---

#### Stage 3: Competitor Content Analysis
**Input:** SERP intel from Stage 2, keyword clusters from Stage 1
**What it does:**
- For each target keyword, fetches the top 5-10 current articles (using NewsAPI + web scraping via trafilatura, same as current article_finder but smarter)
- Analyzes each competitor article via LLM:
  - Word count, heading structure, content depth
  - What topics they cover vs. miss
  - Quality of examples, data, visuals
  - Strengths to match, weaknesses to exploit
- Produces a **content gap analysis**: what nobody covers well

**Output:** Competitor matrix + content gaps + "beat strategy" per keyword

---

#### Stage 4: Content Blueprint
**Input:** Keyword clusters, SERP intel, competitor analysis
**What it does:**
- LLM generates a **detailed content outline** (not the full post yet):
  - Title options (3-5 candidates with click-appeal scores)
  - Full heading hierarchy (H1 → H2 → H3 → H4)
  - Key points to cover under each heading
  - Required data/stats/examples to include
  - FAQ section questions (from keyword expansion)
  - Target word count (based on SERP intel)
  - Unique angle that competitors miss (from gap analysis)
- This blueprint guides the writing stage — no more single-shot blind drafts

**Output:** Structured JSON blueprint: outline, title candidates, required sections, target length

---

#### Stage 5: Deep Write (Multi-Pass)
**Input:** Content blueprint from Stage 4, competitor articles for reference
**What it does — three sequential LLM passes:**

**Pass 1 — Expert Draft:**
- Writes the full article following the blueprint
- Targets 2000-4000+ words (configurable, based on SERP intel)
- Includes proper heading structure, examples, data points
- Cites sources where applicable
- Uses the multi-source research as knowledge base

**Pass 2 — Quality Review:**
- Second LLM call reviews the draft for:
  - Factual accuracy and depth
  - Missing angles from the blueprint
  - Readability (sentence variety, active voice, jargon level)
  - Whether it actually **beats** the competitor content
- Returns specific revision instructions

**Pass 3 — Revision:**
- Incorporates the review feedback
- Polishes transitions, adds missing depth
- Ensures the article is genuinely the most comprehensive resource on the topic

**Output:** Final markdown article (2000-4000+ words), substantially deeper than the old pipeline's 800-1200

---

#### Stage 6: SEO Optimization
**Input:** Final article from Stage 5, keyword clusters
**What it does:**
- Natural keyword integration (density check: target 1-2%)
- SEO title optimization (50-60 chars, primary keyword included)
- Generate 5-10 semantic SEO tags
- Add FAQ schema data structure
- Generate meta description (150-160 chars, click-optimized)
- Build JSON-LD structured data (Article + FAQ + BreadcrumbList)

**Output:** SEO-optimized article + title + tags + meta description + JSON-LD schemas

---

#### Stage 7: Media Generation
**Input:** SEO-optimized article, keywords
**What it does:**
- Generate featured hero image (existing multi-provider cascade)
- **NEW: Generate 1-2 in-article images** for key sections (diagrams, infographics)
- Generate image alt text with keyword variations
- Upload all images to Vercel Blob

**Output:** Image URLs + alt text metadata

---

#### Stage 8: Internal Linking (NEW — Critical Stage)
**Input:** Final article content, all previously published posts from the Cycolaps DB
**What it does:**

**Forward linking (new article → existing posts):**
- Fetches all existing published posts from the Cycolaps Neon DB (title, slug, content excerpt)
- LLM identifies natural linking opportunities: which phrases in the new article could contextually link to existing posts
- Injects 3-5 internal links into the new article body

**Backward linking (existing posts → new article):**
- For each existing published post, LLM scans for phrases that could naturally link to the new article's topic
- Generates a list of `{post_slug, anchor_text, paragraph_context, link_to_inject}`
- Updates those existing posts in the Neon DB with the new internal links

> [!IMPORTANT]
> This is the single most impactful stage for building topical authority. Google heavily weights internal link structure. The old pipeline had zero internal linking.

**Output:** Updated article with internal links + list of existing posts to update with backlinks

---

#### Stage 9: Technical SEO
**Input:** Article + all metadata from previous stages
**What it does:**
- Build canonical URL
- Generate XML sitemap entry
- Build Open Graph + Twitter Card meta tags
- Validate heading hierarchy (single H1, logical cascade)
- Check keyword density (flag if over-optimized)
- Assemble final HTML-ready metadata bundle

**Output:** Technical SEO metadata package (canonical, OG tags, sitemap data)

---

#### Stage 10: Publish
**Input:** Everything from stages 5-9
**What it does:**
- Upsert post into Cycolaps Neon `posts` table (existing logic)
- Upload images to Vercel Blob (existing logic)
- Execute backward link updates from Stage 8 (update existing posts)
- Ping Google's indexing API / submit URL to Search Console

**Output:** Published URL + confirmation of all DB updates

---

#### Stage 11: Amplify & Distribute
**Input:** Published URL, article metadata, keywords
**What it does:**
- Generate social posts: Twitter, LinkedIn, Reddit, Bluesky (existing logic, enhanced prompts)
- Generate a "key takeaways" snippet for potential newsletter use
- Check if topic is trending on social platforms (existing social_checker)

**Output:** Platform-specific social content ready to post

---

#### Stage 12: Track & Report
**Input:** Published URL, target keywords, run metadata
**What it does:**
- Record the published post + keywords in a new `keyword_tracking` table
- Query Google Search Console API for baseline metrics:
  - Current impressions, clicks, CTR, average position for the target keywords
- Create the initial tracking record for this keyword set
- Generate a run summary report with:
  - All pipeline stage stats (tokens used, time per stage)
  - Content quality metrics (word count, keyword density, internal link count)
  - Baseline ranking position (if any existing presence)
  - Competitive gap score (how much better our content is vs. current #1)

**Future (manual trigger):** A `/track` dashboard page shows ranking progress over time per keyword

**Output:** Tracking record created + run summary report

---

## Project Structure

```
SEODOMINATOR/
├── .env                          # API keys, DB URLs
├── .env.example                  # Template
├── pyproject.toml                # Dependencies
├── alembic.ini                   # DB migrations config
├── alembic/                      # Migration scripts
│   └── versions/
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # [PORTED + EXTENDED] Env loading
│   ├── provider.py               # [PORTED] Unified LLM client
│   ├── orchestrator.py           # [NEW] 12-stage pipeline orchestrator
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── stage_result.py       # [PORTED] StageResult dataclass
│   │   ├── prompts.py            # [NEW] All LLM prompts (massive upgrade)
│   │   ├── keyword_expander.py   # [NEW] Stage 1: Keyword expansion + clustering
│   │   ├── serp_intel.py         # [NEW] Stage 2: SERP intelligence via Keyword API
│   │   ├── competitor_analyzer.py # [NEW] Stage 3: Competitor content deep-dive
│   │   ├── content_blueprint.py  # [NEW] Stage 4: Structured content outline
│   │   ├── deep_writer.py        # [NEW] Stage 5: Multi-pass article writing
│   │   ├── seo_optimizer.py      # [NEW] Stage 6: SEO optimization (enhanced)
│   │   ├── media_generator.py    # [PORTED + EXTENDED] Stage 7: Images
│   │   ├── internal_linker.py    # [NEW] Stage 8: Bidirectional internal linking
│   │   ├── technical_seo.py      # [NEW] Stage 9: Technical SEO metadata
│   │   ├── publisher.py          # [PORTED + EXTENDED] Stage 10: Publish to Neon
│   │   ├── amplifier.py          # [NEW] Stage 11: Social distribution
│   │   └── tracker.py            # [NEW] Stage 12: GSC tracking + reporting
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # [PORTED] Session management
│   │   └── models.py             # [NEW] Extended schema (see below)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py                # [NEW] FastAPI dashboard
│   │   └── templates/
│   │       ├── base.html          # Shared layout
│   │       ├── dashboard.html     # Main dashboard
│   │       ├── run_detail.html    # Run detail view
│   │       ├── tracking.html      # Keyword tracking dashboard
│   │       └── launch.html        # Run configuration / keyword entry
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # [PORTED] Structured logging
│       └── rate_limiter.py       # [PORTED] API rate limiting
├── outputs/                      # Checkpoint files per run
└── README.md
```

---

## Database Schema

### Local PostgreSQL (Docker — pipeline state)

```sql
-- Runs table (simplified: no multi-client Product table)
CREATE TABLE runs (
    id            SERIAL PRIMARY KEY,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    seed_keywords TEXT NOT NULL,          -- JSON array of user-provided keywords
    config        TEXT,                    -- JSON: run configuration overrides
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ,
    error         TEXT
);

-- Step logs (same concept, more stages)
CREATE TABLE step_logs (
    id          SERIAL PRIMARY KEY,
    run_id      INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    step_name   VARCHAR(100) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'running',
    output      TEXT,
    error       TEXT,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Blog posts produced
CREATE TABLE blog_posts (
    id             SERIAL PRIMARY KEY,
    run_id         INTEGER REFERENCES runs(id) ON DELETE CASCADE UNIQUE,
    title          VARCHAR(500) NOT NULL,
    content        TEXT NOT NULL,
    seo_tags       TEXT,                    -- JSON array
    image_urls     TEXT,                    -- JSON array (multiple images now)
    published_url  VARCHAR(1000),
    word_count     INTEGER,
    keyword_density FLOAT,
    internal_links INTEGER,                -- count of internal links injected
    is_published   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NEW: Keyword tracking (for Stage 12 + tracking dashboard)
CREATE TABLE keyword_tracking (
    id              SERIAL PRIMARY KEY,
    keyword         VARCHAR(500) NOT NULL,
    blog_post_id    INTEGER REFERENCES blog_posts(id),
    published_url   VARCHAR(1000),
    target_position INTEGER DEFAULT 1,     -- what we're aiming for
    -- Snapshot fields (updated periodically from GSC)
    impressions     INTEGER DEFAULT 0,
    clicks          INTEGER DEFAULT 0,
    ctr             FLOAT DEFAULT 0,
    avg_position    FLOAT,
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NEW: Internal link graph
CREATE TABLE internal_links (
    id              SERIAL PRIMARY KEY,
    source_slug     VARCHAR(200) NOT NULL,  -- the post containing the link
    target_slug     VARCHAR(200) NOT NULL,  -- the post being linked to
    anchor_text     VARCHAR(500),
    created_by_run  INTEGER REFERENCES runs(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_slug, target_slug)
);
```

---

## FastAPI Dashboard

### Pages

| Route | Purpose |
|---|---|
| `GET /` | Dashboard: recent runs, keyword tracking summary, quick stats |
| `GET /launch` | **Run configuration page**: keyword input form, config toggles |
| `POST /run` | Trigger a new run with the provided keywords |
| `GET /runs/{id}` | Run detail: stage-by-stage progress, outputs, errors |
| `POST /runs/{id}/stop` | Cancel a running pipeline |
| `GET /tracking` | **Keyword tracking dashboard**: position over time, CTR, impressions |
| `POST /tracking/refresh` | Manually trigger a GSC data pull for all tracked keywords |

### Launch Page (keyword entry)

The `/launch` page provides:
- A textarea for entering keywords (one per line)
- Toggle switches for optional stages (e.g., skip social, skip image generation)
- A "Target word count" slider (2000-5000, default 3000)
- A "Run" button that starts the pipeline in the background
- Pre-populated with previous run's keywords for easy re-runs

### CLI Launch

```bash
# Launch via CLI with keywords
python -m src.orchestrator --keywords "docker compose tutorial" "docker networking guide" "container orchestration"

# Launch with UI
python -m src.api.app
# Then open http://localhost:8000/launch
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| LLM | Claude Sonnet 4.6 / Grok 3 / GPT-4o (provider abstraction ported) |
| Keyword API | Google Ads Keyword Planner (existing) |
| Article scraping | NewsAPI + trafilatura (existing) |
| Image generation | xAI → Gemini Imagen → DALL-E 3 → Stability AI (existing cascade) |
| Local DB | PostgreSQL in Docker (port 5433) |
| Publishing DB | Cycolaps Neon Postgres (existing) |
| Image hosting | Vercel Blob (existing) |
| Web framework | FastAPI + Jinja2 (existing pattern, new templates) |
| Migrations | Alembic |
| Tracking | Google Search Console API |
| Social | Twitter, LinkedIn, Reddit, Bluesky (existing) |

---

## New Dependencies (beyond BridgeMindProject1's)

| Package | Purpose |
|---|---|
| `google-api-python-client` + `google-auth` | Google Search Console API |
| `beautifulsoup4` | Enhanced HTML parsing for competitor analysis |
| (all existing deps carry over) | |

---

## Proposed Changes

### Config

#### [NEW] [settings.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/config/settings.py)
Port from BridgeMindProject1, add:
- `google_search_console_credentials` — JSON path for GSC service account
- `gsc_site_url` — the verified Search Console property (e.g., `https://cycolaps.com`)
- Remove multi-client settings (no `ProjectDependency/` scanning)
- Remove WordPress URL/user/password (publish directly to Neon, not WordPress)

---

### Pipeline Stages (all new files)

#### [NEW] [keyword_expander.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/keyword_expander.py)
Stage 1 — keyword expansion + intent classification + clustering

#### [NEW] [serp_intel.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/serp_intel.py)
Stage 2 — extract SERP intelligence from Google Ads API data

#### [NEW] [competitor_analyzer.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/competitor_analyzer.py)
Stage 3 — fetch + analyze top-ranking content for target keywords

#### [NEW] [content_blueprint.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/content_blueprint.py)
Stage 4 — generate detailed content outline before writing

#### [NEW] [deep_writer.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/deep_writer.py)
Stage 5 — three-pass writing: expert draft → review → revision

#### [NEW] [seo_optimizer.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/seo_optimizer.py)
Stage 6 — enhanced SEO optimization with density analysis + FAQ schema

#### [PORTED+EXTENDED] [media_generator.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/media_generator.py)
Stage 7 — hero image + in-article images + alt text

#### [NEW] [internal_linker.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/internal_linker.py)
Stage 8 — bidirectional internal linking engine

#### [NEW] [technical_seo.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/technical_seo.py)
Stage 9 — canonical URLs, OG tags, sitemap, heading validation

#### [PORTED+EXTENDED] [publisher.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/publisher.py)
Stage 10 — publish to Neon + execute backward link updates

#### [NEW] [amplifier.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/amplifier.py)
Stage 11 — social content generation (ported from social_content.py + social_checker.py)

#### [NEW] [tracker.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/pipeline/tracker.py)
Stage 12 — Google Search Console integration + tracking records

---

### Orchestrator

#### [NEW] [orchestrator.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/orchestrator.py)
Complete rewrite. Simpler than BridgeMindProject1 (no multi-client threading):
- Takes keywords directly (no client scanning)
- Runs the 12 stages sequentially
- Per-stage checkpointing, logging, error handling
- Cancellation support via threading.Event

---

### Storage

#### [NEW] [models.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/storage/models.py)
New schema: `runs`, `step_logs`, `blog_posts`, `keyword_tracking`, `internal_links`

#### [PORTED] [database.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/storage/database.py)
As-is from BridgeMindProject1

---

### Dashboard

#### [NEW] [app.py](file:///home/hassan/Desktop/Coding/SEODOMINATOR/src/api/app.py)
FastAPI app with:
- Dashboard (recent runs, stats)
- Launch page (keyword entry form)
- Run detail (stage progress)
- Tracking page (keyword positions over time)

#### [NEW] Templates: `dashboard.html`, `launch.html`, `run_detail.html`, `tracking.html`, `base.html`

---

## Verification Plan

### Automated Tests
```bash
# Run the pipeline in dry mode (no publishing, no DB writes)
python -m src.orchestrator --keywords "docker compose tutorial" --dry-run

# Run individual stages
python -m src.orchestrator --keywords "docker compose tutorial" --steps keyword_expand serp_intel

# Verify DB schema
alembic upgrade head
```

### Manual Verification
- Launch the UI at `localhost:8000`, enter keywords, trigger a run
- Verify each stage produces checkpointed output in `outputs/`
- Verify the published post appears on cycolaps.com with correct internal links
- Verify the tracking dashboard shows GSC data after 24-48 hours

---

## Build Order

> [!TIP]
> We'll build foundation-first, then stages in order, then dashboard last.

| Phase | Components | Why This Order |
|---|---|---|
| **Phase 1: Foundation** | `settings.py`, `provider.py`, `database.py`, `models.py`, `orchestrator.py` skeleton, `stage_result.py`, `logger.py`, `rate_limiter.py`, `prompts.py` | Everything else depends on these |
| **Phase 2: Intelligence** | Stages 1-4 (keyword_expander, serp_intel, competitor_analyzer, content_blueprint) | Must understand the keyword before writing |
| **Phase 3: Content** | Stages 5-7 (deep_writer, seo_optimizer, media_generator) | The actual article production |
| **Phase 4: Authority** | Stages 8-9 (internal_linker, technical_seo) | Post-content enhancement |
| **Phase 5: Distribution** | Stages 10-11 (publisher, amplifier) | Ship it |
| **Phase 6: Tracking** | Stage 12 (tracker) + tracking dashboard | Measure it |
| **Phase 7: Dashboard** | FastAPI app + all templates | Control center |

---

## User Review Required

> [!IMPORTANT]
> **LLM Token Cost**: The multi-pass writing (Stage 5) alone uses ~3 LLM calls per article, each potentially 4000+ tokens. Combined with all other stages, a single keyword run could use **15-20 LLM calls**. With Claude Sonnet, that's roughly $0.30-0.60 per article. Acceptable?

> [!IMPORTANT]
> **Google Search Console Setup**: Stage 12 requires a Google Cloud service account with Search Console API access, verified for `cycolaps.com`. Do you already have this set up, or should we plan to add it as a later addon?

> [!WARNING]
> **Backward Link Updates (Stage 8)**: This stage will **modify existing published blog posts** in the Cycolaps Neon DB to add links to the new article. This is powerful but irreversible without rollback logic. Should we add a confirmation step or a dry-run mode for this?
