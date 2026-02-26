"""Logging module for the web browsing MCP server."""

import logging
import os
from typing import Optional

# Log format: timestamp | level | module | message
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default log level
DEFAULT_LOG_LEVEL = "INFO"


def setup_logging(log_level: Optional[str] = None) -> None:
    """Set up logging configuration.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to WEB_MCP_LOG_LEVEL env var or INFO.
    """
    if log_level is None:
        log_level = os.environ.get("WEB_MCP_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    
    # Convert to uppercase
    log_level = log_level.upper()
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_health_metrics() -> dict:
    """Get health metrics for the /health endpoint.
    
    Returns:
        Dictionary with health metrics
    """
    # These will be implemented in the server module
    return {
        "status": "healthy",
        "cache_hit_rate": 0.0,
        "request_count": 0,
        "uptime_seconds": 0,
    }
