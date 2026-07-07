import logging
import os
import sys

# Process-wide log level, e.g. LOG_LEVEL=DEBUG. Defaults to INFO.
_LOG_LEVEL = getattr(
    logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO
)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        logger.setLevel(_LOG_LEVEL)

        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(_LOG_LEVEL)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        # Prevent propagation to root logger to avoid duplicate logs if uvicorn also logs
        logger.propagate = False

    return logger
