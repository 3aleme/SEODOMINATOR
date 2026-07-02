"""Shared LLM prompt templates for all 12 SEODOMINATOR pipeline stages."""

from typing import Dict, List

MODEL = "claude-sonnet-4-6"
CACHING_BETA = "prompt-caching-2024-07-31"

# ── Shared system prompt ──────────────────────────────────────────────────────

SEO_EXPERT_SYSTEM = (
    "You are an elite SEO strategist and content expert with 15+ years of experience "
    "helping brands rank #1 on Google. You combine deep technical SEO knowledge with "
    "exceptional writing ability. You understand search intent at a granular level, "
    "know how to outmaneuver competitor content, and write articles that are genuinely "
    "the most authoritative resource on any topic. You never produce generic AI filler — "
    "every output is strategic, specific, and battle-tested."
)


def make_cache_block(text: str) -> dict:
    """Wrap text in an Anthropic prompt-caching ephemeral content block."""
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


def make_text_block(text: str) -> dict:
    return {"type": "text", "text": text}


# ── Stage 1: Keyword Expansion ────────────────────────────────────────────────

def keyword_intent_classification_prompt(seed_keywords: List[str], keyword_ideas: List[dict]) -> str:
    ideas_text = "\n".join(
        f"- {k['keyword']} (vol: {k['avg_monthly_searches']}, competition: {k['competition']}, trend: {k['trend_score']})"
        for k in keyword_ideas
    )
    return (
        f"Seed keywords: {', '.join(seed_keywords)}\n\n"
        f"Keyword ideas from Google Ads API:\n{ideas_text}\n\n"
        "Your job: build a strategic keyword cluster map.\n\n"
        "For each keyword, classify:\n"
        "- intent: informational | commercial | transactional | navigational\n"
        "- cluster: group related keywords under a primary topic (e.g. 'docker basics', 'docker networking')\n"
        "- opportunity_score: 0-100 based on (high volume × low competition × upward trend)\n"
        "- paa_questions: 1-3 'People Also Ask'-style questions this keyword triggers\n\n"
        "Then identify the TOP 3 keyword clusters to target, ranked by opportunity.\n\n"
        "Return a JSON object:\n"
        "{\n"
        '  "clusters": [\n'
        "    {\n"
        '      "cluster_name": "string",\n'
        '      "primary_keyword": "string",\n'
        '      "supporting_keywords": ["string"],\n'
        '      "intent": "informational|commercial|transactional|navigational",\n'
        '      "opportunity_score": 0-100,\n'
        '      "avg_monthly_searches": int,\n'
        '      "competition": "LOW|MEDIUM|HIGH",\n'
        '      "paa_questions": ["string"]\n'
        "    }\n"
        "  ],\n"
        '  "top_cluster_names": ["string", "string", "string"]\n'
        "}\n"
        "Return ONLY the JSON object, no markdown fences."
    )


# ── Stage 2: SERP Intel ───────────────────────────────────────────────────────

def serp_format_recommendation_prompt(keyword: str, intent: str, competition: str, avg_volume: int) -> str:
    return (
        f"Target keyword: {keyword}\n"
        f"Search intent: {intent}\n"
        f"Competition level: {competition}\n"
        f"Avg monthly searches: {avg_volume}\n\n"
        "Determine the optimal content strategy to rank #1 for this keyword.\n\n"
        "Rules:\n"
        "- 'how to X' / 'X tutorial' / 'X guide' → step-by-step guide\n"
        "- 'best X' / 'top X' / 'X alternatives' → listicle / comparison\n"
        "- 'X vs Y' → comparison article\n"
        "- 'what is X' / 'X explained' / 'X meaning' → explainer / pillar page\n"
        "- commercial/transactional intent → buyer guide\n\n"
        "Estimate minimum word count based on competition:\n"
        "- LOW: 1500-2000\n"
        "- MEDIUM: 2500-3500\n"
        "- HIGH: 3500-5000+\n\n"
        "Return JSON:\n"
        "{\n"
        '  "content_format": "step-by-step guide|listicle|comparison|explainer|buyer guide",\n'
        '  "content_angle": "string (unique angle to take, e.g. beginner-focused, enterprise-grade, 2025 updated)",\n'
        '  "min_word_count": int,\n'
        '  "target_word_count": int,\n'
        '  "difficulty_score": 1-10,\n'
        '  "ranking_rationale": "string (why this format wins for this keyword)"\n'
        "}\n"
        "Return ONLY the JSON object."
    )


