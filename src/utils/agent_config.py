"""Load per-step agent_config.json — the control panel for each pipeline agent."""

import json
from pathlib import Path


def load_agent_config(step_file: str) -> dict:
    """Load agent_config.json from the same directory as the given step file.

    Usage in any pipeline step:
        from src.utils.agent_config import load_agent_config
        _cfg = load_agent_config(__file__)

    Returns an empty dict if the config file is missing.
    """
    config_path = Path(step_file).parent / "agent_config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)
