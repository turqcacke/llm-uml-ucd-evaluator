import logging
import sys

from loguru import logger

from src.config import LoggingSettings

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - "
    "<level>{message}</level>"
)


def _stderr_sink(message: str) -> None:
    sys.stderr.write(str(message))


class _LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.log(
            level,
            "[{}] {}",
            record.name,
            record.getMessage(),
        )


def _configure_standard_logging() -> None:
    root_logger = logging.getLogger()
    if not any(
        isinstance(handler, _LoguruHandler)
        for handler in root_logger.handlers
    ):
        root_logger.addHandler(_LoguruHandler())
    root_logger.setLevel(logging.DEBUG)


def _configure_logging(log_level: str) -> None:
    logger.remove()
    logger.add(
        _stderr_sink,
        level=log_level.upper(),
        format=_LOG_FORMAT,
        colorize=sys.stderr.isatty(),
        backtrace=False,
        diagnose=False,
    )
    _configure_standard_logging()


_configure_logging(LoggingSettings().LOG_LEVEL)
