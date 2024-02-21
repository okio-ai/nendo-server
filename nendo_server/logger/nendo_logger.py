# -*- encoding: utf-8 -*-
"""The Nendo server logger."""
import logging
import sys


def create_logger(log_level: str = "INFO"):
    logging.basicConfig(
        level=log_level.upper(),
        datefmt="%Y-%m-%dT%H:%M:%S",
        format="[%(asctime)s.%(msecs)03dZ] %(name)s         %(levelname)s %(message)s",
    )

    logger = logging.getLogger(__name__)
    # Set the logger level
    logger.setLevel(logging.getLevelName(log_level.upper()))

    # Create a handler that outputs to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.getLevelName(log_level.upper()))

    # Create a formatter and add it to the handler
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    handler.setFormatter(formatter)

    # Add the handler to your logger
    logger.addHandler(handler)

    return logger