# ── Stage 3: Competitor Analysis ──────────────────────────────────────────────

def competitor_article_analysis_prompt(keyword: str, article_text: str, url: str) -> str:
    excerpt = article_text[:3000] if len(article_text) > 3000 else article_text
    return (
        f"Target keyword: {keyword}\n"
        f"Competitor URL: {url}\n\n"
        f"Article content:\n{excerpt}\n\n"
        "Analyze this competitor article. Return JSON:\n"
        "{\n"
        '  "word_count": int,\n'
        '  "heading_structure": ["H1: ...", "H2: ...", "H3: ..."],\n'
        '  "topics_covered": ["string"],\n'
        '  "strengths": ["string"],\n'
        '  "weaknesses": ["string"],\n'
        '  "missing_topics": ["string"],\n'
        '  "data_quality": "poor|adequate|strong",\n'
        '  "content_depth": "shallow|moderate|deep",\n'
        '  "overall_score": 1-10\n'
        "}\n"
        "Return ONLY the JSON object."
    )


def content_gap_analysis_prompt(keyword: str, competitor_analyses: List[dict]) -> str:
    analyses_text = "\n\n".join(
        f"URL: {a['url']}\nStrengths: {a.get('strengths', [])}\nWeaknesses: {a.get('weaknesses', [])}\nMissing: {a.get('missing_topics', [])}"
        for a in competitor_analyses
    )
    return (
        f"Target keyword: {keyword}\n\n"
        f"Competitor analysis results:\n{analyses_text}\n\n"
        "Synthesize a content gap analysis and beat strategy. Return JSON:\n"
        "{\n"
        '  "universal_gaps": ["topics nobody covers well"],\n'
        '  "outdated_info": ["claims/stats that are likely stale"],\n'
        '  "beat_strategy": "string (2-3 sentences: exactly how to write a superior article)",\n'
        '  "unique_angles": ["angles no competitor has taken"],\n'
        '  "must_include_sections": ["section names that every top article has"],\n'
        '  "differentiators": ["things we can do that they cannot"]\n'
        "}\n"
        "Return ONLY the JSON object."
    )


# ── Stage 4: Content Blueprint ────────────────────────────────────────────────

def content_blueprint_prompt(
    primary_keyword: str,
    supporting_keywords: List[str],
    paa_questions: List[str],
    serp_intel: dict,
    gap_analysis: dict,
) -> str:
    return (
        f"Primary keyword: {primary_keyword}\n"
        f"Supporting keywords: {', '.join(supporting_keywords)}\n"
        f"People Also Ask questions: {', '.join(paa_questions)}\n"
        f"Content format: {serp_intel.get('content_format', 'guide')}\n"
        f"Target word count: {serp_intel.get('target_word_count', 3000)}\n"
        f"Content angle: {serp_intel.get('content_angle', '')}\n"
        f"Beat strategy: {gap_analysis.get('beat_strategy', '')}\n"
        f"Universal gaps to fill: {', '.join(gap_analysis.get('universal_gaps', []))}\n"
        f"Must-include sections: {', '.join(gap_analysis.get('must_include_sections', []))}\n\n"
        "Create a detailed content blueprint that is structurally superior to the #1 ranking page.\n\n"
        "Requirements:\n"
        "- 3-5 title candidates (compelling, include primary keyword, 50-60 chars each)\n"
        "- Full heading hierarchy: H1 → H2 → H3 (go 3-4 levels deep where needed)\n"
        "- Under each H2: list 3-5 key points to cover\n"
        "- A dedicated FAQ section using the PAA questions\n"
        "- Required data/stats/examples to source for each major section\n"
        "- Estimated word count per section\n\n"
        "Return JSON:\n"
        "{\n"
        '  "title_candidates": [\n'
        '    {"title": "string", "click_appeal_score": 1-10, "rationale": "string"}\n'
        "  ],\n"
        '  "recommended_title": "string",\n'
        '  "meta_description_hint": "string (key benefit to emphasize, 1 sentence)",\n'
        '  "outline": [\n'
        '    {\n'
        '      "level": "H1|H2|H3|H4",\n'
        '      "heading": "string",\n'
        '      "key_points": ["string"],\n'
        '      "required_data": ["string"],\n'
        '      "estimated_words": int\n'
        "    }\n"
        "  ],\n"
        '  "faq_section": [\n'
        '    {"question": "string", "answer_hint": "string"}\n'
        "  ],\n"
        '  "target_word_count": int,\n'
        '  "unique_angle": "string"\n'
        "}\n"
        "Return ONLY the JSON object."
    )


