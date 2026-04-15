"""YouTube Viral Videos API fetcher.

Calls the YouTube Data API v3 ``videos.list`` endpoint with
``chart=mostPopular`` to retrieve the current top-50 trending videos,
for France (regionCode=FR) or worldwide (no regionCode).

Each fetch is stored as a timestamped snapshot in Elasticsearch, enabling
time-series comparison between multiple fetches.

Quota: ~100 units per call (out of 10 000/day default).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import Settings
from importers.base import BaseFetcher, FetchContext, QuotaExhaustedError

logger = logging.getLogger(__name__)


class YouTubeApiFetcher(BaseFetcher):
    """Fetch trending YouTube videos via the YouTube Data API v3.

    Two geographic scopes are supported:
    - ``geo="FR"`` → ``regionCode=FR`` (stored as _geo="FR")
    - ``geo=""``   → worldwide (stored as _geo="")

    Quota tracking is in-memory per instance (sufficient for manual usage).
    """

    SOURCE_KEY = "youtube_viral"
    DISPLAY_NAME = "YouTube Viral Videos"
    SUPPORTED_CATEGORIES = ["trending"]

    # Cost in API units for one videos.list call (snippet + statistics + contentDetails)
    QUOTA_COST_PER_CALL = 100

    def __init__(self) -> None:
        s = Settings()
        self._api_key: str = s.youtube_api_key
        self._daily_limit: int = s.youtube_quota_daily_limit
        self._units_consumed: int = 0

    # ------------------------------------------------------------------
    # BaseFetcher implementation
    # ------------------------------------------------------------------

    def fetch(self, context: FetchContext) -> List[Dict[str, Any]]:
        """Call ``videos.list`` and return the raw video resource dicts.

        Args:
            context: Fetch parameters (geo, extra.max_results, etc.)

        Returns:
            List of YouTube video resource dicts from ``items[]``.

        Raises:
            :class:`~importers.base.QuotaExhaustedError`: if daily quota is reached.
        """
        if not self._api_key:
            logger.error("YOUTUBE_API_KEY is not configured.")
            return []

        self._check_quota()

        max_results = min(int(context.extra.get("max_results", 50)), 50)

        try:
            youtube = build("youtube", "v3", developerKey=self._api_key)

            request_kwargs: Dict[str, Any] = {
                "part":       "snippet,statistics,contentDetails",
                "chart":      "mostPopular",
                "maxResults": max_results,
                "hl":         "fr" if context.geo == "FR" else "en",
            }
            if context.geo:
                request_kwargs["regionCode"] = context.geo

            response = youtube.videos().list(**request_kwargs).execute()

            self._units_consumed += self.QUOTA_COST_PER_CALL
            self._log_quota_status()

            items: List[Dict[str, Any]] = response.get("items", [])
            logger.info(
                "YouTube fetch: %d videos retrieved (geo=%s, quota_used=%d/%d)",
                len(items),
                context.geo or "WW",
                self._units_consumed,
                self._daily_limit,
            )
            return items

        except HttpError as exc:
            if exc.resp.status == 403:
                logger.error("YouTube API quota exceeded or forbidden: %s", exc)
                raise QuotaExhaustedError(
                    f"YouTube API returned 403 — quota may be exhausted "
                    f"({self._units_consumed}/{self._daily_limit} units consumed)"
                ) from exc
            logger.error("YouTube API HTTP error: %s", exc)
            return []
        except Exception as exc:
            logger.error("YouTube fetch failed: %s", exc)
            return []

    def build_document(
        self,
        raw_item: Dict[str, Any],
        item_index: int,
        context: FetchContext,
    ) -> Dict[str, Any]:
        """Convert a YouTube video resource dict to the canonical ES document.

        ``trend`` is set to ``viewCount`` so that ``search_documents()``
        (which sorts by ``trend`` desc) returns the most-viewed videos first.

        ``_snapshot_at`` is separate from ``_imported_at`` to allow future
        time-series queries grouping documents by fetch timestamp.

        Args:
            raw_item:   Single item from the YouTube ``items[]`` array.
            item_index: 1-based rank in this fetch (1 = most popular).
            context:    Fetch parameters.

        Returns:
            ES document dict with mandatory envelope + YouTube-specific fields.
        """
        snippet = raw_item.get("snippet", {})
        statistics = raw_item.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})

        def _int(val: Any) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        thumbnail_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )
        thumbnail_medium_url = (
            thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )

        view_count = _int(statistics.get("viewCount"))
        video_id = raw_item.get("id", "")
        geo = context.geo or "WW"

        # Generate deterministic document ID to enable deduplication on re-fetch
        doc_id = f"youtube_viral#{geo}#{video_id}"

        return {
            "_data_source":   self.SOURCE_KEY,
            "_data_category": context.data_category,
            "_geo":           context.geo or "",
            "_imported_at":   context.fetched_at,
            "_snapshot_at":   context.fetched_at,
            "_fetch_source":  "youtube_api_v3",
            "_doc_id":        doc_id,
            "title":          snippet.get("title", ""),
            "trend":          view_count,
            "data": {
                "video_id":             video_id,
                "channel_title":        snippet.get("channelTitle", ""),
                "channel_id":           snippet.get("channelId", ""),
                "published_at":         snippet.get("publishedAt", ""),
                "view_count":           view_count,
                "like_count":           _int(statistics.get("likeCount")),
                "comment_count":        _int(statistics.get("commentCount")),
                "category_id":          snippet.get("categoryId", ""),
                "tags":                 snippet.get("tags", []),
                "thumbnail_url":        thumbnail_url,
                "thumbnail_medium_url": thumbnail_medium_url,
                "rank":                 item_index,
            },
        }

    # ------------------------------------------------------------------
    # Quota helpers
    # ------------------------------------------------------------------

    def _check_quota(self) -> None:
        """Raise QuotaExhaustedError if consumed units >= daily limit."""
        if self._units_consumed >= self._daily_limit:
            raise QuotaExhaustedError(
                f"YouTube API daily quota exhausted "
                f"({self._units_consumed}/{self._daily_limit} units consumed)."
            )

    def _log_quota_status(self) -> None:
        """Log a warning when quota consumption reaches 80%."""
        if self._daily_limit > 0:
            ratio = self._units_consumed / self._daily_limit
            if ratio >= 1.0:
                logger.error(
                    "YouTube API quota exhausted: %d/%d units consumed.",
                    self._units_consumed, self._daily_limit,
                )
            elif ratio >= 0.8:
                logger.warning(
                    "YouTube API quota at %.0f%%: %d/%d units consumed.",
                    ratio * 100, self._units_consumed, self._daily_limit,
                )
            else:
                logger.debug(
                    "YouTube quota: %d/%d units consumed.",
                    self._units_consumed, self._daily_limit,
                )
