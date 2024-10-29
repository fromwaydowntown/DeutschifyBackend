# app/bot/utils.py
import os
import random
import shutil
import tempfile
import json
import datetime
from app.services.audio_generator import AudioGenerator
from app.services.openai_client import OpenAIClient
from app.services.news_fetcher import NewsFetcher
from app.models.news import NewsArticle
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# This file can include additional utility functions if needed.
# Since most utilities have been integrated into services, it may remain empty for now.