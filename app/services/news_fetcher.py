# app/services/news_fetcher.py

import abc
import threading
import time
from app.utils.logger import get_logger

logger = get_logger(__name__)

class NewsFetcher(abc.ABC):
    def __init__(self):
        self.news_lock = threading.Lock()
        self.cached_articles = []
        self.cache_expiration_time = 3600  # 1 hour in seconds
        self.last_updated = 0

    def is_cache_valid(self):
        current_time = time.time()
        return (self.cached_articles is not None and
                (current_time - self.last_updated) < self.cache_expiration_time)

    @abc.abstractmethod
    def load_cached_articles(self):
        pass

    @abc.abstractmethod
    def save_cached_articles(self, articles):
        pass

    @abc.abstractmethod
    def update_articles(self):
        pass

    @abc.abstractmethod
    def get_cached_articles(self):
        pass

    @abc.abstractmethod
    def fetch_articles(self):
        pass

    @abc.abstractmethod
    def fetch_article_details(self, article_url):
        pass

    @abc.abstractmethod
    def adapt_text_to_level(self, text, level):
        pass

    def format_article_text(self, text: str) -> str:
        """
        Formats the article text into HTML, assuming uppercase lines are headings.
        """
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        formatted_text = ''
        for para in paragraphs:
            if para.isupper():
                formatted_text += f'<h2>{para.title()}</h2>'
            else:
                formatted_text += f'<p>{para}</p>'
        return formatted_text