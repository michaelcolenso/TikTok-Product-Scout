"""Logging utilities for TikTok Product Scout."""

import logging
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from .config import get_config


def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None):
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
    """
    config = get_config()

    # Remove default handler
    logger.remove()

    # Get log level
    if log_level is None:
        log_level = config.logging.level

    # Console handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # File handler
    if log_file is None:
        log_file = config.logging.file

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
        )

    logger.info(f"Logging initialized at {log_level} level")


def get_logger(name: str):
    """Get logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)
