# app/bot/bot.py
import threading
from telegram.ext import Updater
from app.config import settings
from app.bot.handlers import get_conv_handler
from app.utils.logger import get_logger
from app.services.news_fetcher_service import news_fetcher

logger = get_logger(__name__)

class TelegramBot:
    def __init__(self):
        self.updater = Updater(settings.TELEGRAM_BOT_TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.setup_handlers()

    def setup_handlers(self):
        conv_handler = get_conv_handler()
        self.dispatcher.add_handler(conv_handler)

    def start(self):
        logger.info("Starting Telegram bot using long polling.")
        news_fetcher.update_articles()
        self.updater.start_polling()
        self.updater.idle()

    def stop(self):
        logger.info("Stopping Telegram bot.")
        self.updater.stop()