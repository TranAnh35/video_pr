# config/logging_setup.py

import logging
import sys

def setup_logging():
    """
    Configure logging system for the entire application.
    """
    if logging.root.handlers:
        return logging.getLogger()

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(asctime)s: %(name)s: %(message)s',
        stream=sys.stdout
    )

    logging.getLogger('pyscenedetect').setLevel(logging.DEBUG)

    return logging.getLogger()

if __name__ == '__main__':
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Logging setup complete.")
    logger.debug("This is a debug message.")
    logger.warning("This is a warning message.")