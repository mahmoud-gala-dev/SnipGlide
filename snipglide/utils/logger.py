import logging
from logging.handlers import RotatingFileHandler
from snipglide.core.config import DATA_DIR

def setup_logger():
    log_file = DATA_DIR / "snipglide.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SnipGlide")

logger = setup_logger()
