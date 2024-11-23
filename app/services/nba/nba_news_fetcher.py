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
import html  # Import html module to unescape HTML entities

logger = get_logger(__name__)

class NBANewsFetcher(NewsFetcher):
    def __init__(self):
        super().__init__()
        self.news_json_path = settings.NEWS_JSON_PATH
        self.cached_articles = self.load_cached_articles()
        self.openai_client = OpenAIClient()
        self.news_lock = threading.Lock()
        self.last_updated = time.time()

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

    def is_cache_valid(self):
        return self.cached_articles and (time.time() - self.last_updated) < 3600

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

    def clean_html_content(self, html_content):
        """
        Cleans the HTML content by removing scripts, styles, and extracting the text content.
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script, style, and other unwanted elements
        for element in soup(['script', 'style', 'noscript', 'header', 'footer', 'nav', 'aside']):
            element.decompose()

        # Get the text content
        text = soup.get_text(separator='\n')

        # Decode HTML entities
        text = html.unescape(text)

        # Normalize whitespace
        lines = [line.strip() for line in text.splitlines()]
        text = '\n'.join(line for line in lines if line)

        return text

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

            # Adapt the title to the desired level
            adapted_title = self.adapt_text_to_level(original_title, 'A1') or original_title

            # Fetch detailed description and image URL
            details = self.fetch_article_details(article_url)
            adapted_teaser = details.get('adapted_description', '')


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

            news_list.append({
                'title': original_title,
                'adapted_title': adapted_title,
                'published_date': time.strftime('%Y-%m-%d'),
                'teaser': '',  # Assuming teaser is not available; set to empty string
                'adapted_teaser': adapted_teaser,
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

        # Clean the HTML content
        cleaned_text = self.clean_html_content(response.content)

        # Create a prompt for the AI model
        prompt = f"""
Dies ist der Text von einer Basketball-Website. Bitte verstehe, was passiert ist, fasse es zusammen und passe es an das deutsche Niveau A1 an. Antworte nur mit dem angepassten Text.

Text:

{cleaned_text}
"""

        # Call the AI model to get the adapted description
        adapted_description = self.openai_client.adapt_text_with_prompt(prompt)

        return {
            'adapted_description': adapted_description
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