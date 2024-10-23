import logging
import os
import random
import json
import datetime
import tempfile
import requests
from bs4 import BeautifulSoup
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import threading
import json
import shutil


# Fetch tokens securely from environment variables
openai_api_key = os.environ.get('OPENAI_API_KEY')
telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')


# Initialize FastAPI app
app = FastAPI()
updater = Updater(telegram_bot_token, use_context=True)
dispatcher = updater.dispatcher

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Define conversation states
LEVEL, SELECTING_ARTICLE, ARTICLE_SENT, ANSWERING_QUESTIONS = range(4)

# Define voice lists based on gender (replace with actual voices if needed)
male_voices = ['alloy', 'onyx']
female_voices = ['echo', 'fable', 'nova', 'shimmer']

# Path to the JSON file where news articles will be saved
NEWS_JSON_PATH = Path("news_articles.json")


# Threading lock for thread safety
news_lock = threading.Lock()

# Prefix for web app routes
WEB_APP_PREFIX = '/app'

# FastAPI Routes
@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/app/")

@app.get(f"{WEB_APP_PREFIX}/", response_class=HTMLResponse)
async def index(request: Request):
    with news_lock:
        if NEWS_JSON_PATH.exists():
            with open(NEWS_JSON_PATH, 'r', encoding='utf-8') as f:
                news_articles = json.load(f)
        else:
            news_articles = []

    return templates.TemplateResponse("news.html", {"request": request, "articles": enumerate(news_articles)})

