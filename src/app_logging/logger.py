import logging
import sys

from loguru import logger

from src.config import LoggingSettings

_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "{name}:{function}:{line} - {message}"
)


def _stderr_sink(message: str) -> None:
    sys.stderr.write(str(message))


class _LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.opt(exception=record.exc_info).log(
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
        backtrace=False,
        diagnose=False,
    )
    _configure_standard_logging()


_configure_logging(LoggingSettings().LOG_LEVEL)
