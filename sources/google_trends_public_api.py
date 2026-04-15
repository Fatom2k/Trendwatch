"""Google Trends via public API (trending searches).

This source fetches the actual "Trending searches" displayed on
https://trends.google.com/explore - the top 50 searches per category
and geography from the last 7 days.

Supports multiple property types and geographies:
- gprop: web (default), news, shopping, youtube, images
- geo: FR, US, etc. (empty string = worldwide)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)


class GoogleTrendsPublicAPISource(BaseSource):
    """Fetch trending searches from Google Trends public API.

    Args:
        settings: Global configuration.
        geos: List of geo codes (e.g. ["FR", "US", ""]) where "" = worldwide
        properties: List of gprop values (web, news, shopping, youtube, images)
    """

    PLATFORM = "google_trends"

    # Default: search web trends in France and worldwide
    DEFAULT_GEOS = ["FR", ""]  # "" = worldwide/international
    DEFAULT_PROPERTIES = ["web"]  # web, news, shopping, youtube, images

    def __init__(
        self,
        settings: Optional[Settings] = None,
        geos: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.geos = geos or self.DEFAULT_GEOS
        self.properties = properties or self.DEFAULT_PROPERTIES

        # Headers to appear as a real browser (Google blocks scraping)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://trends.google.com/",
            "Origin": "https://trends.google.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
        }
        self._client = httpx.Client(timeout=30.0, headers=headers, follow_redirects=False)

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch trending searches from all configured geo/property combinations."""
        all_trends: List[Dict[str, Any]] = []

        for geo in self.geos:
            for gprop in self.properties:
                try:
                    trends = self._fetch_trending_searches(geo=geo, gprop=gprop)
                    all_trends.extend(trends)
                    time.sleep(1)  # Rate limiting
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch trends (geo=%s, gprop=%s): %s",
                        geo or "worldwide",
                        gprop,
                        exc,
                    )

        logger.info("Fetched %d trending searches", len(all_trends))
        return all_trends

    def _fetch_trending_searches(
        self, geo: str = "", gprop: str = "web"
    ) -> List[Dict[str, Any]]:
        """Fetch trending searches for a specific geo and property.

        The Google Trends API endpoint returns JSON embedded in the HTML response.
        We extract the JSON, parse it, and return the trending searches.

        Args:
            geo: Geography code (e.g. "FR", "US"). Empty string = worldwide.
            gprop: Property type (web, news, shopping, youtube, images).

        Returns:
            List of trending search items with rank, title, and metadata.
        """
        params = {
            "geo": geo,
            "gprop": gprop,
            "date": "now 7-d",  # Last 7 days
        }

        url = f"https://trends.google.com/trends/api/explore?{urlencode(params)}"
        logger.debug("Fetching: %s", url)

        resp = self._client.get(url)
        resp.raise_for_status()

        # Google's API response starts with ")]}'" — remove it
        text = resp.text.lstrip(")]}'\n")

        # Parse JSON
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON response: %s", exc)
            return []

        # Extract trending searches from response
        # Structure: { "default": { "geo": { ... }, "exploreQuery": { ... }, "widgets": [ { "request": { ... }, "response": [ items ] } ] } }
        items: List[Dict[str, Any]] = []

        try:
            default = data.get("default", {})
            widgets = default.get("widgets", [])

            # Usually the trending searches are in the first widget
            for widget in widgets:
                response = widget.get("response", [])
                if not response:
                    continue

                # Each response item has trending searches
                for item in response:
                    if "trendingSearchesSummary" in item:
                        # Summary format with trend items
                        trending = item.get("trendingSearchesSummary", {}).get(
                            "trendingSearches", []
                        )
                        for idx, trend in enumerate(trending, 1):
                            title = trend.get("title", {}).get("query", "")
                            if title:
                                items.append({
                                    "rank": idx,
                                    "keyword": title,
                                    "geo": geo or "worldwide",
                                    "gprop": gprop,
                                    "traffic_display": trend.get("title", {}).get(
                                        "exploreLink", ""
                                    ),
                                })

        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Failed to extract trending searches: %s", exc)

        geo_label = geo or "worldwide"
        logger.info(
            "Found %d trending searches for %s (%s)",
            len(items),
            geo_label,
            gprop,
        )
        return items

    # ====================================================================
    # BaseSource implementation
    # ====================================================================

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a trending search item."""
        keyword: str = raw_item.get("keyword", "")
        rank: int = raw_item.get("rank", 50)
        geo: str = raw_item.get("geo", "")
        gprop: str = raw_item.get("gprop", "web")

        # Score based on rank: #1 = 100, #50 = 10
        # Linear scale: score = 100 - (rank - 1) * 1.8
        score_value = max(10, 100 - (rank - 1) * 1.8)

        return {
            "topic": keyword,
            "hashtags": [f"#{keyword.replace(' ', '')}"],
            "demand": {
                "volume": int((51 - rank) * 1000),  # Inverse rank → volume
                "growth_rate": 0.5,  # Trending = moderate growth
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
                "source": "google_trends_public_api",
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert normalized dict to Trend object."""
        metadata = normalized.pop("raw_metadata", {})
        rank = metadata.get("rank", 50)
        geo = metadata.get("geo", "")
        gprop = metadata.get("gprop", "web")

        # Build a unique ID that includes geo and gprop
        geo_label = geo or "worldwide"
        topic_with_context = f"{normalized['topic']} ({gprop}/{geo_label})"

        return Trend(
            platform=self.PLATFORM,
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
            suggested_formats=["thread", "carousel", "reel"],
            pipeline_target="digital",
            raw={
                **normalized,
                **metadata,
            },
        )