# ── Stage 5: Deep Write ───────────────────────────────────────────────────────

def deep_write_pass1_prompt(blueprint: dict, keyword: str, supporting_keywords: List[str]) -> str:
    outline_text = "\n".join(
        f"{'  ' * (['H1','H2','H3','H4'].index(s['level']) if s['level'] in ['H1','H2','H3','H4'] else 0)}"
        f"{s['level']}: {s['heading']} (~{s.get('estimated_words', 200)} words)\n"
        f"  Points: {', '.join(s.get('key_points', []))}"
        for s in blueprint.get("outline", [])
    )
    faq_text = "\n".join(
        f"Q: {f['question']}" for f in blueprint.get("faq_section", [])
    )
    return (
        f"Title: {blueprint.get('recommended_title', keyword)}\n"
        f"Primary keyword: {keyword}\n"
        f"Supporting keywords: {', '.join(supporting_keywords)}\n"
        f"Target word count: {blueprint.get('target_word_count', 3000)}\n"
        f"Unique angle: {blueprint.get('unique_angle', '')}\n\n"
        f"Content outline:\n{outline_text}\n\n"
        f"FAQ questions to answer:\n{faq_text}\n\n"
        "Write the complete expert article following this blueprint exactly.\n\n"
        "Requirements:\n"
        "- Sound like a 10-year industry veteran who has actually done this, not a content mill\n"
        "- Every H2 and H3 must be fully written (no placeholders)\n"
        "- Include real, specific examples, numbers, and comparisons\n"
        "- Integrate keywords naturally — never stuff\n"
        "- The FAQ section must appear near the end with complete answers\n"
        "- Format in Markdown with proper heading hierarchy\n"
        "- Write at least the target word count\n\n"
        "Write the full article now:"
    )


def deep_write_pass2_review_prompt(draft: str, blueprint: dict, keyword: str) -> str:
    outline_headings = [s['heading'] for s in blueprint.get("outline", [])]
    return (
        f"Keyword: {keyword}\n"
        f"Required outline headings: {', '.join(outline_headings)}\n\n"
        f"Draft to review:\n{draft}\n\n"
        "You are a senior editor reviewing this draft before publication.\n"
        "Assess ruthlessly on these axes:\n\n"
        "1. COMPLETENESS: Are all outline sections present and fully written?\n"
        "2. DEPTH: Is any section shallow or generic? Where does it need more specificity?\n"
        "3. ACCURACY: Are there claims that seem vague, outdated, or unsupported?\n"
        "4. READABILITY: Passive voice overuse? Awkward transitions? Repetitive phrases?\n"
        "5. SEO: Is the primary keyword appearing naturally 8-12 times? Supporting keywords used?\n"
        "6. COMPETITOR BEAT: Does this actually surpass what a top Google result would contain?\n\n"
        "Return JSON with specific revision instructions:\n"
        "{\n"
        '  "overall_quality": 1-10,\n'
        '  "passes_bar": true|false,\n'
        '  "revision_instructions": [\n'
        '    {"section": "heading or area", "issue": "string", "fix": "string"}\n'
        "  ],\n"
        '  "missing_sections": ["string"],\n'
        '  "weak_sections": ["string"],\n'
        '  "keyword_density_ok": true|false,\n'
        '  "estimated_word_count": int\n'
        "}\n"
        "Return ONLY the JSON object."
    )


def deep_write_pass3_revision_prompt(draft: str, review: dict) -> str:
    instructions_text = "\n".join(
        f"- [{r['section']}] {r['issue']} → Fix: {r['fix']}"
        for r in review.get("revision_instructions", [])
    )
    missing = ", ".join(review.get("missing_sections", []))
    return (
        f"Revision instructions:\n{instructions_text}\n"
        + (f"\nMissing sections to add: {missing}\n" if missing else "")
        + f"\nOriginal draft:\n{draft}\n\n"
        "Apply all revision instructions above. Produce the final, publication-ready version.\n"
        "- Fix every identified issue\n"
        "- Add all missing sections in the correct position\n"
        "- Do NOT change what is already working well\n"
        "- Return the complete revised article in Markdown, nothing else."
    )


