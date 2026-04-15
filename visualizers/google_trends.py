"""Google Trends visualizer.

Queries Elasticsearch for documents imported from Google Trends CSV files
and returns the data formatted for the google_trends visualization template.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from visualizers.base import BaseVisualizer, VizContext

logger = logging.getLogger(__name__)


class GoogleTrendsVisualizer(BaseVisualizer):
    """Visualizer for Google Trends imported data.

    Supports two categories:
    - ``"terms"``    — Search terms ranked by Increase percent
    - ``"trending"`` — Trending topics (raw data view)
    """

    SOURCE_KEY = "google_trends"
    DISPLAY_NAME = "Google Trends"
    SUPPORTED_CATEGORIES = ["terms", "trending"]
    TEMPLATE = "viz/google_trends.html"

    def fetch_data(self, store: Any, context: VizContext) -> Dict[str, Any]:
        """Query ES for Google Trends documents and return template context.

        Args:
            store:   :class:`~storage.elasticsearch.TrendStore` instance.
            context: Viz parameters (category, geo, time_range, size).

        Returns:
            Template context dict with ``items``, ``total``, ``geo_options``,
            ``categories``, ``source_label``, and the active filter values.
        """
        items: List[Dict[str, Any]] = []
        total = 0

        try:
            items = store.search_documents(
                data_source=context.source,
                data_category=context.data_category or None,
                geo=context.geo or None,
                time_range=context.time_range or None,
                search_type=context.search_type or None,
                size=context.size,
            )
            total = len(items)
        except Exception as exc:
            logger.warning("GoogleTrendsVisualizer.fetch_data failed: %s", exc)

        return {
            "items":         items,
            "total":         total,
            "source_label":  self.DISPLAY_NAME,
            "categories":    self.SUPPORTED_CATEGORIES,
            # Active filters (passed back to template for form state)
            "active_source":    context.source,
            "active_category":  context.data_category,
            "active_geo":       context.geo,
            "active_time":      context.time_range,
            "active_search_type": context.search_type,
        }
