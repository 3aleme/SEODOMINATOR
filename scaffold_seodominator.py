import os
import json

base_dir = "/home/hassan/Desktop/Coding/SEODOMINATOR"

steps = [
    {
        "id": 1, 
        "name": "step1_keyword_expansion", 
        "has_llm": True,
        "goal": "Take seed keywords and expand them into related long-tail variants, cluster them, and classify intent (informational, commercial, transactional).",
        "excellence": "Don't just spit out synonyms. Build a strategic topic map. Understand the search intent deeply so we don't write a tutorial when the user wants to buy.",
        "input": "User-provided seed keywords",
        "output": "Ranked keyword clusters with intent labels, volumes, and competition scores."
    },
    {
        "id": 2, 
        "name": "step2_serp_intel", 
        "has_llm": False,
        "goal": "Extract SERP intelligence from Google Ads API (CPC, trends, competition) and recommend the content format.",
        "excellence": "Accurately predict the exact format Google wants to see (listicle, guide, vs-post) and the minimum word count required to compete.",
        "input": "Keyword clusters from Step 1",
        "output": "SERP intel report (format, depth, angle, difficulty)."
    },
    {
        "id": 3, 
        "name": "step3_competitor_analysis", 
        "has_llm": True,
        "goal": "Fetch and deeply analyze the top 5-10 current articles ranking for the target keyword.",
        "excellence": "Find the content gaps. What did everyone else miss? What data is outdated? The output must give our writer the exact blueprint to beat them.",
        "input": "SERP intel from Step 2, Keyword clusters from Step 1",
        "output": "Competitor matrix, content gaps, and beat strategy."
    },
    {
        "id": 4, 
        "name": "step4_content_blueprint", 
        "has_llm": True,
        "goal": "Generate a detailed content outline (H1-H4), target word count, and required data/examples.",
        "excellence": "The outline must be structurally superior to the #1 ranking page. It must answer 'People Also Ask' questions naturally.",
        "input": "Competitor analysis from Step 3, SERP intel from Step 2",
        "output": "Structured JSON blueprint (outline, titles, sections, length)."
    },
    {
        "id": 5, 
        "name": "step5_deep_write", 
        "has_llm": True,
        "goal": "Multi-pass writing of the article: Expert Draft -> Quality Review -> Revision.",
        "excellence": "No AI-fluff. It must sound like a 10-year industry veteran wrote it. Deep, accurate, authoritative, and engaging. 2000-4000+ words.",
        "input": "Content blueprint from Step 4",
        "output": "Final markdown article."
    },
    {
        "id": 6, 
        "name": "step6_seo_optimization", 
        "has_llm": True,
        "goal": "Natural keyword integration, meta descriptions, semantic tags, and schema generation (FAQ, Article).",
        "excellence": "Perfect keyword density without stuffing. Click-optimized meta descriptions that drive insane CTR. Flawless JSON-LD schema.",
        "input": "Markdown article from Step 5, Keyword clusters",
        "output": "SEO-optimized article, meta description, tags, JSON-LD schemas."
    },
    {
        "id": 7, 
        "name": "step7_media_generation", 
        "has_llm": True,
        "goal": "Generate a hero image and 1-2 in-article images/diagrams using visual AI.",
        "excellence": "Images must look professional and custom-made, not generic AI slop. Alt-text must be perfectly keyword-optimized.",
        "input": "SEO-optimized article from Step 6",
        "output": "Image URLs + alt text metadata."
    },
    {
        "id": 8, 
        "name": "step8_internal_linking", 
        "has_llm": True,
        "goal": "Bidirectional internal linking engine. Link this article to old posts, and update old posts to link to this one.",
        "excellence": "The single biggest lever for topical authority. Links must be highly contextual and natural. Anchor text must be varied and relevant.",
        "input": "Article from Step 7, Existing published posts from DB",
        "output": "Article with internal links + list of DB updates for backward links."
    },
    {
        "id": 9, 
        "name": "step9_technical_seo", 
        "has_llm": False,
        "goal": "Build canonical URLs, XML sitemap entries, OG/Twitter tags, and validate heading hierarchy.",
        "excellence": "Zero technical errors. Perfect metadata bundle ready for publishing.",
        "input": "Article and metadata from Step 8",
        "output": "Technical SEO metadata package."
    },
    {
        "id": 10, 
        "name": "step10_publish", 
        "has_llm": False,
        "goal": "Upsert post to Cycolaps Neon DB, upload images, execute backward link updates.",
        "excellence": "Atomic transactions. If backward linking fails, don't corrupt the DB. Robust state management.",
        "input": "Everything from Stages 5-9",
        "output": "Published URL, DB update confirmations."
    },
    {
        "id": 11, 
        "name": "step11_amplify_distribute", 
        "has_llm": True,
        "goal": "Generate highly engaging social snippets (Twitter, LinkedIn, Reddit).",
        "excellence": "Native-feeling content for each platform. Hooks that stop the scroll and drive clicks to the blog.",
        "input": "Published URL, metadata, keywords",
        "output": "Platform-specific social content."
    },
    {
        "id": 12, 
        "name": "step12_track_report", 
        "has_llm": False,
        "goal": "Record post in tracking DB and pull initial baselines from Google Search Console.",
        "excellence": "Provides the feedback loop. We must know exactly where we rank and what our CTR is over time.",
        "input": "Published URL, target keywords",
        "output": "Tracking record created, run summary report."
    }
]

