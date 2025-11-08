"""Constants for Home Assistant News integration."""
from typing import Final

DOMAIN: Final = "ai_news_anchor"

CATEGORY_MAP: Final[dict[str, str]] = {
    "U.S.": "NATION",
    "World": "WORLD",
    "Local": "GEO",
    "Business": "BUSINESS",
    "Technology": "TECHNOLOGY",
    "Entertainment": "ENTERTAINMENT",
    "Sports": "SPORTS",
    "Science": "SCIENCE",
    "Health": "HEALTH",
}

GOOGLE_RSS_BASE: Final = "https://news.google.com/rss/headlines/section"

DEFAULTS = {
    "scan_interval": 1800,
    "max_per_category": 2,
    "local_geo": "New York, NY",
    "tts_entity": "",
    "media_players": [],
    "ai_mode": "auto",
    "conversation_agent_id": "",
    "preroll_ms": 150,
    "enabled_categories": {
        "U.S.": True,
        "World": True,
        "Local": True,
        "Business": True,
        "Technology": True,
        "Entertainment": True,
        "Sports": True,
        "Science": True,
        "Health": True,
    },
}


