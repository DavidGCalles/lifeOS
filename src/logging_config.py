"""
Centralized logging configuration for LifeOS.

Usage:
    from src.logging_config import configure_logging, get_logger
    configure_logging()  # idempotent
    logger = get_logger(__name__)

It reads optional environment variables:
- LOG_LEVEL (e.g., INFO, DEBUG)
- LOG_FORMAT
- LOG_FILE (path to log file, optional)

The function is idempotent (won't reconfigure unless force=True) to make it safe to call from multiple modules/tests.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from typing import Optional

_configured = False


def configure_logging(level: Optional[str | int] = None, log_file: Optional[str] = None, fmt: Optional[str] = None, datefmt: Optional[str] = None, force: bool = False) -> None:
    """Configure root logger once for the application.

    - level: logging level (numeric or string like 'INFO')
    - log_file: optional path to a rotating file handler
    - fmt: log format string
    - datefmt: date format
    - force: if True reconfigures even if already configured
    """
    global _configured
    root = logging.getLogger()

    if _configured and not force:
        # Update level if requested
        if level is not None:
            resolved = _resolve_level(level)
            root.setLevel(resolved)
        return

    # Determine level from env / param
    env_level = os.getenv('LOG_LEVEL') or os.getenv('LOGGING_LEVEL')
    level = level or env_level or 'INFO'
    resolved_level = _resolve_level(level)

    fmt = fmt or os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    datefmt = datefmt or os.getenv('LOG_DATEFMT', '%Y-%m-%d %H:%M:%S')

    # Clear existing handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(stream_handler)

    # Optional file handler
    file_path = log_file or os.getenv('LOG_FILE')
    if file_path:
        fh = logging.handlers.RotatingFileHandler(file_path, maxBytes=10 * 1024 * 1024, backupCount=3)
        fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root.addHandler(fh)

    root.setLevel(resolved_level)

    # Tame noisy libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Convenience wrapper for logging.getLogger."""
    return logging.getLogger(name)


def _resolve_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    try:
        return getattr(logging, str(level).upper())
    except Exception:
        return logging.INFO
