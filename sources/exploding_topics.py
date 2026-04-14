"""Exploding Topics source connector.

Uses the Exploding Topics REST API to retrieve rapidly growing topics
across categories.

API docs: https://explodingtopics.com/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)

BASE_URL = "https://explodingtopics.com/api"


class ExplodingTopicsSource(BaseSource):
    """Fetches exploding trends from the Exploding Topics API.

    Args:
        api_key:  Exploding Topics API key.
        settings: Global configuration.
    """

    PLATFORM = "exploding_topics"

    def __init__(self, api_key: str, settings: Optional[Settings] = None) -> None:
        self.api_key = api_key
        self.settings = settings or Settings()
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # BaseSource implementation
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict[str, Any]]:
        """Retrieve trending topics from the Exploding Topics API.

        Returns:
            List of raw topic dicts as returned by the API.
        """
        params: Dict[str, Any] = {
            "sort": "exploding",
            "limit": self.settings.exploding_topics_limit,
        }
        if self.settings.exploding_topics_category:
            params["category"] = self.settings.exploding_topics_category

        response = self._client.get("/topics", params=params)
        response.raise_for_status()
        data = response.json()
        topics = data.get("topics", data) if isinstance(data, dict) else data
        logger.debug("ExplodingTopics fetched %d topics.", len(topics))
        return topics

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single Exploding Topics API item.

        Args:
            raw_item: Raw dict from the API response.

        Returns:
            Normalized dict compatible with :meth:`to_trend`.
        """
        topic: str = raw_item.get("topic", raw_item.get("name", ""))
        growth: float = raw_item.get("growth", raw_item.get("growth_pct", 0.0))
        volume: int = raw_item.get("volume", raw_item.get("search_volume", 0))

        return {
            "topic": topic,
            "hashtags": [f"#{topic.replace(' ', '')}"],
            "demand": {
                "volume": volume,
                "growth_rate": round(growth / 100, 4) if growth > 1 else growth,
            },
            "saturation": {
                "creator_count": raw_item.get("competitor_count", 0),
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": round(growth / 30, 4) if growth else 0.0,
                "peak_acceleration": raw_item.get("acceleration", 0.0),
            },
            "category": raw_item.get("category", ""),
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized Exploding Topics dict to a :class:`Trend`.

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
            suggested_formats=["thread", "carousel", "blog"],
            pipeline_target="digital",
            raw=normalized,
        )
