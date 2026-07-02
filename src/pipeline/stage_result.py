from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageResult:
    """Wraps a pipeline stage return value with token usage metadata."""
    value: Any
    tokens_in: int = 0
    tokens_out: int = 0
