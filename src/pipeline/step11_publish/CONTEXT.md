# CONTEXT: step10_publish

## Workflow Position
This is **Stage 10** of the 12-stage SEODOMINATOR pipeline.
- **Input:** Everything from Stages 5-9
- **Output:** Published URL, DB update confirmations.

## Goal
Upsert post to Cycolaps Neon DB, upload images, execute backward link updates.

## Standard of Excellence
Atomic transactions. If backward linking fails, don't corrupt the DB. Robust state management.

## Agent Instructions
When working on this folder, ensure your code perfectly receives the input from the previous stage and outputs a cleanly typed dataclass/schema for the next stage. Do not bleed responsibilities across stages.
