"""Structured logging via rich — single source of truth for log output."""

import logging
from rich.logging import RichHandler
from rich.console import Console


_console = Console(stderr=True)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a rich-formatted logger for the given module name."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
