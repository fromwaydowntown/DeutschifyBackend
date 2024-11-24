# app/services/nba_news_fetcher.py

from app.services.news_fetcher import NewsFetcher
import requests
from bs4 import BeautifulSoup
from app.services.openai_client import OpenAIClient
import threading
import time
import json
from app.utils.logger import get_logger
from app.config import settings
from pathlib import Path
import re
import html  # Import html module to unescape HTML entities

logger = get_logger(__name__)

class NBANewsFetcher(NewsFetcher):
    def __init__(self):
        super().__init__()
        self.news_json_path = settings.NEWS_JSON_PATH  # Ensure this path is set in settings
        self.cached_articles = self.load_cached_articles()
        self.openai_client = OpenAIClient()

    def load_cached_articles(self):
        with self.news_lock:
            if self.news_json_path.exists():
                with open(self.news_json_path, 'r', encoding='utf-8') as f:
                    news_articles = json.load(f)
                logger.info("Loaded NBA news articles from cache.")
                self.last_updated = time.time()
                return news_articles
            else:
                logger.info("No cached NBA news articles found.")
                return []

    def save_cached_articles(self, articles):
        with self.news_lock:
            with open(self.news_json_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=4)
            self.last_updated = time.time()
            logger.info(f"Saved {len(articles)} NBA news articles to cache.")

    def get_cached_articles(self):
        if self.is_cache_valid():
            logger.info("Using cached NBA news.")
            return self.cached_articles
        else:
            self.update_articles()
            return self.cached_articles

    def update_articles(self):
        logger.info("Fetching new NBA news from Slamdunk website.")
        news_articles = self.fetch_articles()
        if news_articles:
            self.save_cached_articles(news_articles)
            self.cached_articles = news_articles
            logger.info("NBA news articles updated successfully.")
        else:
            logger.warning("No new NBA articles were fetched.")

    def fetch_articles(self):
        url = "https://www.slamdunk.ru/news/nba/"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve NBA news. Error: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        news_list = []

        articles = soup.find_all('article', class_='invisionNews_grid_item')

        for article in articles:
            link_tag = article.find('a', href=True, title=True)
            if not link_tag:
                continue

            original_title = link_tag['title'].strip()
            article_url = link_tag['href']

            # Extract the teaser from the main page
            teaser_section = article.find('section', class_='invisionNews_grid_item__snippet')
            if teaser_section:
                original_teaser = teaser_section.get_text(separator='\n', strip=True)
            else:
                original_teaser = ''
                logger.warning(f"Teaser not found for article: {original_title}")

            # Extract the image URL from the style attribute
            # Use a lambda function to find the div with class containing 'invisionNews_grid_item__image'
            image_div = article.find('div', class_=lambda value: value and 'invisionNews_grid_item__image' in value)
            if image_div and 'style' in image_div.attrs:
                style = image_div['style']
                # Unescape HTML entities in the style attribute
                style_unescaped = html.unescape(style)
                # Extract the URL from the style attribute
                match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style_unescaped)
                if match:
                    image_url = match.group(1)
                    # Ensure the image URL is absolute
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = 'https://www.slamdunk.ru' + image_url
                else:
                    image_url = ''
                    logger.warning(f"Image URL not found in style attribute for article: {original_title}")
            else:
                image_url = ''
                logger.warning(f"Image not found for article: {original_title}")

            # Adapt the title and teaser to A1 level
            adapted_title = self.adapt_text_to_level(original_title, 'A1') or original_title
            adapted_teaser = self.adapt_text_to_level(original_teaser, 'A1') or original_teaser


            news_list.append({
                'title': original_title,
                'adapted_title': adapted_title,
                'published_date': time.strftime('%Y-%m-%d'),
                'teaser': original_teaser,
                'adapted_teaser': adapted_teaser,
                'text': '',  # Will be filled later
                'image_url': image_url,
                'url': article_url,
                'adapted_texts': {}  # Empty dict; full article adaptation happens on demand
            })

        logger.info(f"Fetched {len(news_list)} NBA news articles.")
        return news_list

    def fetch_article_details(self, article_url):
        logger.info(f"Fetching NBA article details from URL: {article_url}")
        try:
            response = requests.get(article_url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve NBA article details. Error: {e}")
            return {}

        soup = BeautifulSoup(response.content, 'html.parser')
        title_meta = soup.find('meta', property='og:title')
        image_meta = soup.find('meta', property='og:image')

        # Extract the article title
        title = title_meta['content'] if title_meta else ''

        # Extract the image URL
        image_url = image_meta['content'] if image_meta else ''

        # Find the main content of the article
        article_body_section = soup.find('section', class_='ipsType_richText ipsType_normal boxed withWidget')
        if not article_body_section:
            # Try alternative selectors if needed
            article_body_section = soup.find('div', class_='article-content')

        if article_body_section:
            # Extract text content
            article_body_text = article_body_section.get_text(separator='\n', strip=True)
            # Extract HTML content if needed
            article_body_html = ''.join(str(element) for element in article_body_section.contents)
        else:
            logger.warning(f"Article body not found for URL: {article_url}")
            article_body_text = ''
            article_body_html = ''

        logger.info(f"Fetched NBA article details: {title}")
        return {
            'title': title,
            'image_url': image_url,
            'article_body_text': article_body_text,
            'article_body_html': article_body_html
        }

    def adapt_text_to_level(self, text, level):
        if not text.strip():
            logger.warning("Empty text provided for adaptation.")
            return ''

        # Proceed with adaptation
        logger.info(f"Adapting text to level {level}.")
        adapted_text = self.openai_client.adapt_text_to_level(text, level)
        if adapted_text:
            logger.info("Text adaptation successful.")
        else:
            logger.error("Text adaptation failed.")
        return adapted_text

    def get_adapted_text(self, article, level, openai_client=None):
        """
        Retrieves adapted text for the article at the specified level, adapting on demand if not cached.
        """
        adapted_texts = article.get('adapted_texts', {})
        if level in adapted_texts:
            logger.info(f"Using cached adapted text for level {level}.")
            return adapted_texts[level]
        else:
            logger.info(f"Adapting full article text to level {level} on demand.")
            adapted_text = self.adapt_text_to_level(article['text'], level)
            if adapted_text:
                adapted_texts[level] = adapted_text
                article['adapted_texts'] = adapted_texts
                # Save updated article to cache
                with self.news_lock:
                    self.save_cached_articles(self.cached_articles)
                return adapted_text
            else:
                logger.error("Failed to adapt text to the specified level.")
                return None