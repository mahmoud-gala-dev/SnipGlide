import logging
from snipglide.core.config import DATA_DIR

def setup_logger():
    log_file = DATA_DIR / "snipglide.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SnipGlide")

logger = setup_logger()
