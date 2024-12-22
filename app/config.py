# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

# app/config.py

import os
from pathlib import Path

class Settings:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    WEB_APP_PREFIX = '/app'  # Or your desired prefix
    NEWS_JSON_PATH = Path('news_articles.json')
    NEWS_JSON_PATH_DW = Path('news_articles_dw.json')  # Separate cache for DW news
    PORT = int(os.getenv('PORT', 8080))
    NEWS_FETCHER = os.getenv('NEWS_FETCHER', 'nba')  # 'nba' or 'dw'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')  # Add this line with a default value

settings = Settings()