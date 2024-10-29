# app/bot/handlers.py
import logging
import os
import random
import json
import datetime
import tempfile
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from app.services.openai_client import OpenAIClient
from app.services.audio_generator import AudioGenerator
from app.utils.logger import get_logger
from app.services.news_fetcher_service import news_fetcher

logger = get_logger(__name__)

# Define conversation states
LEVEL, SELECTING_ARTICLE, ARTICLE_SENT, ANSWERING_QUESTIONS = range(4)

# Define voice lists based on gender
male_voices = ['alloy', 'onyx']
female_voices = ['echo', 'fable', 'nova', 'shimmer']

openai_client = OpenAIClient()
audio_generator = AudioGenerator()

def get_conv_handler():
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
    return conv_handler

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

# Start function
def start(update: Update, context: CallbackContext) -> int:
    logger.info("User started the bot.")
    # Load news articles from disk or fetch if not available
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
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_levels', {})[user_id] = data
        logger.info(f"User selected level: {data}")
        return start(update, context)
    else:
        safe_edit_message_text(update, context, "Unbekannte Option.")
        keyboard = [
            [InlineKeyboardButton("📰 Nachrichten", callback_data='news')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        send_message(update, context, "Bitte wähle eine Option:", reply_markup=reply_markup)
        return LEVEL

def ask_level(update: Update, context: CallbackContext) -> int:
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
    user_id = update.effective_user.id
    context.bot_data.setdefault('user_levels', {})[user_id] = user_level
    logger.info(f"User provided level: {user_level}")
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
        adapted_text = news_fetcher.get_adapted_text(article, user_level, openai_client)
        if not adapted_text:
            send_message(update, context, "Entschuldigung, es gab einen Fehler beim Anpassen des Artikels.")
            return LEVEL

        context.user_data['adapted_text'] = adapted_text

        # Generate audio
        selected_voice = random.choice(female_voices + male_voices)  # Choose a voice
        audio_file = audio_generator.generate_audio(adapted_text, selected_voice)
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

def cancel(update: Update, context: CallbackContext) -> int:
    logger.info("User cancelled the conversation.")
    send_message(update, context, 'Auf Wiedersehen! 👋')
    return ConversationHandler.END

def update_news_articles(context: CallbackContext):
    logger.info("Updating news articles.")
    news_fetcher.update_articles()
    context.bot_data['news_articles'] = news_fetcher.get_cached_articles()
    logger.info("News articles updated in bot data.")

def send_questions(update: Update, context: CallbackContext) -> int:
    adapted_text = context.user_data.get('adapted_text')
    if not adapted_text:
        send_message(update, context, "Es gibt keinen Artikel, um Fragen zu generieren.")
        return ARTICLE_SENT

    logger.info("Generating questions based on the adapted text.")
    send_message(update, context, "✨ Fragen werden generiert, bitte warten... ⏳")
    questions = openai_client.generate_questions(adapted_text)
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
    vocabulary = openai_client.generate_vocabulary(adapted_text)
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
    feedback = openai_client.generate_feedback(adapted_text, questions, user_answers)
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