@app.get(f"{WEB_APP_PREFIX}/article/{{article_id}}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int):
    with news_lock:
        if NEWS_JSON_PATH.exists():
            with open(NEWS_JSON_PATH, 'r', encoding='utf-8') as f:
                news_articles = json.load(f)
        else:
            news_articles = []

    if 0 <= article_id < len(news_articles):
        article = news_articles[article_id]

        # Format the article text into HTML
        article_text = article['text']
        paragraphs = [p.strip() for p in article_text.split('\n') if p.strip()]
        formatted_text = ''
        for para in paragraphs:
            if para.isupper():
                # Assume uppercase lines are headings
                formatted_text += f'<h2>{para.title()}</h2>'
            else:
                formatted_text += f'<p>{para}</p>'

        # Check if audio is available (original)
        audio_file_path = f"static/audio/article_{article_id}_original.mp3"
        if os.path.exists(audio_file_path):
            audio_available = True
            audio_url = f"/{audio_file_path}"
        else:
            audio_available = False
            audio_url = None

        return templates.TemplateResponse(
            "news_detail.html",
            {
                "request": request,
                "article": article,
                "formatted_text": formatted_text,
                "article_id": article_id,
                "audio_available": audio_available,
                "audio_url": audio_url
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Article not found")

@app.post(f"{WEB_APP_PREFIX}/article/{{article_id}}/adapt")
async def adapt_article_text(article_id: int, request: Request):
    data = await request.json()
    level = data.get('level')

    if not level:
        return JSONResponse({'status': 'error', 'message': 'Level not specified'}, status_code=400)

    with news_lock:
        if NEWS_JSON_PATH.exists():
            with open(NEWS_JSON_PATH, 'r', encoding='utf-8') as f:
                news_articles = json.load(f)
        else:
            news_articles = []

        if 0 <= article_id < len(news_articles):
            article = news_articles[article_id]
            adapted_texts = article.get('adapted_texts', {})
            if level in adapted_texts:
                adapted_text = adapted_texts[level]
            else:
                original_text = article['text']
                adapted_text = adapt_text_to_level(original_text, level)
                if adapted_text:
                    adapted_texts[level] = adapted_text
                    article['adapted_texts'] = adapted_texts

                    with open(NEWS_JSON_PATH, 'w', encoding='utf-8') as f:
                        json.dump(news_articles, f, ensure_ascii=False, indent=4)
                else:
                    return JSONResponse({'status': 'error', 'message': 'Error adapting text'}, status_code=500)

            # Format the adapted text into HTML
            paragraphs = [p.strip() for p in adapted_text.split('\n') if p.strip()]
            formatted_adapted_text = ''
            for para in paragraphs:
                if para.isupper():
                    formatted_adapted_text += f'<h2>{para.title()}</h2>'
                else:
                    formatted_adapted_text += f'<p>{para}</p>'

            return JSONResponse({'status': 'success', 'adapted_text': formatted_adapted_text})
        else:
            raise HTTPException(status_code=404, detail="Article not found")
# Updated /play endpoint to generate audio from provided text

# Updated /play endpoint to generate audio from provided text
@app.post(f"{WEB_APP_PREFIX}/play")
async def generate_audio(request: Request):
    data = await request.json()
    text = data.get('text', '')
    voice = data.get('voice', random.choice(female_voices + male_voices))  # Optional: specify voice

    if not text:
        return JSONResponse({'status': 'error', 'message': 'Text not provided'}, status_code=400)

    # Generate audio
    logger.info("Generating audio for provided text.")
    temp_audio_path = generate_audio_content(text, voice)

    if temp_audio_path:
        # Generate unique audio file name to prevent caching
        unique_suffix = random.randint(1000, 9999)
        audio_file_path = f"static/audio/audio_{unique_suffix}.mp3"
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        try:
            shutil.move(temp_audio_path, audio_file_path)
            logger.info(f"Audio file saved at {audio_file_path}")
            audio_url = f"/{audio_file_path}"
            return JSONResponse({'status': 'success', 'audio_url': audio_url})
        except Exception as e:
            logger.error(f"Failed to move audio file: {e}")
            return JSONResponse({'status': 'error', 'message': 'Failed to save audio file'}, status_code=500)
    else:
        logger.error("Failed to generate audio")
        return JSONResponse({'status': 'error', 'message': 'Audio generation failed'}, status_code=500)

# Helper functions
def send_message(update: Update, context: CallbackContext, text: str, reply_markup=None):
    if update.message:
        update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

def safe_edit_message_text(update: Update, context: CallbackContext, text, reply_markup=None):
    try:
        if update.callback_query and update.callback_query.message:
            update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

def safe_edit_message_text(update: Update, context: CallbackContext, text, reply_markup=None):
    try:
        if update.callback_query and update.callback_query.message:
            update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

def safe_edit_message_text(update: Update, context: CallbackContext, text, reply_markup=None):
    try:
        if update.callback_query and update.callback_query.message:
            update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

# Start function
def start(update: Update, context: CallbackContext) -> int:
    logger.info("User started the bot.")
    # Load news articles from disk or fetch if not available
    update_news_articles(context)
    keyboard = [
        [InlineKeyboardButton("📰 Nachrichten", callback_data='news')],
        [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
        [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "👋 Willkommen zum Deutsch Lern Bot! Bitte wähle eine Option:", reply_markup=reply_markup)
    return LEVEL

def button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    data = query.data
    logger.info(f"Button clicked: {data}")
    query.answer()

    if data == 'start':
        return start(update, context)
    elif data == 'change_level':
        return ask_level(update, context)
    elif data == 'reset':
        context.user_data.clear()
        logger.info("User reset the bot.")
        safe_edit_message_text(update, context, "🔄 Bot wurde zurückgesetzt. Bitte starte erneut.")
        return start(update, context)
    elif data == 'news':
        return show_news_list(update, context)
    elif data in ['get_questions', 'show_text', 'check_vocabulary', 'review_vocabulary', 'check_answers']:
        # Existing handlers
        if data == 'get_questions':
            return send_questions(update, context)
        elif data == 'show_text':
            return send_text(update, context)
        elif data == 'check_vocabulary':
            return send_vocabulary(update, context)
        elif data == 'review_vocabulary':
            return review_vocabulary(update, context)
        elif data == 'check_answers':
            return check_answers(update, context)
    elif data in ['A1', 'A2', 'B1']:
        context.user_data['level'] = data
        # Store user's level in bot_data for future use
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_levels', {})[user_id] = data
        logger.info(f"User selected level: {data}")
        # After selecting level, present options
        return start(update, context)
    else:
        safe_edit_message_text(update, context, "Unbekannte Option.")
        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📰 Nachrichten", callback_data='news')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        send_message(update, context, "Bitte wähle eine Option:", reply_markup=reply_markup)
        return LEVEL

def ask_level(update: Update, context) -> int:
    logger.info("Asking user for language level.")
    keyboard = [
        [InlineKeyboardButton("A1", callback_data='A1'), InlineKeyboardButton("A2", callback_data='A2')],
        [InlineKeyboardButton("B1", callback_data='B1')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Bitte wähle dein Deutschniveau:", reply_markup=reply_markup)
    return LEVEL

def level_received(update: Update, context: CallbackContext) -> int:
    user_level = update.message.text.upper()
    if user_level not in ['A1', 'A2', 'B1']:
        send_message(update, context, "Bitte gib ein gültiges Niveau ein (A1, A2, B1):")
        return LEVEL
    context.user_data['level'] = user_level
    # Store user's level in bot_data for future use
    user_id = update.effective_user.id
    context.bot_data.setdefault('user_levels', {})[user_id] = user_level
    logger.info(f"User provided level: {user_level}")
    # After selecting level, present options
    return start(update, context)

def show_news_list(update, context) -> int:
    user_level = context.user_data.get('level')
    if not user_level:
        send_message(update, context, "Bitte wähle zuerst dein Deutschniveau.")
        return ask_level(update, context)

    news_articles = context.bot_data.get('news_articles', [])
    if not news_articles:
        send_message(update, context, "Es sind derzeit keine Nachrichten verfügbar. Bitte versuche es später erneut.")
        return LEVEL

    # Generate a numbered list of articles
    articles_list = ""
    for idx, article in enumerate(news_articles[:10], start=1):  # Show top 10 articles
        article_title = article.get('short_title', article['title'])
        articles_list += f"{idx}. {article_title}\n"

    message_text = "Bitte wähle einen Nachrichtenartikel, indem du seine Nummer eingibst:\n\n" + articles_list
    send_message(update, context, message_text)
    return SELECTING_ARTICLE

def select_article(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()
    if not user_input.isdigit():
        send_message(update, context, "Bitte gib eine gültige Zahl ein.")
        return SELECTING_ARTICLE

    idx = int(user_input) - 1  # Adjust for zero-based index
    news_articles = context.bot_data.get('news_articles', [])
    if idx < 0 or idx >= len(news_articles[:10]):
        send_message(update, context, "Bitte gib eine Zahl aus der Liste ein.")
        return SELECTING_ARTICLE

    context.user_data['selected_article_index'] = idx
    return adapt_and_send_news_article(update, context, idx)

def adapt_and_send_news_article(update, context, idx) -> int:
    try:
        user_level = context.user_data.get('level')
        news_articles = context.bot_data.get('news_articles', [])
        if idx < 0 or idx >= len(news_articles):
            send_message(update, context, "Ungültige Auswahl.")
            return LEVEL

        article = news_articles[idx]
        context.user_data['selected_article'] = article

        send_message(update, context, "✨ Artikel wird an dein Level angepasst, bitte warten... ⏳")

        # Adapt the text to the user's level
        adapted_text = adapt_text_to_level(article['text'], user_level)
        if not adapted_text:
            send_message(update, context, "Entschuldigung, es gab einen Fehler beim Anpassen des Artikels.")
            return LEVEL

        context.user_data['adapted_text'] = adapted_text

        # Generate audio
        selected_voice = random.choice(female_voices + male_voices)  # Choose a voice
        audio_file = generate_audio_content(adapted_text, selected_voice)
        if not audio_file:
            send_message(update, context, "Entschuldigung, es gab einen Fehler bei der Audio-Generierung.")
            return LEVEL

        # Send the audio
        try:
            with open(audio_file, 'rb') as audio:
                context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio, caption="🎧 Hier ist dein Artikel!")
            logger.info("Audio sent to user.")
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            send_message(update, context, "Entschuldigung, es gab einen Fehler beim Senden der Audio.")
            return LEVEL
        finally:
            os.remove(audio_file)  # Clean up audio file

        # Provide options to the user
        keyboard = [
            [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
            [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
            [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
            [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        send_message(update, context, "Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
        return ARTICLE_SENT
    except Exception as e:
        logger.error(f"Error in adapt_and_send_news_article: {e}")
        send_message(update, context, "Entschuldigung, es gab einen Fehler beim Verarbeiten des Artikels.")
        return LEVEL

# ... [Rest of your code remains the same]

def generate_audio_content(text: str, voice: str) -> str:
    logger.info(f"Generating audio with voice: {voice}")

    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    data = {
        "model": "tts-1",
        "input": text,
        "voice": voice
    }

    try:
        logger.info("Sending request to TTS API for audio.")
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request Headers: {headers}")
        logger.debug(f"Request Data: {json.dumps(data, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data)
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response Headers: {response.headers}")
        logger.debug(f"Response Content: {response.text}")

        response.raise_for_status()
        audio_content = response.content

        # Write to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        logger.info("Audio file generated and saved.")
        return temp_audio_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating audio: {e}")
        if e.response is not None:
            logger.error(f"Response Content: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None


def send_questions(update, context) -> int:
    adapted_text = context.user_data.get('adapted_text')
    if not adapted_text:
        send_message(update, context, "Es gibt keinen Artikel, um Fragen zu generieren.")
        return ARTICLE_SENT

    logger.info("Generating questions based on the adapted text.")
    send_message(update, context, "✨ Fragen werden generiert, bitte warten... ⏳")
    questions = generate_questions(adapted_text)
    if questions:
        context.user_data['questions'] = questions
        context.user_data['user_answers'] = []  # Reset any previous answers
        send_message(update, context, "Hier sind einige Fragen zum Artikel: ❓\n" + questions)
        send_message(update, context, "Bitte sende deine Antworten einzeln. 💬")
        # Provide options to the user
        keyboard = [
            [InlineKeyboardButton("✅ Antworten überprüfen", callback_data='check_answers')],
            [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
            [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
            [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        send_message(update, context, "Du kannst jederzeit Optionen wählen:", reply_markup=reply_markup)
        return ANSWERING_QUESTIONS
    else:
        logger.error("Failed to generate questions.")
        send_message(update, context, "Entschuldigung, es gab einen Fehler beim Generieren der Fragen.")
        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📰 Nachrichten", callback_data='news')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        send_message(update, context, "Bitte wähle eine Option:", reply_markup=reply_markup)
        return LEVEL

def send_text(update, context) -> int:
    adapted_text = context.user_data.get('adapted_text')
    if not adapted_text:
        send_message(update, context, "Es gibt keinen Text zum Anzeigen.")
        return ARTICLE_SENT
    logger.info("Sending adapted text to user.")
    send_message(update, context, "Hier ist der Text des Artikels: 📄\n" + adapted_text)
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
        [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return ARTICLE_SENT

def send_vocabulary(update, context) -> int:
    adapted_text = context.user_data.get('adapted_text')
    if not adapted_text:
        send_message(update, context, "Es gibt keinen Text, um Vokabeln zu extrahieren.")
        return ARTICLE_SENT

    logger.info("Extracting vocabulary from the adapted text.")
    send_message(update, context, "🔍 Vokabeln werden extrahiert, bitte warten... ⏳")
    vocabulary = generate_vocabulary(adapted_text)
    if vocabulary:
        send_message(update, context, "Hier sind einige Vokabeln aus dem Artikel: 📚\n" + vocabulary)

        # Store vocabulary for tracking
        user_id = update.effective_user.id
        user_vocab = context.bot_data.setdefault('user_vocab', {})
        user_vocab.setdefault(user_id, []).extend(vocabulary.split('\n'))
        logger.info(f"Vocabulary stored for user {user_id}.")

    else:
        logger.error("Failed to generate vocabulary.")
        send_message(update, context, "Entschuldigung, es gab einen Fehler beim Extrahieren der Vokabeln.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return ARTICLE_SENT

def review_vocabulary(update, context) -> int:
    user_id = update.effective_user.id
    user_vocab = context.bot_data.get('user_vocab', {}).get(user_id, [])
    if user_vocab:
        unique_vocab = list(set(user_vocab))
        vocab_text = "\n".join(unique_vocab)
        send_message(update, context, "Hier ist deine gesammelte Vokabelliste: 📚\n" + vocab_text)
    else:
        send_message(update, context, "Du hast noch keine Vokabeln gesammelt.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("📰 Nachrichten", callback_data='news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return LEVEL

def receive_answer(update: Update, context: CallbackContext) -> int:
    user_answer = update.message.text
    context.user_data.setdefault('user_answers', []).append(user_answer)
    logger.info(f"User provided answer: {user_answer}")
    send_message(update, context, "Antwort erhalten. 😊")
    # Provide options to check answers or continue
    keyboard = [
        [InlineKeyboardButton("✅ Antworten überprüfen", callback_data='check_answers')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Du kannst weitere Antworten senden oder Optionen wählen:", reply_markup=reply_markup)
    return ANSWERING_QUESTIONS

def check_answers(update, context) -> int:
    adapted_text = context.user_data.get('adapted_text')
    questions = context.user_data.get('questions')
    user_answers = context.user_data.get('user_answers', [])

    if not adapted_text or not questions or not user_answers:
        send_message(update, context, "Es gibt keine Antworten zum Überprüfen.")
        return ARTICLE_SENT

    logger.info("Checking user's answers.")
    send_message(update, context, "🔎 Antworten werden überprüft, bitte warten... ⏳")
    feedback = generate_feedback(adapted_text, questions, user_answers)
    if feedback:
        send_message(update, context, "Hier ist das Feedback zu deinen Antworten: ✅\n" + feedback)
    else:
        logger.error("Failed to generate feedback.")
        send_message(update, context, "Entschuldigung, es gab einen Fehler beim Überprüfen der Antworten.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
        [InlineKeyboardButton("🔄 Anderen Artikel wählen", callback_data='news')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_message(update, context, "Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return ARTICLE_SENT

def generate_feedback(text: str, questions: str, user_answers: list) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = (
        f"Hier ist ein Text:\n\n{text}\n\n"
        f"Hier sind die Fragen:\n{questions}\n\n"
        f"Hier sind die Antworten des Lerners:\n" + "\n".join(user_answers) +
        "\n\nBitte überprüfe die Antworten und gib Feedback auf Deutsch:"
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for feedback.")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        feedback = response_data['choices'][0]['message']['content'].strip()
        logger.info("Feedback received from OpenAI API.")
        return feedback
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating feedback: {e}")
        return None

def generate_vocabulary(text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = (
        f"Extrahiere die wichtigsten Vokabeln aus dem folgenden Text und gib eine Liste mit Übersetzungen ins Englische:\n\n{text}\n\n"
        "Vokabelliste (immer nutzen DER DIE DAS):"
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for vocabulary.")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        vocabulary = response_data['choices'][0]['message']['content'].strip()
        logger.info("Vocabulary received from OpenAI API.")
        return vocabulary
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating vocabulary: {e}")
        return None

def generate_questions(text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = f"Lies den folgenden Text und erstelle drei Verständnisfragen dazu:\n\n{text}\n\nFragen:"
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for questions.")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        questions = response_data['choices'][0]['message']['content'].strip()
        logger.info("Questions received from OpenAI API.")
        return questions
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating questions: {e}")
        return None

def adapt_text_to_level(text, level):
    """
    Uses OpenAI to adapt the text to the user's German level (A1, A2, B1, etc.).
    """
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
        logger.info(f"Sending request to OpenAI API to adapt text to level {level}.")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        adapted_text = result['choices'][0]['message']['content']
        logger.info("Text adapted successfully.")
        return adapted_text.strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adapting text to level {level}: {e}")
        return None

def generate_short_title(title: str, max_length: int = 30) -> str:
    """
    Generates a concise summary title suitable for button display.
    """
    if len(title) <= max_length:
        return title  # Title is already short enough

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    prompt = (
        f"Verkürze den folgenden Titel auf maximal {max_length} Zeichen, sodass er die Hauptidee enthält und für eine Liste geeignet ist:\n\n"
        f"Titel: {title}\n\n"
        "Kurzer Titel:"
    )

    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 20,
        "n": 1,
        "stop": None
    }

    try:
        logger.info(f"Generating short title for: {title}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        short_title = result['choices'][0]['message']['content'].strip()
        logger.info(f"Short title generated: {short_title}")
        return short_title
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating short title: {e}")
        # Fallback to truncating the title
        return title[:max_length] + "..."
import re

def fetch_general_news():
    """
    Fetch the general news from the main DW Germany news section.
    Extracts article URLs and returns them for detailed fetching.
    """
    url = "https://www.dw.com/de/themen/s-9077"
    logger.info(f"Fetching general news from {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching the main news page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Use a set to store unique article URLs
    article_urls = set()

    # Define a regex pattern for article URLs
    article_url_pattern = re.compile(r'^/de/[\w\-/]+/a-\d+$')

    for link in soup.find_all('a', href=True):
        href = link['href']
        if article_url_pattern.match(href):
            # Ensure the URL is correctly concatenated
            if href.startswith('http'):
                full_url = href
            else:
                full_url = "https://www.dw.com" + href
            article_urls.add(full_url)
            logger.info(f"Found article URL: {full_url}")

    article_urls = list(article_urls)
    logger.info(f"Total {len(article_urls)} unique articles found.")
    return article_urls
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
                article_key = next((key for key in app_state_json if key.startswith("/graph-api/de/content/article")), None)
                if article_key and article_key in app_state_json:
                    article_data = app_state_json[article_key]["data"]["content"]

                    # Check if necessary fields are present
                    if not article_data.get("title") or not article_data.get("text"):
                        logger.warning(f"Article missing title or text: {article_url}")
                        return None

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

    logger.error(f"Could not extract article details from {article_url}")
    return None

def extract_and_fetch_news():
    """
    Fetches the list of news articles without adapting the text yet.
    """
    logger.info("Starting the extraction and fetching of news articles.")
    news_articles = []

    # Step 1: Fetch the general news URLs
    article_urls = fetch_general_news()

    # Use a set to track article URLs that have been processed
    processed_urls = set()

    # Step 2: For each article URL, fetch its details and add to the list
    for article_url in article_urls:
        if article_url not in processed_urls:
            details = fetch_article_details(article_url)
            if details:
                # Generate short title
                short_title = generate_short_title(details['title'])
                details['short_title'] = short_title
                news_articles.append(details)
                processed_urls.add(article_url)
        else:
            logger.info(f"Duplicate article URL found and skipped: {article_url}")

    logger.info(f"Total {len(news_articles)} unique articles successfully fetched.")
    return news_articles

def cancel(update: Update, context: CallbackContext) -> int:
    logger.info("User cancelled the conversation.")
    send_message(update, context, 'Auf Wiedersehen! 👋')
    return ConversationHandler.END

def update_news_articles(context: CallbackContext):
    logger.info("Updating news articles.")

    # Check if the news articles JSON file exists and is up-to-date (e.g., not older than 1 hour)
    if NEWS_JSON_PATH.exists():
        file_mod_time = datetime.datetime.fromtimestamp(NEWS_JSON_PATH.stat().st_mtime)
        if datetime.datetime.now() - file_mod_time < datetime.timedelta(hours=1):
            # Load articles from the JSON file
            logger.info("Loading news articles from cache.")
            with open(NEWS_JSON_PATH, 'r', encoding='utf-8') as f:
                news_articles = json.load(f)
            context.bot_data['news_articles'] = news_articles
            logger.info("News articles loaded from disk.")
            return

    # If the JSON file doesn't exist or is outdated, fetch new articles
    logger.info("Fetching new news articles from the website.")
    news_articles = extract_and_fetch_news()

    # Save the articles to disk
    with open(NEWS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(news_articles, f, ensure_ascii=False, indent=4)
    logger.info(f"News articles saved to {NEWS_JSON_PATH}.")

    context.bot_data['news_articles'] = news_articles
    logger.info("News articles updated in bot data.")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Telegram bot.")

    # Set up your ConversationHandler and other handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LEVEL: [
                CallbackQueryHandler(button_handler),
                MessageHandler(Filters.text & ~Filters.command, level_received)
            ],
            SELECTING_ARTICLE: [
                MessageHandler(Filters.regex(r'^\d+$'), select_article),
                CallbackQueryHandler(button_handler),
                MessageHandler(Filters.text & ~Filters.command, lambda u, c: send_message(u, c, "Bitte gib die Zahl des Artikels ein."))
            ],
            ARTICLE_SENT: [
                CallbackQueryHandler(button_handler),
                MessageHandler(Filters.text & ~Filters.command, receive_answer)
            ],
            ANSWERING_QUESTIONS: [
                MessageHandler(Filters.text & ~Filters.command, receive_answer),
                CallbackQueryHandler(button_handler)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    # Set up job for updating news articles every hour
    job_queue = updater.job_queue
    job_queue.run_repeating(update_news_articles, interval=3600*6, first=3600*6)

    # Use long polling
    logger.info("Starting bot using long polling.")
    updater.start_polling()
    logger.info("Telegram bot started.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping Telegram bot.")
    updater.stop()
    updater.is_idle = False
    logger.info("Telegram bot stopped.")

def main():
    # Fetch tokens securely from environment variables
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    openai_api_key_env = os.environ.get('OPENAI_API_KEY')  # Avoid overwriting the global variable

    # Check if tokens are available
    if not telegram_bot_token or not openai_api_key_env:
        logger.error("Bot token or OpenAI API key not set in environment variables.")
        return

    global openai_api_key
    openai_api_key = openai_api_key_env  # Assign to the global variable used in functions

    # Initialize news articles
    update_news_articles(dispatcher)

    # Run FastAPI with Uvicorn in the main thread
    if __name__ == "__main__":
        import uvicorn
        PORT = int(os.environ.get('PORT', 8080))
        uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")



if __name__ == '__main__':
    main()