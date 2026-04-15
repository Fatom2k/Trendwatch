"""Google Trends source with multiple backends.

This module provides three ways to fetch Google Trends data:
1. MOCK mode     — Use hardcoded trending data (development/testing)
2. RAPIDAPI mode — Use RapidAPI Google Trends wrapper (paid API)
3. DIRECT mode   — Direct API calls (currently blocked by Google)

Configure via GOOGLE_TRENDS_BACKEND in .env
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)


class GoogleTrendsSource(BaseSource):
    """Fetch trending searches from Google Trends.

    Supports multiple backends (mock, rapidapi, direct) to handle Google's
    aggressive bot protection. Use mock mode for development; switch to
    RapidAPI for production.

    Args:
        settings: Global configuration.
        backend: "mock" (dev), "rapidapi" (prod), or "direct" (currently blocked)
        rapidapi_key: RapidAPI key for RapidAPI backend
    """

    PLATFORM = "google_trends"

    # Mock data for development/testing
    MOCK_TRENDS = {
        "web": {
            "FR": [
                {"rank": 1, "keyword": "cyber security", "search_volume": 100000},
                {"rank": 2, "keyword": "ai trends", "search_volume": 95000},
                {"rank": 3, "keyword": "web3", "search_volume": 85000},
                {"rank": 4, "keyword": "no code tools", "search_volume": 75000},
                {"rank": 5, "keyword": "sustainable fashion", "search_volume": 70000},
            ],
            "": [  # worldwide
                {"rank": 1, "keyword": "ai tools", "search_volume": 500000},
                {"rank": 2, "keyword": "chatgpt", "search_volume": 480000},
                {"rank": 3, "keyword": "machine learning", "search_volume": 420000},
                {"rank": 4, "keyword": "generative ai", "search_volume": 400000},
                {"rank": 5, "keyword": "deep learning", "search_volume": 380000},
            ],
        },
        "youtube": {
            "FR": [
                {"rank": 1, "keyword": "shorts viral", "search_volume": 50000},
                {"rank": 2, "keyword": "gaming trending", "search_volume": 45000},
                {"rank": 3, "keyword": "music clips", "search_volume": 40000},
            ],
            "": [
                {"rank": 1, "keyword": "youtube shorts", "search_volume": 300000},
                {"rank": 2, "keyword": "viral videos", "search_volume": 280000},
                {"rank": 3, "keyword": "gaming content", "search_volume": 250000},
            ],
        },
        "news": {
            "FR": [
                {"rank": 1, "keyword": "actualités tech", "search_volume": 80000},
                {"rank": 2, "keyword": "IA nouvelles", "search_volume": 75000},
            ],
            "": [
                {"rank": 1, "keyword": "ai news", "search_volume": 200000},
                {"rank": 2, "keyword": "tech news", "search_volume": 190000},
            ],
        },
        "shopping": {
            "FR": [
                {"rank": 1, "keyword": "sustainable products", "search_volume": 60000},
                {"rank": 2, "keyword": "eco fashion", "search_volume": 55000},
            ],
            "": [
                {"rank": 1, "keyword": "eco products", "search_volume": 150000},
                {"rank": 2, "keyword": "sustainable goods", "search_volume": 140000},
            ],
        },
    }

    def __init__(
        self,
        settings: Optional[Settings] = None,
        backend: str = "mock",
        rapidapi_key: Optional[str] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.backend = backend
        self.rapidapi_key = rapidapi_key
        self._client = httpx.Client(timeout=30.0)

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch trending searches based on configured backend."""
        if self.backend == "mock":
            return self._fetch_mock()
        elif self.backend == "rapidapi":
            return self._fetch_rapidapi()
        else:  # direct
            return self._fetch_direct()

    def _fetch_mock(self) -> List[Dict[str, Any]]:
        """Return mock trending data (for development)."""
        items: List[Dict[str, Any]] = []

        geos = ["FR", ""]  # France + worldwide
        properties = ["web", "youtube", "news", "shopping"]

        for geo in geos:
            for gprop in properties:
                trends = self.MOCK_TRENDS.get(gprop, {}).get(geo, [])
                for trend in trends:
                    items.append({
                        **trend,
                        "geo": geo or "worldwide",
                        "gprop": gprop,
                        "source": "google_trends_mock",
                    })

        logger.info("MOCK: Returned %d trending searches", len(items))
        return items

    def _fetch_rapidapi(self) -> List[Dict[str, Any]]:
        """Fetch from RapidAPI Google Trends wrapper.

        Register at: https://rapidapi.com/
        Search for: "Google Trends" or "Trending Searches"
        Popular options:
        - google-trends-api (by nadeesh)
        - google-search-trending (by rakesh-metha)

        Example implementation:
        """
        if not self.rapidapi_key:
            logger.error("RapidAPI backend requires GOOGLE_TRENDS_RAPIDAPI_KEY")
            return []

        logger.warning("RapidAPI backend not yet implemented. Use MOCK mode for now.")
        return []

    def _fetch_direct(self) -> List[Dict[str, Any]]:
        """Fetch directly from Google Trends API (currently blocked by Google).

        This method is documented for reference but doesn't work in practice
        because Google blocks automated requests. Use MOCK or RAPIDAPI mode instead.
        """
        logger.warning(
            "DIRECT backend: Google Trends blocks automated requests. "
            "Use MOCK mode for development or switch to RapidAPI for production."
        )
        return []

    # ====================================================================
    # BaseSource implementation
    # ====================================================================

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a trending search item."""
        keyword: str = raw_item.get("keyword", "")
        rank: int = raw_item.get("rank", 50)
        search_volume: int = raw_item.get("search_volume", 1000)
        geo: str = raw_item.get("geo", "")
        gprop: str = raw_item.get("gprop", "web")

        return {
            "topic": keyword,
            "hashtags": [f"#{keyword.replace(' ', '')}"],
            "demand": {
                "volume": search_volume,
                "growth_rate": 0.5,  # Moderate growth
            },
            "saturation": {
                "creator_count": 0,
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": 0.1,
                "peak_acceleration": 0.0,
            },
            "raw_metadata": {
                "rank": rank,
                "geo": geo,
                "gprop": gprop,
                "search_volume": search_volume,
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert normalized dict to Trend object."""
        metadata = normalized.pop("raw_metadata", {})
        gprop = metadata.get("gprop", "web")

        # Map gprop to content_type
        content_type_map = {
            "web": "web_searches",
            "youtube": "social_video",
            "news": "news",
            "shopping": "shopping",
            "images": "social_video",
        }
        content_type = content_type_map.get(gprop, "web_searches")

        return Trend(
            platform=self.PLATFORM,
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
            suggested_formats=["thread", "carousel", "reel"],
            pipeline_target="digital",
            content_type=content_type,  # ← Specify data type
            raw={
                **normalized,
                **metadata,
            },
        )
