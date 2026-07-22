"""Logging configuration — loguru file output with rotation."""
import sys
from loguru import logger
from app.core.config import settings


def setup_logging():
    """Configure loguru: console + file output with rotation."""
    # Remove default stderr handler
    logger.remove()

    # Console output (colored)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # File: all logs, rotated daily, kept 30 days
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="00:00",       # New file at midnight
        retention="30 days",    # Keep 30 days
        compression="gz",       # Compress old logs
        encoding="utf-8",
        enqueue=True,           # Thread-safe writing
    )

    # File: errors only, rotated daily, kept 90 days
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
    )

    logger.info("Logging configured: console + file (30d) + error (90d)")
