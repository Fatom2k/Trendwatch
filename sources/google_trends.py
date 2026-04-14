"""Google Trends source connector.

Uses the `pytrends` unofficial API wrapper to fetch trending topics by
keyword and category.  No API key required.

Docs: https://github.com/GeneralMills/pytrends
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pytrends.request import TrendReq

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)


class GoogleTrendsSource(BaseSource):
    """Fetches trending topics from Google Trends via pytrends.

    Args:
        settings: Global configuration (country, language, keywords).
    """

    PLATFORM = "google_trends"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._pytrends = TrendReq(
            hl=self.settings.google_trends_language,
            tz=self.settings.google_trends_tz_offset,
            timeout=(10, 30),
            retries=3,
            backoff_factor=0.5,
        )

    # ------------------------------------------------------------------
    # BaseSource implementation
    # ------------------------------------------------------------------

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch real-time trending searches and interest-over-time data.

        Combines:
        * Daily trending searches (``trending_searches``).
        * Interest-over-time for the configured seed keywords.

        Returns:
            List of raw item dicts with at least ``keyword`` and
            ``growth_pct`` keys.
        """
        geo = self.settings.google_trends_geo
        items: List[Dict[str, Any]] = []

        # --- Daily trending searches --------------------------------
        try:
            trending = self._pytrends.trending_searches(pn=geo)
            for keyword in trending[0].tolist():
                items.append({"keyword": keyword, "source": "daily_trending", "growth_pct": 0.0})
        except Exception as exc:
            logger.warning("Could not fetch trending searches: %s", exc)

        # --- Interest over time for seed keywords -------------------
        keywords = self.settings.google_trends_keywords
        if keywords:
            for batch_start in range(0, len(keywords), 5):
                batch = keywords[batch_start : batch_start + 5]
                try:
                    self._pytrends.build_payload(batch, geo=geo, timeframe="now 7-d")
                    iot = self._pytrends.interest_over_time()
                    if not iot.empty:
                        for kw in batch:
                            if kw in iot.columns:
                                series = iot[kw]
                                growth = float(
                                    (series.iloc[-1] - series.iloc[0]) / max(series.iloc[0], 1)
                                )
                                items.append(
                                    {
                                        "keyword": kw,
                                        "source": "interest_over_time",
                                        "growth_pct": round(growth, 4),
                                        "avg_interest": round(float(series.mean()), 2),
                                    }
                                )
                    time.sleep(1)  # respect rate limits
                except Exception as exc:
                    logger.warning("pytrends batch failed for %s: %s", batch, exc)

        logger.debug("GoogleTrends fetched %d raw items.", len(items))
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single Google Trends item to the common schema.

        Args:
            raw_item: Dict with at minimum ``keyword`` and ``growth_pct``.

        Returns:
            Normalized dict compatible with :meth:`to_trend`.
        """
        keyword: str = raw_item.get("keyword", "")
        growth: float = raw_item.get("growth_pct", 0.0)
        avg_interest: float = raw_item.get("avg_interest", 50.0)

        return {
            "topic": keyword,
            "hashtags": [f"#{keyword.replace(' ', '')}"],
            "demand": {
                "volume": int(avg_interest * 10_000),
                "growth_rate": growth,
            },
            "saturation": {
                "creator_count": 0,   # not available from Google Trends
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": round(growth / 7, 4) if growth else 0.0,
                "peak_acceleration": 0.0,
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized Google Trends dict to a :class:`Trend`.

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
            suggested_formats=["thread", "carousel", "reel"],
            pipeline_target="digital",
            raw=normalized,
        )
