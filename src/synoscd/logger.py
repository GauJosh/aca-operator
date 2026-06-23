# SynosCD Logger Setup
# Structured logging with structlog

import logging
import os
import structlog
from typing import Optional


def setup_logging(log_level: Optional[str] = None, structured: bool = True):
    """Initialize structured logging."""
    effective_log_level = log_level or os.getenv("SYNOSCD_LOG_LEVEL", "WARNING")
    level = getattr(logging, effective_log_level.upper(), logging.WARNING)
    logging.basicConfig(level=level, force=True)

    # Reduce third-party log noise unless debugging explicitly.
    if level > logging.DEBUG:
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("azure.identity").setLevel(logging.WARNING)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
            logging.WARNING
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)

    if structured:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    return structlog.get_logger()


def get_logger(name: Optional[str] = None):
    """Get a logger instance."""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
