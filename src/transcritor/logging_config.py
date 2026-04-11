"""Logging configuration for the transcritor service."""
import logging
import os
import sys


def configure_logging() -> None:
    """Configure logging based on LOG_LEVEL env var.

    Outputs plain text in development, JSON-compatible format in production.
    Call once at application startup (api/app.py lifespan and celery worker init).
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Simple structured format: timestamp | level | logger | message
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