# Project level docs
project_claude = """# SEODOMINATOR

The 12-stage SEO domination pipeline that replaces BridgeMindProject1.
Target: Rank #1 organically for any keyword by generating the most authoritative, comprehensive, and technically perfect content on the web.

## Project Structure
- `src/pipeline/` - Contains the 12 discrete steps of the pipeline. Each step has its own folder.
- `src/api/` - FastAPI dashboard and endpoints.
- `src/storage/` - Neon PostgreSQL DB models and session.
- `src/config/` - Settings and environment variables.

## Getting Started
Agents: Start by reading `DEVPLAN.md` at the root, then navigate to `CONTEXT.md` to understand how to move around the project. 
When working on a specific step, ALWAYS read the `CONTEXT.md` and `DEVPLAN.md` inside that step's folder.
"""

project_devplan = """# SEODOMINATOR Overarching Development Plan

We are building a single-site (Cycolaps) SEO powerhouse that publishes to a Neon Postgres DB.

## Phases of Development
1. **Foundation**: Scaffold the DB schema, `provider.py` (LLM abstraction), and `orchestrator.py`.
2. **Intelligence (Steps 1-4)**: Keyword Expansion, SERP Intel, Competitor Analysis, Content Blueprint.
3. **Content (Steps 5-7)**: Deep Write (Multi-pass), SEO Optimization, Media Generation.
4. **Authority & Tech (Steps 8-9)**: Internal Linking (Bidirectional), Technical SEO.
5. **Publish & Distribute (Steps 10-11)**: Neon Publisher, Social Amplifier.
6. **Feedback Loop (Step 12)**: Google Search Console tracking and reporting.

## Agent Instructions
- Implement one step at a time.
- Ensure the input/output dataclasses between steps are strictly typed.
- Use `src.utils.logger` for all logging.
- Reference `BridgeMindProject1` code where useful (e.g., LLM provider, Image generation), but do not blindly copy it.
"""

project_context = """# Project Navigation Context

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
"""

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

# Scaffold project docs
write_file(os.path.join(base_dir, "CLAUDE.md"), project_claude)
write_file(os.path.join(base_dir, "DEVPLAN.md"), project_devplan)
write_file(os.path.join(base_dir, "CONTEXT.md"), project_context)

# Scaffold step folders
for step in steps:
    step_dir = os.path.join(base_dir, "src", "pipeline", step["name"])
    
    context_md = f"""# CONTEXT: {step['name']}

## Workflow Position
This is **Stage {step['id']}** of the 12-stage SEODOMINATOR pipeline.
- **Input:** {step['input']}
- **Output:** {step['output']}

## Goal
{step['goal']}

## Standard of Excellence
{step['excellence']}

## Agent Instructions
When working on this folder, ensure your code perfectly receives the input from the previous stage and outputs a cleanly typed dataclass/schema for the next stage. Do not bleed responsibilities across stages.
"""
    
    devplan_md = f"""# DEVPLAN: {step['name']}

## Implementation Plan
1. Define the input dataclass (what this step expects).
2. Define the output dataclass (what this step returns).
3. Implement the core logic in `{step['name']}.py`.
4. Ensure robust error handling (e.g., API failures, LLM parsing errors).
5. Add rich logging via `src.utils.logger`.

## Specific Requirements
- Keep the logic strictly scoped to the goal defined in `CONTEXT.md`.
- If using an LLM, load the configuration from `agent_config.json`.
"""

    code_py = f'"""\nImplementation of {step["name"]}.\n"""\n\nimport logging\n\nlogger = logging.getLogger(__name__)\n\nclass {step["name"].replace("_", " ").title().replace(" ", "")}:\n    def __init__(self, settings=None):\n        self.settings = settings\n\n    def run(self, input_data):\n        logger.info(f"Running {step["name"]}...")\n        # TODO: Implement step logic\n        pass\n'

    write_file(os.path.join(step_dir, "CONTEXT.md"), context_md)
    write_file(os.path.join(step_dir, "DEVPLAN.md"), devplan_md)
    write_file(os.path.join(step_dir, f"{step['name']}.py"), code_py)
    
    if step["has_llm"]:
        agent_config = {
            "agent_name": f"{step['name']}_agent",
            "model": "claude-sonnet-4-6",
            "system_prompt": f"You are an elite SEO AI agent specialized in {step['name'].replace('_', ' ')}. Your sole purpose is to {step['goal'].lower()}",
            "skills_required": ["analysis", "seo", "content_creation" if "write" in step["name"] else "strategy"],
            "tools": [],
            "temperature": 0.7 if "write" in step["name"] or "media" in step["name"] else 0.2,
            "max_tokens": 4096,
            "response_format": "json" if "blueprint" in step["name"] or "analysis" in step["name"] else "text"
        }
        write_file(os.path.join(step_dir, "agent_config.json"), json.dumps(agent_config, indent=2))

print("SEODOMINATOR scaffold complete.")
