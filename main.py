# app/main.py

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import get_logger
from apscheduler.schedulers.background import BackgroundScheduler
from app.api.routes import router as api_router
from app.services.news_fetcher_service import news_fetcher  # Import the news_fetcher instance
import pytz  # Import pytz

logger = get_logger(__name__)

app = FastAPI()

# Include API routes
app.include_router(api_router, prefix=settings.WEB_APP_PREFIX)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],             # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],             # Allows all HTTP methods
    allow_headers=["*"],             # Allows all headers
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize APScheduler with pytz timezone
scheduler = BackgroundScheduler(timezone=pytz.utc)  # You can specify any timezone you prefer
@app.on_event("startup")
async def startup_event():
    # # Run the bot in a separate thread
    # bot_thread = threading.Thread(target=start_telegram_bot, name="TelegramBotThread", daemon=True)
    # bot_thread.start()
    # logger.info("Telegram bot started.")

    # Start the scheduler
    scheduler.add_job(news_fetcher.update_articles, 'interval', hours=5)
    scheduler.start()
    logger.info("Scheduler started for news fetching.")

    # Fetch news articles at startup
    news_fetcher.update_articles()

@app.on_event("shutdown")
async def shutdown_event():
    # logger.info("Stopping Telegram bot.")
    # telegram_bot.stop()

    logger.info("Shutting down scheduler.")
    scheduler.shutdown()

# Define a root route
@app.get("/", response_class=RedirectResponse)
async def root():
    # Redirect to the main app prefix
    return RedirectResponse(url=settings.WEB_APP_PREFIX + "/")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)