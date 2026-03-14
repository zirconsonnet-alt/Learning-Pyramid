from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from desktop_agent.config_store import ConfigStore


LOGGER_NAME = "learningpyramid.desktop_agent"
_CONFIGURED_LOG_PATH: str | None = None


def get_desktop_agent_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{str(name).strip('.')}")


def configure_desktop_agent_logging(base_dir: Path | str | None = None) -> Path:
    global _CONFIGURED_LOG_PATH

    store = ConfigStore(base_dir)
    log_path = store.log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_log_path = str(log_path.resolve())
    logger = get_desktop_agent_logger()
    logger.setLevel(getattr(logging, str(os.getenv("PLM_AGENT_LOG_LEVEL") or "INFO").strip().upper(), logging.INFO))
    logger.propagate = False

    if _CONFIGURED_LOG_PATH == resolved_log_path:
        return log_path

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    _CONFIGURED_LOG_PATH = resolved_log_path
    logger.info("desktop_agent_logging_configured log_path=%s", resolved_log_path)
    return log_path
