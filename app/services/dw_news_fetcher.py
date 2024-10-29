# app/services/dw_news_fetcher.py

from app.services.news_fetcher import NewsFetcher
import requests
from bs4 import BeautifulSoup
from app.services.openai_client import OpenAIClient
import threading
import time
import json
from app.utils.logger import get_logger
from app.config import settings
import re

logger = get_logger(__name__)

class DWNewsFetcher(NewsFetcher):
    def __init__(self):
        super().__init__()
        self.news_json_path = settings.NEWS_JSON_PATH_DW  # Ensure this path is set in settings
        self.cached_articles = self.load_cached_articles()
        self.openai_client = OpenAIClient()

    def load_cached_articles(self):
        with self.news_lock:
            if self.news_json_path.exists():
                with open(self.news_json_path, 'r', encoding='utf-8') as f:
                    news_articles = json.load(f)
                logger.info("Loaded DW news articles from cache.")
                self.last_updated = time.time()
                return news_articles
            else:
                logger.info("No cached DW news articles found.")
                return []

    def save_cached_articles(self, articles):
        with self.news_lock:
            with open(self.news_json_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=4)
            self.last_updated = time.time()
            logger.info(f"Saved {len(articles)} DW news articles to cache.")

    def get_cached_articles(self):
        if self.is_cache_valid():
            logger.info("Using cached DW news.")
            return self.cached_articles
        else:
            self.update_articles()
            return self.cached_articles

    def update_articles(self):
        logger.info("Fetching new DW news from DW website.")
        news_articles = self.fetch_articles()
        if news_articles:
            self.save_cached_articles(news_articles)
            self.cached_articles = news_articles
            logger.info("DW news articles updated successfully.")
        else:
            logger.warning("No new DW articles were fetched.")

    def fetch_articles(self):
        url = "https://www.dw.com/de/themen/s-9077"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve DW news. Error: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        article_urls = set()

        # Define a regex pattern for article URLs
        article_url_pattern = re.compile(r'^/de/[\w\-/]+/a-\d+$')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if article_url_pattern.match(href):
                full_url = "https://www.dw.com" + href
                article_urls.add(full_url)

        news_list = []

        for article_url in article_urls:
            article_details = self.fetch_article_details(article_url)
            if article_details:
                # Prepare the teaser
                teaser = article_details.get('teaser', article_details['text'][:150])

                # Get or generate published date
                published_date = article_details.get('published_date', time.strftime('%Y-%m-%d'))

                # Adapt the text to A1 level
                adapted_text = self.adapt_text_to_level(article_details['text'], 'A1')

                adapted_texts = {'A1': adapted_text} if adapted_text else {}

                news_list.append({
                    'title': article_details['title'],
                    'published_date': published_date,
                    'teaser': teaser,
                    'text': article_details['text'],
                    'image_url': article_details.get('image_url', ''),
                    'url': article_details.get('url', article_url),
                    'adapted_texts': adapted_texts
                })

        logger.info(f"Fetched {len(news_list)} DW news articles.")
        return news_list

    def fetch_article_details(self, article_url):
        logger.info(f"Fetching DW article details from URL: {article_url}")
        try:
            response = requests.get(article_url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve DW article details. Error: {e}")
            return {}

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract article details
        # For DW, the article content is often in a script tag named "window.__DW_SPT"

        scripts = soup.find_all('script')
        for script in scripts:
            if 'window.__DW_SPT' in script.text:
                app_state_json = self.extract_article_json(script.text)
                if app_state_json:
                    # Navigate the JSON structure to extract article data
                    article_data = self.parse_dw_article_json(app_state_json)

                    if article_data:
                        title = article_data.get('title', '')
                        teaser = article_data.get('teaser', '')
                        text_html = article_data.get('body', '')
                        text = BeautifulSoup(text_html, 'html.parser').get_text(separator='\n')
                        image_url = article_data.get('image_url', '')
                        published_date = article_data.get('date', '')

                        logger.info(f"Fetched DW article details: {title}")

                        return {
                            'title': title,
                            'teaser': teaser,
                            'text': text,
                            'image_url': image_url,
                            'published_date': published_date,
                            'url': article_url
                        }
        logger.error(f"Could not extract article details from {article_url}")
        return {}

    def extract_article_json(self, script_content):
        """
        Extract the JSON data from the script tag containing window.__DW_SPT.
        """
        start_index = script_content.find('window.__DW_SPT = ') + len('window.__DW_SPT = ')
        json_data = script_content[start_index:].strip().rstrip(';')

        try:
            article_json = json.loads(json_data)
            logger.info("Successfully extracted JSON data from window.__DW_SPT")
            return article_json
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return None

    def parse_dw_article_json(self, app_state_json):
        """
        Parse the DW article JSON structure to extract relevant data.
        """
        try:
            # Implement the logic to navigate and extract data from app_state_json
            # This might vary depending on the actual JSON structure
            # Placeholder implementation:

            # Example:
            article_data = app_state_json.get('data', {}).get('article', {})
            return article_data
        except Exception as e:
            logger.error(f"Error parsing article JSON: {e}")
            return None

    def adapt_text_to_level(self, text, level):
        """
        Adapts the text to the specified level using OpenAI's API.
        """
        logger.info(f"Adapting text to level {level}.")
        adapted_text = self.openai_client.adapt_text_to_level(text, level)
        if adapted_text:
            logger.info("Text adaptation successful.")
        else:
            logger.error("Text adaptation failed.")
        return adapted_text

    def get_adapted_text(self, article, level, openai_client=None):
        """
        Retrieves adapted text for the article at the specified level, already adapted during fetching.
        """
        adapted_texts = article.get('adapted_texts', {})
        if level in adapted_texts:
            logger.info(f"Using cached adapted text for level {level}.")
            return adapted_texts[level]
        else:
            logger.warning(f"Adapted text for level {level} not found.")
            return None