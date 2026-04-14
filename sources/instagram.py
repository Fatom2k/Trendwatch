"""Instagram source connector.

Combines two data sources:
1. Instagram Graph API  — account-level insights and hashtag search.
2. SISTRIX Hashtag API  — external hashtag volume and trend data.

Graph API reference: https://developers.facebook.com/docs/instagram-api
SISTRIX API reference: https://api.sistrix.com/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
SISTRIX_BASE = "https://api.sistrix.com"


class InstagramSource(BaseSource):
    """Fetches trending hashtags from Instagram Graph API and SISTRIX.

    Args:
        access_token: Instagram Graph API access token.
        sistrix_api_key: SISTRIX API key (optional; enriches volume data).
        settings: Global configuration.
    """

    PLATFORM = "instagram"

    def __init__(
        self,
        access_token: str,
        sistrix_api_key: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.access_token = access_token
        self.sistrix_api_key = sistrix_api_key
        self.settings = settings or Settings()
        self._client = httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------
    # BaseSource implementation
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch hashtag trend data from Instagram and optionally SISTRIX.

        Returns:
            List of raw hashtag dicts with volume and growth data.
        """
        seed_hashtags = self.settings.instagram_seed_hashtags
        items: List[Dict[str, Any]] = []

        for tag in seed_hashtags:
            try:
                ig_data = self._fetch_instagram_hashtag(tag)
                if self.sistrix_api_key:
                    sistrix_data = self._fetch_sistrix_hashtag(tag)
                    ig_data.update(sistrix_data)
                items.append(ig_data)
            except Exception as exc:
                logger.warning("Instagram fetch failed for #%s: %s", tag, exc)

        logger.debug("Instagram fetched data for %d hashtags.", len(items))
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single Instagram hashtag item.

        Args:
            raw_item: Combined dict from Graph API + SISTRIX.

        Returns:
            Normalized dict compatible with :meth:`to_trend`.
        """
        tag: str = raw_item.get("hashtag", "")
        media_count: int = raw_item.get("media_count", 0)
        recent_media: int = raw_item.get("recent_media_count", 0)
        sistrix_trend: float = raw_item.get("sistrix_trend", 0.0)

        growth_rate = sistrix_trend / 100 if sistrix_trend else (
            recent_media / max(media_count, 1)
        )

        return {
            "topic": tag,
            "hashtags": [f"#{tag}"],
            "demand": {
                "volume": media_count,
                "growth_rate": round(growth_rate, 4),
            },
            "saturation": {
                "creator_count": media_count,
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": round(recent_media / 7, 2),
                "peak_acceleration": 0.0,
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized Instagram dict to a :class:`Trend`.

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
            suggested_formats=["reel", "carousel", "story"],
            pipeline_target="digital",
            raw=normalized,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_instagram_hashtag(self, hashtag: str) -> Dict[str, Any]:
        """Query Instagram Graph API for hashtag media count."""
        # Step 1: resolve hashtag ID
        resp = self._client.get(
            f"{GRAPH_API_BASE}/ig_hashtag_search",
            params={
                "user_id": self.settings.instagram_user_id,
                "q": hashtag,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        hashtag_id = resp.json()["data"][0]["id"]

        # Step 2: fetch media count
        resp2 = self._client.get(
            f"{GRAPH_API_BASE}/{hashtag_id}",
            params={
                "fields": "media_count,name",
                "access_token": self.access_token,
            },
        )
        resp2.raise_for_status()
        info = resp2.json()
        return {
            "hashtag": hashtag,
            "media_count": info.get("media_count", 0),
        }

    def _fetch_sistrix_hashtag(self, hashtag: str) -> Dict[str, Any]:
        """Query SISTRIX for hashtag trend data."""
        resp = self._client.get(
            f"{SISTRIX_BASE}/social.instagram.hashtag",
            params={
                "api_key": self.sistrix_api_key,
                "hashtag": hashtag,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        answers = data.get("answer", [{}])
        trend_value = answers[0].get("trend", {}).get("value", 0.0) if answers else 0.0
        return {"sistrix_trend": trend_value}
