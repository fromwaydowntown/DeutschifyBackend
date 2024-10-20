import os

import requests
from bs4 import BeautifulSoup
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_general_news():
    """
    Fetch the general news from the main DW Germany news section.
    Extracts article URLs and returns them for detailed fetching.
    """
    url = "https://www.dw.com/en/germany/s-1432"
    logger.info(f"Fetching general news from {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching the main news page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract article URLs from the page
    articles = []
    for link in soup.find_all('a', href=True):
        if '/en/' in link['href'] and '/a-' in link['href']:  # Filter article URLs
            # Ensure the URL is correctly concatenated
            if link['href'].startswith('http'):
                full_url = link['href']
            else:
                full_url = "https://www.dw.com" + link['href']
            articles.append(full_url)
            logger.info(f"Found article URL: {full_url}")

    logger.info(f"Total {len(articles)} articles found.")
    return articles


def extract_article_json(script_content):
    """
    Extract the JSON data from the script tag containing window.__APP_STATE__.
    """
    start_index = script_content.find('window.__APP_STATE__ = ') + len('window.__APP_STATE__ = ')
    json_data = script_content[start_index:].strip().rstrip(';')

    try:
        article_json = json.loads(json_data)
        logger.info("Successfully extracted JSON data from window.__APP_STATE__")
        return article_json
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        return None


def fetch_article_details(article_url):
    """
    Fetch the details for a specific article URL by extracting the JSON-like content from window.__APP_STATE__.
    """
    logger.info(f"Fetching article details for {article_url}")

    try:
        response = requests.get(article_url)
        response.raise_for_status()  # Raise an error for bad responses
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching the article details: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extracting the JSON embedded in the script tag (window.__APP_STATE__)
    scripts = soup.find_all('script')
    for script in scripts:
        if 'window.__APP_STATE__' in script.text:
            app_state_json = extract_article_json(script.text)
            if app_state_json:
                article_key = next((key for key in app_state_json if key.startswith("/graph-api/en/content/article")),
                                   None)
                if article_key and article_key in app_state_json:
                    article_data = app_state_json[article_key]["data"]["content"]
                    article_details = {
                        "title": article_data.get("title", ""),
                        "teaser": article_data.get("teaser", ""),
                        "published_date": article_data.get("localizedContentDate", ""),
                        "text": BeautifulSoup(article_data.get("text", ""), "html.parser").text,
                        "url": article_data.get("canonicalUrl", article_url)
                    }
                    return article_details
            else:
                logger.error(f"Could not find valid article data in {article_url}")

    return None


import requests
import logging

logger = logging.getLogger(__name__)

def adapt_text_to_level(text, level):
    """
    Uses OpenAI to adapt the text to the user's German level (A1, A2, B1, etc.).
    """
    openai_api_key = os.getenv('OPENAI_API_KEY')
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    # Prompt to adapt the text
    prompt = (
        f"Bitte passe diesen Text an das Niveau {level} an:\n\n"
        f"{text}\n\n"
        "Verwende vereinfachte Sätze und reduziere den Wortschatz, wenn nötig."
    )

    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        adapted_text = result['choices'][0]['message']['content']
        return adapted_text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adapting text to level {level}: {e}")
        return text  # Return original text if adaptation fails


def extract_and_fetch_news(user_level):
    """
    Combines the extraction of general news articles and fetching their details.
    The article texts will be adapted based on the user's German level.
    """
    logger.info("Starting the extraction and fetching of news articles.")
    news_articles = []

    # Step 1: Fetch the general news URLs
    article_urls = fetch_general_news()

    # Step 2: For each article URL, fetch its details and add to the list
    for article_url in article_urls:
        details = fetch_article_details(article_url)
        if details:
            # Adapt the text to the user's level
            adapted_text = adapt_text_to_level(details['text'], user_level)
            details['text'] = adapted_text  # Replace the original text with the adapted one
            news_articles.append(details)

    logger.info(f"Total {len(news_articles)} articles successfully fetched and adapted.")
    return news_articles


def save_to_json(data, filename):
    """
    Save the extracted news articles to a JSON file.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)
        logger.info(f"Successfully saved the data to {filename}")
    except Exception as e:
        logger.error(f"Error saving data to JSON file: {e}")


# Execute the process and save results to JSON
if __name__ == '__main__':
    news_articles = extract_and_fetch_news("A1")
    save_to_json(news_articles, 'dw_news_articles_with_details.json')

    # Optional: print some of the data to the console
    for article in news_articles:
        print(f"Title: {article['title']}")
        print(f"Teaser: {article['teaser']}")
        print(f"Published Date: {article['published_date']}")
        print(f"Text: {article['text'][:100]}...")  # Print the first 100 characters of the article text
        print(f"URL: {article['url']}")
        print("-" * 80)