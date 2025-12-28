"""Structured logging configuration for the CAD-MATLAB Agent"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID


# Context variable for correlation ID (thread-safe across async tasks)
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def __init__(
        self,
        include_correlation_id: bool = True,
        include_timestamps: bool = True,
    ):
        super().__init__()
        self.include_correlation_id = include_correlation_id
        self.include_timestamps = include_timestamps

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.include_timestamps:
            log_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"

        if self.include_correlation_id:
            corr_id = correlation_id_ctx.get()
            if corr_id:
                log_entry["correlation_id"] = corr_id

        # Include extra fields from record
        if hasattr(record, "run_id") and record.run_id:
            log_entry["run_id"] = str(record.run_id)
        if hasattr(record, "state") and record.state:
            log_entry["state"] = record.state
        if hasattr(record, "iteration") and record.iteration is not None:
            log_entry["iteration"] = record.iteration
        if hasattr(record, "extra_data") and record.extra_data:
            log_entry["data"] = record.extra_data

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Text formatter for human-readable logging"""

    def __init__(
        self,
        include_correlation_id: bool = True,
        include_timestamps: bool = True,
    ):
        fmt_parts = []
        if include_timestamps:
            fmt_parts.append("%(asctime)s")
        fmt_parts.append("%(levelname)s")
        fmt_parts.append("[%(name)s]")
        fmt_parts.append("%(message)s")

        super().__init__(" - ".join(fmt_parts))
        self.include_correlation_id = include_correlation_id

    def format(self, record: logging.LogRecord) -> str:
        # Add correlation ID and extra fields to message
        extra_parts = []

        if self.include_correlation_id:
            corr_id = correlation_id_ctx.get()
            if corr_id:
                extra_parts.append(f"[corr_id={corr_id[:8]}]")

        if hasattr(record, "run_id") and record.run_id:
            extra_parts.append(f"[run={str(record.run_id)[:8]}]")
        if hasattr(record, "state") and record.state:
            extra_parts.append(f"[state={record.state}]")
        if hasattr(record, "iteration") and record.iteration is not None:
            extra_parts.append(f"[iter={record.iteration}]")

        if extra_parts:
            record.msg = " ".join(extra_parts) + " " + record.msg

        return super().format(record)


class AgentLogger:
    """Logger with structured context support"""

    def __init__(self, name: str = "agent"):
        self.logger = logging.getLogger(name)
        self._name = name

    def set_correlation_id(self, run_id: UUID) -> None:
        """Set correlation ID for current async context"""
        correlation_id_ctx.set(str(run_id))

    def clear_correlation_id(self) -> None:
        """Clear correlation ID"""
        correlation_id_ctx.set(None)

    def _log(
        self,
        level: int,
        msg: str,
        run_id: Optional[UUID] = None,
        state: Optional[str] = None,
        iteration: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Internal logging method with context fields"""
        extra: Dict[str, Any] = {}
        if run_id:
            extra["run_id"] = run_id
        if state:
            extra["state"] = state
        if iteration is not None:
            extra["iteration"] = iteration
        if extra_data:
            extra["extra_data"] = extra_data

        self.logger.log(level, msg, extra=extra, exc_info=exc_info)

    def info(
        self,
        msg: str,
        run_id: Optional[UUID] = None,
        state: Optional[str] = None,
        iteration: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log info level message"""
        self._log(logging.INFO, msg, run_id, state, iteration, extra_data)

    def warning(
        self,
        msg: str,
        run_id: Optional[UUID] = None,
        state: Optional[str] = None,
        iteration: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log warning level message"""
        self._log(logging.WARNING, msg, run_id, state, iteration, extra_data)

    def error(
        self,
        msg: str,
        run_id: Optional[UUID] = None,
        state: Optional[str] = None,
        iteration: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: bool = True,
    ) -> None:
        """Log error level message with optional exception info"""
        self._log(logging.ERROR, msg, run_id, state, iteration, extra_data, exc_info)

    def debug(
        self,
        msg: str,
        run_id: Optional[UUID] = None,
        state: Optional[str] = None,
        iteration: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log debug level message"""
        self._log(logging.DEBUG, msg, run_id, state, iteration, extra_data)


def setup_logging(config) -> AgentLogger:
    """
    Initialize logging from configuration.

    Args:
        config: Config object with logging configuration

    Returns:
        AgentLogger instance for the application
    """
    log_config = config.logging

    # Get root agent logger
    logger = logging.getLogger("agent")
    logger.setLevel(getattr(logging, log_config.level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Create formatter based on config
    if log_config.format == "json":
        formatter = StructuredFormatter(
            include_correlation_id=log_config.include_correlation_id,
            include_timestamps=log_config.include_timestamps,
        )
    else:
        formatter = TextFormatter(
            include_correlation_id=log_config.include_correlation_id,
            include_timestamps=log_config.include_timestamps,
        )

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_config.file_path:
        file_path = Path(log_config.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return AgentLogger("agent")


def get_logger(name: str = "agent") -> AgentLogger:
    """
    Get logger instance for a module.

    Args:
        name: Logger name (will be prefixed with "agent." if not already)

    Returns:
        AgentLogger instance
    """
    if not name.startswith("agent"):
        name = f"agent.{name}"
    return AgentLogger(name)
