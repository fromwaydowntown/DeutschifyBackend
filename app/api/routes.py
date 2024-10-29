# app/api/routes.py

from fastapi import Request, HTTPException, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

from app.services.news_fetcher_service import news_fetcher
from app.services.openai_client import OpenAIClient
from app.services.audio_generator import AudioGenerator
from app.utils.logger import get_logger
from starlette.templating import Jinja2Templates

logger = get_logger(__name__)
router = APIRouter()

# Initialize services
openai_client = OpenAIClient()
audio_generator = AudioGenerator()

# Jinja2 Templates
templates = Jinja2Templates(directory="app/api/templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    news_articles = news_fetcher.get_cached_articles()
    logger.info("Rendering index page")
    return templates.TemplateResponse("news.html", {"request": request, "articles": enumerate(news_articles)})

@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int):
    articles = news_fetcher.get_cached_articles()
    if 0 <= article_id < len(articles):
        article = articles[article_id]

        # Adapt full article text on demand
        adapted_text = news_fetcher.get_adapted_text(article, 'A1')

        # Format the adapted text for display
        formatted_adapted_text = news_fetcher.format_article_text(adapted_text) if adapted_text else ''

        # Remove formatting of original text since it's not displayed
        # formatted_text = news_fetcher.format_article_text(article['text']) if article['text'] else ''

        return templates.TemplateResponse(
            "news_detail.html",
            {
                "request": request,
                "article": article,
                "formatted_adapted_text": formatted_adapted_text,
                "article_id": article_id,
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Article not found")

@router.post("/article/{article_id}/adapt")
async def adapt_article_text(article_id: int, request: Request):
    data = await request.json()
    level = data.get('level')

    if not level:
        return JSONResponse({'status': 'error', 'message': 'Level not specified'}, status_code=400)

    news_articles = news_fetcher.get_cached_articles()
    if 0 <= article_id < len(news_articles):
        article = news_articles[article_id]
        adapted_text = news_fetcher.get_adapted_text(article, level)
        if adapted_text:
            formatted_adapted_text = news_fetcher.format_article_text(adapted_text)
            return JSONResponse({'status': 'success', 'adapted_text': formatted_adapted_text})
        else:
            return JSONResponse({'status': 'error', 'message': 'Adapted text not available for this level'}, status_code=404)
    else:
        raise HTTPException(status_code=404, detail="Article not found")

@router.post("/play")
async def generate_audio_endpoint(request: Request):
    data = await request.json()
    text = data.get('text', '')
    voice = data.get('voice', audio_generator.get_random_voice())

    if not text:
        return JSONResponse({'status': 'error', 'message': 'Text not provided'}, status_code=400)

    # Generate audio
    logger.info("Generating audio for provided text.")
    temp_audio_path = audio_generator.generate_audio(text, voice)

    if temp_audio_path:
        # Generate unique audio file name to prevent caching
        unique_suffix = audio_generator.generate_unique_suffix()
        audio_file_path = f"static/audio/audio_{unique_suffix}.mp3"
        Path("static/audio").mkdir(parents=True, exist_ok=True)
        try:
            audio_generator.save_audio(temp_audio_path, audio_file_path)
            logger.info(f"Audio file saved at {audio_file_path}")
            audio_url = f"/{audio_file_path}"
            return JSONResponse({'status': 'success', 'audio_url': audio_url})
        except Exception as e:
            logger.error(f"Failed to move audio file: {e}")
            return JSONResponse({'status': 'error', 'message': 'Failed to save audio file'}, status_code=500)
        finally:
            audio_generator.cleanup_temp_audio(temp_audio_path)
    else:
        logger.error("Failed to generate audio")
        return JSONResponse({'status': 'error', 'message': 'Audio generation failed'}, status_code=500)