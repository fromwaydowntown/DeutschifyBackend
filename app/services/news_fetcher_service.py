# app/services/news_fetcher_service.py

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_news_fetcher():
    if settings.NEWS_FETCHER == 'nba':
        from app.services.nba_news_fetcher import NBANewsFetcher
        return NBANewsFetcher()
    elif settings.NEWS_FETCHER == 'dw':
        from app.services.dw_news_fetcher import DWNewsFetcher
        return DWNewsFetcher()
    else:
        raise ValueError("Invalid NEWS_FETCHER setting in configuration.")

news_fetcher = get_news_fetcher()