"""TikTok Creative Center source connector.

Retrieves trending hashtags, top videos by category, and Creator Search
Insights from the TikTok Creative Center API.

API reference: https://ads.tiktok.com/marketing_api/docs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
CREATIVE_CENTER_URL = "https://ads.tiktok.com/creative_radar_api/v1"


class TikTokSource(BaseSource):
    """Fetches trending content signals from the TikTok Creative Center.

    Args:
        api_key:  TikTok for Business API key.
        settings: Global configuration.
    """

    PLATFORM = "tiktok"

    def __init__(self, api_key: str, settings: Optional[Settings] = None) -> None:
        self.api_key = api_key
        self.settings = settings or Settings()
        self._client = httpx.Client(
            headers={
                "Access-Token": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # BaseSource implementation
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch trending hashtags from the TikTok Creative Center.

        Returns:
            List of raw hashtag trend dicts.
        """
        country_code = self.settings.tiktok_country_code
        period = self.settings.tiktok_trend_period  # 7 | 30 | 120

        url = f"{CREATIVE_CENTER_URL}/trending/hashtag/list/"
        params = {
            "country_code": country_code,
            "period": period,
            "page": 1,
            "page_size": 50,
        }

        response = self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get("data", {}).get("list", [])
        logger.debug("TikTok fetched %d trending hashtags.", len(items))
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single TikTok hashtag trend item.

        Args:
            raw_item: Raw dict from the Creative Center API response.

        Returns:
            Normalized dict compatible with :meth:`to_trend`.
        """
        hashtag: str = raw_item.get("hashtag_name", "")
        publish_cnt: int = raw_item.get("publish_cnt", 0)
        video_views: int = raw_item.get("video_views", 0)
        rank_diff: int = raw_item.get("rank_diff", 0)  # positive = rising

        return {
            "topic": hashtag,
            "hashtags": [f"#{hashtag}"],
            "demand": {
                "volume": video_views,
                "growth_rate": round(rank_diff / 100, 4),
            },
            "saturation": {
                "creator_count": publish_cnt,
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": round(rank_diff / (7 * 100), 4),
                "peak_acceleration": raw_item.get("trend_type", 0),
            },
            "country_code": raw_item.get("country_code", ""),
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized TikTok dict to a :class:`Trend`.

        Args:
            normalized: Output of :meth:`normalize`.

        Returns:
            :class:`~sources.base.Trend` instance.
        """
        return Trend(
            platform=self.PLATFORM,
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
            suggested_formats=["tiktok_video", "reel", "short"],
            pipeline_target="digital",
            raw=normalized,
        )
