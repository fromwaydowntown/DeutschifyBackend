# app/utils/logger.py
import logging
from app.config import settings

def get_logger(name):
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    )
    logger = logging.getLogger(name)
    return logger