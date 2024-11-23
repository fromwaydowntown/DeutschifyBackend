from fastapi import Request, HTTPException, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from starlette.responses import StreamingResponse
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

# HTML Routes for Web Interface
@router.get("/health")
async def health_check():
    return {"status": "ok"}

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

        # Use adapted_teaser from the article object
        adapted_teaser = article.get('adapted_teaser', '')

        # Format the adapted teaser for display
        formatted_adapted_teaser = news_fetcher.format_article_text(adapted_teaser) if adapted_teaser else ''

        return templates.TemplateResponse(
            "news_detail.html",
            {
                "request": request,
                "article": article,
                "formatted_adapted_text": formatted_adapted_teaser,
                "article_id": article_id,
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Article not found")

# API Routes for Android App
@router.get("/api/articles")
async def get_articles():
    news_articles = news_fetcher.get_cached_articles()
    logger.info("Returning news articles as JSON")
    return {"articles": news_articles}

@router.get("/api/article/{article_id}")
async def get_article_detail(article_id: int):
    articles = news_fetcher.get_cached_articles()
    if 0 <= article_id < len(articles):
        article = articles[article_id]

        # Use adapted_teaser from the article object
        adapted_teaser = article.get('adapted_teaser', '')

        # Format the adapted teaser
        formatted_adapted_teaser = news_fetcher.format_article_text(adapted_teaser) if adapted_teaser else ''

        return {
            "article": article,
            "formatted_adapted_text": formatted_adapted_teaser,
            "article_id": article_id,
        }
    else:
        raise HTTPException(status_code=404, detail="Article not found")

@router.post("/api/article/{article_id}/adapt")
async def adapt_article_text_api(article_id: int, request: Request):
    data = await request.json()
    level = data.get('level')

    if not level:
        return JSONResponse({'status': 'error', 'message': 'Level not specified'}, status_code=400)

    news_articles = news_fetcher.get_cached_articles()
    if 0 <= article_id < len(news_articles):
        article = news_articles[article_id]
        # Since we're no longer adapting text on demand, check if the level matches
        if level == 'A1':
            adapted_teaser = article.get('adapted_teaser', '')
            formatted_adapted_teaser = news_fetcher.format_article_text(adapted_teaser) if adapted_teaser else ''
            return {'status': 'success', 'adapted_text': formatted_adapted_teaser}
        else:
            return JSONResponse(
                {'status': 'error', 'message': f'Adapted text not available for level {level}'},
                status_code=404
            )
    else:
        raise HTTPException(status_code=404, detail="Article not found")

@router.post("/api/play")
async def generate_audio_endpoint_api(request: Request):
    data = await request.json()
    text = data.get('text', '')
    voice = data.get('voice', audio_generator.get_random_voice())

    if not text:
        return JSONResponse({'status': 'error', 'message': 'Text not provided'}, status_code=400)

    # Generate audio content
    logger.info("Generating audio for provided text.")
    audio_content = audio_generator.generate_audio(text, voice)

    if audio_content:
        logger.info("Audio content generated successfully.")
        return StreamingResponse(
            content=audio_content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=audio.mp3"
            }
        )
    else:
        logger.error("Failed to generate audio")
        return JSONResponse({'status': 'error', 'message': 'Audio generation failed'}, status_code=500)