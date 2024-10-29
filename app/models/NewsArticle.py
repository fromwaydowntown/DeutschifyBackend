# app/models/news.py
from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class NewsArticle:
    title: str
    short_title: str
    teaser: Optional[str]
    published_date: str
    text: str
    url: str
    adapted_texts: Dict[str, str] = field(default_factory=dict)