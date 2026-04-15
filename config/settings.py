"""Global configuration for TrendWatch.

All settings are read from environment variables (with sensible defaults)
so the agent can be configured entirely via a ``.env`` file without
modifying source code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load .env file if present
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _env_list(key: str, default: str = "") -> List[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Centralised settings object loaded from environment variables.

    All attributes have safe defaults so the agent can run with zero
    configuration for a basic Google Trends cycle.
    """

    # ------------------------------------------------------------------
    # Anthropic / Claude
    # ------------------------------------------------------------------
    anthropic_api_key: str = _env("ANTHROPIC_API_KEY")

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    output_dir: str = _env("OUTPUT_DIR", "output/reports")

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    min_score_threshold: int = _env_int("MIN_SCORE_THRESHOLD", 30)
    scorer_weight_overrides: Dict[str, float] = {}  # override per-instance if needed

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------
    schedule_cadence: str = _env("SCHEDULE_CADENCE", "daily")  # hourly | daily | weekly
    schedule_time: str = _env("SCHEDULE_TIME", "08:00")         # HH:MM
    schedule_interval_hours: int = _env_int("SCHEDULE_INTERVAL_HOURS", 1)
    timezone: str = _env("TIMEZONE", "UTC")

    # ------------------------------------------------------------------
    # Active platforms
    # ------------------------------------------------------------------
    active_platforms: List[str] = _env_list(
        "ACTIVE_PLATFORMS", "google_trends,exploding_topics"
    )

    # ------------------------------------------------------------------
    # Google Trends (multiple backends: mock, rapidapi, direct)
    # ------------------------------------------------------------------
    google_trends_backend: str = _env("GOOGLE_TRENDS_BACKEND", "mock")  # mock (dev) | rapidapi (prod) | direct (blocked)
    google_trends_rapidapi_key: str = _env("GOOGLE_TRENDS_RAPIDAPI_KEY")  # Required for rapidapi backend

    # ------------------------------------------------------------------
    # TikTok
    # ------------------------------------------------------------------
    tiktok_api_key: str = _env("TIKTOK_API_KEY")
    tiktok_country_code: str = _env("TIKTOK_COUNTRY_CODE", "US")
    tiktok_trend_period: int = _env_int("TIKTOK_TREND_PERIOD", 7)  # days: 7 | 30 | 120

    # ------------------------------------------------------------------
    # Instagram
    # ------------------------------------------------------------------
    instagram_access_token: str = _env("INSTAGRAM_ACCESS_TOKEN")
    instagram_user_id: str = _env("INSTAGRAM_USER_ID")
    instagram_seed_hashtags: List[str] = _env_list(
        "INSTAGRAM_SEED_HASHTAGS", "aesthetic,vintage,cottagecore"
    )
    sistrix_api_key: str = _env("SISTRIX_API_KEY")

    # ------------------------------------------------------------------
    # Twitter / X
    # ------------------------------------------------------------------
    twitter_bearer_token: str = _env("TWITTER_BEARER_TOKEN")
    twitter_woeid: int = _env_int("TWITTER_WOEID", 1)  # 1 = worldwide
    twitter_language: str = _env("TWITTER_LANGUAGE", "en")
    twitter_seed_keywords: List[str] = _env_list(
        "TWITTER_SEED_KEYWORDS", "aesthetic,trending,viral"
    )

    # ------------------------------------------------------------------
    # Exploding Topics
    # ------------------------------------------------------------------
    exploding_topics_api_key: str = _env("EXPLODING_TOPICS_API_KEY")
    exploding_topics_limit: int = _env_int("EXPLODING_TOPICS_LIMIT", 50)
    exploding_topics_category: str = _env("EXPLODING_TOPICS_CATEGORY", "")

    # ------------------------------------------------------------------
    # Elasticsearch
    # ------------------------------------------------------------------
    elasticsearch_host: str = _env("ELASTICSEARCH_HOST", "http://localhost:9200")
    elasticsearch_index: str = _env("ELASTICSEARCH_INDEX", "trendwatch_trends")
    elasticsearch_enabled: bool = _env("ELASTICSEARCH_ENABLED", "true").lower() == "true"