# ── Stage 6: SEO Optimization ─────────────────────────────────────────────────

def seo_optimization_prompt(content: str, primary_keyword: str, supporting_keywords: List[str]) -> str:
    return (
        f"Primary keyword: {primary_keyword}\n"
        f"Supporting keywords: {', '.join(supporting_keywords)}\n\n"
        f"Article to optimize:\n{content}\n\n"
        "Perform full SEO optimization. Return JSON:\n"
        "{\n"
        '  "optimized_content": "full article with natural keyword integration",\n'
        '  "seo_title": "50-60 chars, primary keyword included, compelling",\n'
        '  "meta_description": "150-160 chars, primary keyword, strong CTA, makes people click",\n'
        '  "seo_tags": ["tag1", "tag2", ...],\n'
        '  "keyword_density": float,\n'
        '  "faq_schema": [\n'
        '    {"question": "string", "answer": "string"}\n'
        "  ],\n"
        '  "article_schema": {\n'
        '    "headline": "string",\n'
        '    "description": "string",\n'
        '    "keywords": ["string"]\n'
        "  }\n"
        "}\n\n"
        "Rules:\n"
        "- Keyword density target: 1.0-2.0% (count occurrences / total words)\n"
        "- Never add keywords where they sound unnatural\n"
        "- Generate 5-10 tags: mix of exact-match, long-tail, and semantic variations\n"
        "- Meta description must be 150-160 chars exactly and drive clicks\n"
        "- FAQ schema must include ALL FAQ questions from the article\n"
        "Return ONLY the JSON object."
    )


# ── Stage 7: Media Generation ─────────────────────────────────────────────────

def hero_image_prompt_gen(title: str, primary_keyword: str, content_excerpt: str) -> str:
    excerpt = content_excerpt[:500] if len(content_excerpt) > 500 else content_excerpt
    return (
        f"Article title: {title}\n"
        f"Primary keyword: {primary_keyword}\n"
        f"Content excerpt: {excerpt}\n\n"
        "Write a detailed image generation prompt for a professional hero/featured image.\n\n"
        "Requirements:\n"
        "- Visually represents the article topic with authority and professionalism\n"
        "- Clean, modern aesthetic — NOT stock-photo generic\n"
        "- NO text, words, letters, or numbers in the image\n"
        "- Specify: subject, composition, lighting, color palette, mood, photographic style\n"
        "- Suitable for a tech/business blog (Cycolaps)\n"
        "- 16:9 aspect ratio composition\n\n"
        "Return ONLY the image prompt text, nothing else."
    )


def in_article_image_prompt_gen(section_heading: str, section_content: str, primary_keyword: str) -> str:
    excerpt = section_content[:400] if len(section_content) > 400 else section_content
    return (
        f"Article section: {section_heading}\n"
        f"Section content: {excerpt}\n"
        f"Primary keyword: {primary_keyword}\n\n"
        "Write a detailed image generation prompt for an in-article diagram or illustration.\n\n"
        "Requirements:\n"
        "- Visually explains or reinforces the concept in this section\n"
        "- Infographic or diagram style preferred (clean, educational)\n"
        "- NO decorative or generic imagery — must add informational value\n"
        "- NO text in image\n"
        "- Specify: visual concept, layout, color scheme, illustration style\n\n"
        "Return ONLY the image prompt text."
    )


def image_alt_text_prompt(image_description: str, section_context: str, keywords: List[str]) -> str:
    return (
        f"Image description/prompt used: {image_description}\n"
        f"Section context: {section_context}\n"
        f"Target keywords: {', '.join(keywords)}\n\n"
        "Write SEO-optimized alt text for this image.\n"
        "Rules:\n"
        "- 8-12 words maximum\n"
        "- Describe what the image actually shows\n"
        "- Include primary keyword naturally if it fits\n"
        "- No 'image of' or 'photo of' prefix\n\n"
        "Return ONLY the alt text string."
    )


# ── Stage 8: Internal Linking ─────────────────────────────────────────────────

