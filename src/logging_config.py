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
import asyncio

_configured = False

def _handle_async_exception(loop, context):
    """
    Custom exception handler for asyncio to suppress benign BlockingIOErrors.
    These errors are noise from gRPC/uvloop during ungraceful shutdowns of tools.
    """
    exception = context.get("exception")
    
    # We are only interested in suppressing the specific "Resource temporarily unavailable" error.
    if isinstance(exception, BlockingIOError) and "Resource temporarily unavailable" in str(context.get("message", "")):
        # Log it at a DEBUG level for inspection but otherwise ignore it.
        logging.getLogger("asyncio").debug(f"Suppressing known gRPC BlockingIOError: {context.get('message')}")
    else:
        # For all other exceptions, use the default handler to ensure they are logged.
        logging.getLogger("asyncio").error(f"Unhandled asyncio error: {context.get('message')}", exc_info=exception)

def install_grpc_noise_filter(loop: asyncio.AbstractEventLoop):
    """
    Sets the custom exception handler for the given asyncio event loop
    to suppress benign gRPC BlockingIOErrors.
    """
    try:
        loop.set_exception_handler(_handle_async_exception)
        logging.getLogger(__name__).info("✅ Custom asyncio exception handler installed.")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not install asyncio exception handler: {e}")


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

    # Tame noisy libraries (ej. httpcore/x)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    
    # FIX: Tame noisy gRPC library logs
    logging.getLogger("grpc").setLevel(logging.WARNING)

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
