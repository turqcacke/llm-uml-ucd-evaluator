import sys

from loguru import logger

from src.config import LoggingSettings

_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "{name}:{function}:{line} - {message}"
)


def _stderr_sink(message: str) -> None:
    sys.stderr.write(str(message))


def _configure_logging(log_level: str) -> None:
    logger.remove()
    logger.add(
        _stderr_sink,
        level=log_level.upper(),
        format=_LOG_FORMAT,
        backtrace=False,
        diagnose=False,
    )


_configure_logging(LoggingSettings().LOG_LEVEL)