def forward_link_injection_prompt(new_article: str, existing_posts: List[dict]) -> str:
    posts_text = "\n".join(
        f"- slug: {p['slug']} | title: {p['title']} | excerpt: {p.get('excerpt', '')[:100]}"
        for p in existing_posts
    )
    return (
        f"New article content:\n{new_article[:4000]}\n\n"
        f"Existing published posts (potential link targets):\n{posts_text}\n\n"
        "Find 3-5 natural places in the new article to link to existing posts.\n\n"
        "Rules:\n"
        "- Links must be highly contextual — the anchor text must naturally flow in the sentence\n"
        "- Anchor text should be descriptive (not 'click here' or 'read more')\n"
        "- Only link where it genuinely helps the reader\n"
        "- Vary anchor text — no two links should use identical phrasing\n\n"
        "Return JSON:\n"
        "{\n"
        '  "forward_links": [\n'
        "    {\n"
        '      "target_slug": "string",\n'
        '      "anchor_text": "string",\n'
        '      "sentence_context": "the full sentence where the link appears",\n'
        '      "replacement_sentence": "same sentence with [anchor_text](url) inserted"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Return ONLY the JSON object."
    )


def backward_link_injection_prompt(new_article_title: str, new_article_slug: str, new_article_excerpt: str, existing_post: dict) -> str:
    post_excerpt = existing_post.get("content", "")[:3000]
    return (
        f"New article being published:\n"
        f"  Title: {new_article_title}\n"
        f"  Slug: {new_article_slug}\n"
        f"  Summary: {new_article_excerpt}\n\n"
        f"Existing post to scan for linking opportunities:\n"
        f"  Title: {existing_post.get('title', '')}\n"
        f"  Slug: {existing_post.get('slug', '')}\n"
        f"  Content: {post_excerpt}\n\n"
        "Find 0-2 places in the existing post where a link to the new article would be natural and helpful.\n"
        "Only suggest links where the anchor text fits seamlessly — never force it.\n\n"
        "Return JSON:\n"
        "{\n"
        '  "backward_links": [\n'
        "    {\n"
        '      "anchor_text": "string",\n'
        '      "original_sentence": "the exact sentence as it appears in the post",\n'
        '      "replacement_sentence": "sentence with link injected in markdown",\n'
        '      "paragraph_hint": "first few words of the paragraph containing this sentence"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Return ONLY the JSON object. Return empty backward_links array if no natural fit exists."
    )


# ── Stage 9: Technical SEO ────────────────────────────────────────────────────
# Stage 9 is logic-only (no LLM calls needed).


# ── Stage 11: Amplify & Distribute ───────────────────────────────────────────

def social_post_prompt(platform: str, title: str, published_url: str, keywords: List[str], excerpt: str) -> str:
    specs: Dict[str, str] = {
        "twitter": (
            "Max 280 characters total including the URL. "
            "Use 2-3 relevant hashtags. Be punchy and drive clicks. Hook in the first line."
        ),
        "linkedin": (
            "Professional, insight-driven. 150-200 words. "
            "Strong opening hook, share a key takeaway, invite engagement. "
            "End with 3-5 industry hashtags."
        ),
        "reddit": (
            "Community-first, zero self-promotion vibe. "
            "Post title under 100 chars. Body paragraph adds genuine value. "
            "No hashtags. Include the URL naturally."
        ),
        "bluesky": (
            "Max 300 characters. Casual and engaging. "
            "1-2 hashtags. Similar energy to Twitter but slightly more conversational."
        ),
    }
    spec = specs.get(platform.lower(), "150-200 words, professional and engaging.")
    content_hint = excerpt[:300] if len(excerpt) > 300 else excerpt
    return (
        f"Article title: {title}\n"
        f"Article URL: {published_url}\n"
        f"Keywords: {', '.join(keywords)}\n"
        f"Article summary: {content_hint}\n"
        f"Platform: {platform.upper()}\n"
        f"Requirements: {spec}\n\n"
        f"Write a native-feeling {platform} post that stops the scroll and drives clicks. "
        "Return ONLY the post text."
    )


def newsletter_snippet_prompt(title: str, content: str, published_url: str) -> str:
    excerpt = content[:800] if len(content) > 800 else content
    return (
        f"Article title: {title}\n"
        f"Article URL: {published_url}\n"
        f"Content excerpt: {excerpt}\n\n"
        "Write a 'key takeaways' newsletter snippet (3-5 bullet points) that makes subscribers "
        "want to read the full article. Each bullet should be a specific, actionable insight.\n"
        "Return ONLY the snippet text in markdown bullet format."
    )
