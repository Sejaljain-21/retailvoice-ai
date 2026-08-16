"""Structured logging setup shared by the API, the agent and the WS layer."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


class _ColourFormatter(logging.Formatter):
    COLOURS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self.COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname:<8}{self.RESET}"
        return super().format(record)


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _ColourFormatter("%(asctime)s %(levelname)s %(name)s | %(message)s", "%H:%M:%S")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Third-party noise reduction
    for noisy in ("httpx", "httpcore", "anthropic", "asyncio", "multipart",
                  "aiosqlite", "asyncpg", "watchfiles", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
