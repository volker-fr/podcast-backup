"""Logging configuration for podcast backup."""

import logging
import sys


def setup_logger(name="podcast-backup", level=logging.INFO):
    """Set up logger with clean formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Update existing handlers or create new ones
    if logger.handlers:
        # Update level for existing handlers
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger

    # Create console handler with formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Clean format: [LEVEL] message
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


# Default logger instance
logger = setup_logger()
