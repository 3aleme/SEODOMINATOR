"""Load per-step agent_config.json — the control panel for each pipeline agent."""

import json
import os
from pathlib import Path


def load_agent_config(step_file: str) -> dict:
    """Load agent_config.json from the same directory as the given step file.

    Usage in any pipeline step:
        from src.utils.agent_config import load_agent_config, resolve_model
        _cfg = load_agent_config(__file__)

    Returns an empty dict if the config file is missing.
    """
    config_path = Path(step_file).parent / "agent_config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def resolve_model(cfg: dict, client) -> str:
    """Pick the right model following the precedence: env > config > provider default.

    - LLM_PROVIDER or LLM_MODEL env vars force the provider/model selected by
      get_llm_client — config model is bypassed entirely in that case.
    - Without env overrides, the config's 'model' field controls the model.
    - Falls back to whatever get_llm_client picked if config has no 'model' key.
    """
    if os.getenv("LLM_PROVIDER") or os.getenv("LLM_MODEL"):
        return client.model
    return cfg.get("model", client.model)
