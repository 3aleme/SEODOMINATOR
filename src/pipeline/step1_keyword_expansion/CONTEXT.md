# CONTEXT: step1_keyword_expansion

## Workflow Position
This is **Stage 1** of the 12-stage SEODOMINATOR pipeline.
- **Input:** User-provided seed keywords
- **Output:** Ranked keyword clusters with intent labels, volumes, and competition scores.

## Goal
Take seed keywords and expand them into related long-tail variants, cluster them, and classify intent (informational, commercial, transactional).

## Standard of Excellence
Don't just spit out synonyms. Build a strategic topic map. Understand the search intent deeply so we don't write a tutorial when the user wants to buy.

## Agent Instructions
When working on this folder, ensure your code perfectly receives the input from the previous stage and outputs a cleanly typed dataclass/schema for the next stage. Do not bleed responsibilities across stages.
