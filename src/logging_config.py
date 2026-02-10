import logging
import os
import sys


def configure_logging() -> None:
    """Configure root logging for container-friendly stdout output."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )

    # Keep third-party output concise for small-resource deployments.
    for noisy_logger in ("discord", "urllib3", "httpx", "google"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
