# DEVPLAN: step8_internal_linking

## Implementation Plan
1. Define the input dataclass (what this step expects).
2. Define the output dataclass (what this step returns).
3. Implement the core logic in `step8_internal_linking.py`.
4. Ensure robust error handling (e.g., API failures, LLM parsing errors).
5. Add rich logging via `src.utils.logger`.

## Specific Requirements
- Keep the logic strictly scoped to the goal defined in `CONTEXT.md`.
- If using an LLM, load the configuration from `agent_config.json`.
