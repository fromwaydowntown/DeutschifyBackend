import logging
import os
import random
import time  # Add this import for time handling
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
)
from bs4 import BeautifulSoup
import requests
import threading

# Fetch tokens securely from environment variables
openai_api_key = os.environ.get('OPENAI_API_KEY')
telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')

# Initialize FastAPI app
app = FastAPI()

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Telegram bot
updater = Updater(telegram_bot_token, use_context=True)
dispatcher = updater.dispatcher

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Lock for thread safety
news_lock = threading.Lock()

# Cache variables
cache = {
    "nba_news": None,
    "last_updated": 0
}
CACHE_EXPIRATION_TIME = 3600  # 1 hour in seconds

# Telegram conversation states
LEVEL, SELECTING_ARTICLE, ARTICLE_SENT, ANSWERING_QUESTIONS = range(4)


def is_cache_valid():
    current_time = time.time()
    return (cache["nba_news"] is not None and
            (current_time - cache["last_updated"]) < CACHE_EXPIRATION_TIME)


# Fetch NBA news and cache it
def fetch_nba_news():
    with news_lock:
        if is_cache_valid():
            logger.info("Using cached NBA news.")
            return cache["nba_news"]

        logger.info("Fetching NBA news from Slamdunk website.")
        url = "https://www.slamdunk.ru/news/nba/"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve news. Error: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        news_list = []

        articles = soup.find_all('article', class_='invisionNews_grid_item')

        for article in articles:
            link_tag = article.find('a', href=True, title=True)
            if not link_tag:
                continue

            title = link_tag['title'].strip()
            article_url = link_tag['href']

            # Fetch full article details to get the description
            article_details = fetch_article_details(article_url)
            if not article_details:
                continue

            # Adapt the title, description, and body to A1 German
            adapted_title = adapt_text_to_a1_german(article_details['title'])
            adapted_description = adapt_text_to_a1_german(article_details['article_body'])
            adapted_body = adapt_text_to_a1_german(article_details['article_body'])

            news_list.append({
                'title': adapted_title or title,
                'url': article_url,
                'image_url': article_details['image_url'],
                'adapted_body': adapted_body or article_details['article_body'],
                'description': adapted_description or article_details['article_body']
            })

        # Update cache
        cache["nba_news"] = news_list
        cache["last_updated"] = time.time()
        logger.info("NBA news cached.")

        return news_list


# Fetch article details from the detailed page
def fetch_article_details(article_url):
    logger.info(f"Fetching article details from URL: {article_url}")
    try:
        response = requests.get(article_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve article details. Error: {e}")
        return {}

    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.find('meta', property='og:title')['content']
    image_url = soup.find('meta', property='og:image')['content']
    article_body = soup.find('meta', property='og:description')['content']

    logger.info(f"Fetched article details: {title}")
    return {
        'title': title,
        'image_url': image_url,
        'article_body': article_body
    }


# FastAPI Routes
@app.get("/", response_class=RedirectResponse)
async def root():
    logger.info("Root route accessed, redirecting to /app/")
    return RedirectResponse(url="/app/")


@app.get("/app/news", response_class=HTMLResponse)
async def get_nba_news(request: Request):
    logger.info("Fetching NBA news for FastAPI.")

    nba_news = fetch_nba_news()  # Fetch the news

    if not nba_news:
        logger.error("No news articles fetched. Displaying empty news page.")
        return templates.TemplateResponse("news.html", {"request": request, "articles": []})

    return templates.TemplateResponse("nba_news.html", {"request": request, "articles": enumerate(nba_news)})


@app.get("/app/article/{article_id}", response_class=HTMLResponse)
async def get_nba_article_details(request: Request, article_id: int):
    logger.info(f"Fetching details for article {article_id}")

    nba_news = fetch_nba_news()

    if article_id < 0 or article_id >= len(nba_news):
        logger.error(f"Article with ID {article_id} not found.")
        raise HTTPException(status_code=404, detail="Article not found")

    article = nba_news[article_id]

    return templates.TemplateResponse("nba_news_detail.html", {
        "request": request,
        "article_title": article['title'],
        "article_image": article['image_url'],
        "article_content": article['adapted_body'],  # Render the A1 adapted text
        "article_description": article['description']  # Render the A1 adapted description
    })


def adapt_text_to_a1_german(text):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    prompt = (
        f"Bitte passe diesen Text auf das Deutschniveau A1 an:\n\n"
        f"{text}\n\n"
        "Verwende einfache Sätze und vereinfachten Wortschatz."
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
        adapted_text = result['choices'][0]['message']['content'].strip()
        return adapted_text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adapting text to A1 German: {e}")
        return None


# Telegram Bot Commands
def start(update: Update, context: CallbackContext) -> int:
    logger.info("User started the bot.")
    keyboard = [
        [InlineKeyboardButton("📰 Get NBA News", callback_data='get_news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("👋 Welcome to NBA News Bot! Please select an option:", reply_markup=reply_markup)
    return LEVEL


def button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    data = query.data
    query.answer()

    if data == 'get_news':
        logger.info("User requested NBA news.")
        return send_news_list(update, context)
    elif data == 'reset':
        logger.info("User reset the bot.")
        context.user_data.clear()
        query.edit_message_text("🔄 Bot reset. Start again with /start")
        return LEVEL


def send_news_list(update, context) -> int:
    logger.info("Sending NBA news list to user.")
    news_articles = fetch_nba_news()
    if not news_articles:
        update.callback_query.edit_message_text("No news available.")
        logger.warning("No news available to send to user.")
        return LEVEL

    articles_list = "\n".join([f"{idx + 1}. {news['title']}" for idx, news in enumerate(news_articles[:10])])
    message_text = "Select a news article by typing its number:\n\n" + articles_list
    update.callback_query.edit_message_text(message_text)
    return SELECTING_ARTICLE


def select_article(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()
    if not user_input.isdigit():
        update.message.reply_text("Please enter a valid number.")
        return SELECTING_ARTICLE



    idx = int(user_input) - 1
    logger.info(f"User selected article number {idx + 1}")
    nba_news = fetch_nba_news()
    if idx < 0 or idx >= len(nba_news):
        update.message.reply_text("Invalid selection. Try again.")
        logger.warning(f"Invalid article selection: {idx}")
        return SELECTING_ARTICLE

    article_url = nba_news[idx]['url']
    article_details = fetch_article_details(article_url)
    if article_details:
        update.message.reply_text(f"Title: {article_details['title']}\n{article_details['article_body']}")
    else:
        update.message.reply_text("Failed to fetch article details.")
        logger.error(f"Failed to fetch article details for {article_url}.")

    return ARTICLE_SENT