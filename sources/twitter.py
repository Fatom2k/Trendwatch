"""X (Twitter) source connector.

Uses the X API v2 to fetch trending topics by country and advanced
search results.  Optionally integrates Grok AI summaries when available.

API reference: https://developer.x.com/en/docs/x-api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)

X_API_BASE = "https://api.twitter.com/2"


class TwitterSource(BaseSource):
    """Fetches trending topics from X (Twitter) via the v2 API.

    Args:
        bearer_token: X API v2 bearer token.
        settings:     Global configuration.
    """

    PLATFORM = "twitter"

    def __init__(self, bearer_token: str, settings: Optional[Settings] = None) -> None:
        self.bearer_token = bearer_token
        self.settings = settings or Settings()
        self._client = httpx.Client(
            base_url=X_API_BASE,
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # BaseSource implementation
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch trending topics for the configured location WOEID.

        Falls back to advanced keyword search when trends endpoint is
        unavailable on the current API tier.

        Returns:
            List of raw trend dicts.
        """
        items: List[Dict[str, Any]] = []

        # Try v1.1 trends endpoint (requires Elevated access)
        try:
            items = self._fetch_trending_topics()
        except httpx.HTTPStatusError as exc:
            logger.warning("Trending topics endpoint unavailable (%s), falling back to search.", exc.response.status_code)
            items = self._fetch_via_search()

        logger.debug("Twitter fetched %d raw items.", len(items))
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single X trend item.

        Args:
            raw_item: Dict from the trends or search API.

        Returns:
            Normalized dict compatible with :meth:`to_trend`.
        """
        name: str = raw_item.get("name", raw_item.get("query", "")).lstrip("#")
        tweet_volume: int = raw_item.get("tweet_volume") or raw_item.get("public_metrics", {}).get("like_count", 0) or 0
        promoted = raw_item.get("promoted_content", False)

        return {
            "topic": name,
            "hashtags": [f"#{name.replace(' ', '')}"] if name else [],
            "promoted": promoted,
            "demand": {
                "volume": tweet_volume,
                "growth_rate": 0.0,  # not directly available
            },
            "saturation": {
                "creator_count": 0,
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": 0.0,
                "peak_acceleration": 0.0,
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized Twitter dict to a :class:`Trend`.

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
            suggested_formats=["thread", "tweet_series", "reply_chain"],
            pipeline_target="digital",
            raw=normalized,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_trending_topics(self) -> List[Dict[str, Any]]:
        """Call the v1.1 trends/place endpoint."""
        woeid = self.settings.twitter_woeid
        resp = self._client.get(
            "https://api.twitter.com/1.1/trends/place.json",
            params={"id": woeid},
        )
        resp.raise_for_status()
        return resp.json()[0].get("trends", [])

    def _fetch_via_search(self) -> List[Dict[str, Any]]:
        """Fall back to recent-search endpoint for keyword signals."""
        keywords = self.settings.twitter_seed_keywords
        items: List[Dict[str, Any]] = []
        for kw in keywords:
            try:
                resp = self._client.get(
                    "/tweets/search/recent",
                    params={
                        "query": f"{kw} lang:{self.settings.twitter_language} -is:retweet",
                        "max_results": 10,
                        "tweet.fields": "public_metrics,created_at",
                    },
                )
                resp.raise_for_status()
                for tweet in resp.json().get("data", []):
                    tweet["name"] = kw
                    items.append(tweet)
            except Exception as exc:
                logger.warning("Twitter search failed for %r: %s", kw, exc)
        return items
