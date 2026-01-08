import sys
from pathlib import Path

from loguru import logger


def setup_logger() -> None:
    # Remove default handler
    logger.remove()

    # Sink 1: Stdout (Human-readable)
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Ensure logs directory exists
    log_path = Path("logs")
    if not log_path.exists():
        log_path.mkdir(parents=True, exist_ok=True)

    # Sink 2: File (JSON, Rotation, Retention)
    logger.add(
        "logs/app.log",
        rotation="500 MB",
        retention="10 days",
        serialize=True,
        enqueue=True,
        level="INFO",
    )


setup_logger()

__all__ = ["logger", "setup_logger"]
