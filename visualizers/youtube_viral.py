"""YouTube Viral Videos visualizer.

Queries Elasticsearch for documents imported by YouTubeApiFetcher and
returns the data formatted for the youtube_viral visualization template.

Supports snapshot comparison: the ``snapshot_dates`` list in the returned
context lets the template filter cards by fetch date on the client side.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from visualizers.base import BaseVisualizer, VizContext

logger = logging.getLogger(__name__)


class YouTubeViralVisualizer(BaseVisualizer):
    """Visualizer for YouTube trending videos data.

    Displays a card grid (not a table) because thumbnails require
    horizontal space. Each card links directly to the YouTube video.

    Supports snapshot-based filtering: multiple fetches can be compared
    using the ``snapshot_dates`` selector in the template.
    """

    SOURCE_KEY = "youtube_viral"
    DISPLAY_NAME = "YouTube Viral Videos"
    SUPPORTED_CATEGORIES = ["trending"]
    TEMPLATE = "viz/youtube_viral.html"

    def fetch_data(self, store: Any, context: VizContext) -> Dict[str, Any]:
        """Query ES for YouTube documents and return template context.

        Args:
            store:   :class:`~storage.elasticsearch.TrendStore` instance.
            context: Viz parameters (geo, size, etc.).

        Returns:
            Template context dict with ``items``, ``total``,
            ``snapshot_dates`` (sorted desc), and active filter values.
        """
        items: List[Dict[str, Any]] = []

        try:
            items = store.search_documents(
                data_source=self.SOURCE_KEY,
                data_category=context.data_category or None,
                geo=context.geo or None,
                size=context.size,
            )
        except Exception as exc:
            logger.warning("YouTubeViralVisualizer.fetch_data failed: %s", exc)

        # Build sorted list of unique snapshot dates (YYYY-MM-DD) for the selector
        snapshot_dates: List[str] = sorted(
            {
                item.get("_snapshot_at", "")[:10]
                for item in items
                if item.get("_snapshot_at")
            },
            reverse=True,
        )

        # Group items by geo and get top 10 for each
        geo_groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            geo = item.get("_geo", "WW")
            if geo not in geo_groups:
                geo_groups[geo] = []
            geo_groups[geo].append(item)

        # Sort and truncate to top 10 per geo
        top_by_geo: Dict[str, List[Dict[str, Any]]] = {}
        for geo, group in geo_groups.items():
            # Sort by view_count descending
            sorted_group = sorted(
                group,
                key=lambda x: x.get("data", {}).get("view_count", 0),
                reverse=True
            )
            top_by_geo[geo] = sorted_group[:10]

        # Color palette for charts
        colors = [
            "#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4",
            "#3b82f6", "#8b5cf6", "#ec4899", "#f43f5e", "#14b8a6"
        ]

        return {
            "items":           items,
            "total":           len(items),
            "top_by_geo":      top_by_geo,
            "colors":          colors,
            "source_label":    self.DISPLAY_NAME,
            "categories":      self.SUPPORTED_CATEGORIES,
            "snapshot_dates":  snapshot_dates,
            "active_source":   context.source,
            "active_category": context.data_category,
            "active_geo":      context.geo,
            "active_time":     context.time_range,
            "active_search_type": context.search_type,
        }
