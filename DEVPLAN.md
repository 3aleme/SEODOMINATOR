# SEODOMINATOR Overarching Development Plan

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
