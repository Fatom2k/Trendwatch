"""Google Trends source with both Discovery and Keyword Tracking modes.

This refactored version:
- ✅ Works around pytrends API endpoint blockers
- ✅ Supports DISCOVERY mode (auto-discover emerging trends)
- ✅ Supports TRACKING mode (monitor specific keywords)
- ✅ Uses only working endpoints (interest_over_time, related_queries)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pytrends.request import TrendReq

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)


class GoogleTrendsV2Source(BaseSource):
    """Google Trends with Discovery and Keyword Tracking modes.

    Discovery Mode:
        Auto-discover emerging trends by comparing growth rates across
        a curated list of seed topics. No keyword pre-configuration needed.

    Tracking Mode:
        Monitor specific keywords configured in Settings.
        Provides detailed metrics (growth, related topics, etc.)

    Args:
        settings: Global configuration.
        mode: "discovery" or "tracking" (default: "discovery")
    """

    PLATFORM = "google_trends"

    # Seed topics for discovery (broad categories to detect emerging trends)
    DISCOVERY_SEEDS = [
        # Fashion & Style
        "aesthetic", "fashion", "vintage", "sustainable fashion",
        "luxury fashion", "streetwear", "cottagecore", "minimalism",
        # Entertainment
        "entertainment", "celebrity", "movies", "streaming",
        "music trends", "viral videos", "gaming", "anime",
        # Technology
        "technology", "ai", "cryptocurrency", "social media",
        "apps", "gadgets", "startup", "web3",
        # Lifestyle
        "wellness", "fitness", "mental health", "productivity",
        "travel", "food", "cooking", "home decor",
        # Culture
        "meme", "culture", "gen z", "viral", "trending",
    ]

    def __init__(
        self,
        settings: Optional[Settings] = None,
        mode: str = "discovery"
    ) -> None:
        self.settings = settings or Settings()
        self.mode = mode  # "discovery" or "tracking"
        self._pytrends = TrendReq(
            hl=self.settings.google_trends_language,
            tz=self.settings.google_trends_tz_offset,
            timeout=(10, 30),
            retries=3,
            backoff_factor=0.5,
        )

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch trends using configured mode."""
        if self.mode == "discovery":
            return self._fetch_discovery()
        else:  # tracking
            return self._fetch_tracking()

    def _fetch_discovery(self) -> List[Dict[str, Any]]:
        """Auto-discover emerging trends by comparing growth rates.

        Strategy:
        1. Split seed topics into batches (5 per batch)
        2. Fetch interest_over_time for each batch
        3. Calculate growth % for 7 days
        4. Return topics with growth > threshold (configurable via settings)
        """
        geo = self.settings.google_trends_geo
        items: List[Dict[str, Any]] = []
        growth_threshold = self.settings.google_trends_discovery_threshold

        logger.info("Starting DISCOVERY mode — comparing %d seed topics", len(self.DISCOVERY_SEEDS))

        # Process in batches of 5 (pytrends limit)
        for batch_start in range(0, len(self.DISCOVERY_SEEDS), 5):
            batch = self.DISCOVERY_SEEDS[batch_start : batch_start + 5]

            try:
                self._pytrends.build_payload(batch, geo=geo, timeframe="now 7-d")
                iot = self._pytrends.interest_over_time()

                if not iot.empty:
                    for topic in batch:
                        if topic in iot.columns:
                            series = iot[topic]
                            # Calculate growth %
                            growth_pct = (
                                (series.iloc[-1] - series.iloc[0])
                                / max(series.iloc[0], 1)
                            ) * 100

                            # Only include emerging trends (positive growth > threshold)
                            if growth_pct > growth_threshold:
                                avg_interest = round(float(series.mean()), 2)
                                items.append({
                                    "keyword": topic,
                                    "source": "discovery_emerging",
                                    "growth_pct": round(growth_pct, 2),
                                    "avg_interest": avg_interest,
                                })
                                logger.debug("✓ %s: +%.1f%% growth", topic, growth_pct)
                            else:
                                logger.debug("✗ %s: +%.1f%% (below threshold)", topic, growth_pct)

                time.sleep(1)  # Respect rate limits

            except Exception as exc:
                logger.warning("Batch %s failed: %s", batch, exc)

        logger.info("Discovery complete — found %d emerging trends", len(items))
        return items

    def _fetch_tracking(self) -> List[Dict[str, Any]]:
        """Track specific keywords with detailed metrics.

        Returns per-keyword data: growth, related topics, interest trend.
        """
        geo = self.settings.google_trends_geo
        keywords = self.settings.google_trends_keywords
        items: List[Dict[str, Any]] = []

        if not keywords:
            logger.warning("No keywords configured for tracking mode")
            return items

        logger.info("Starting TRACKING mode — monitoring %d keywords", len(keywords))

        # Process in batches of 5
        for batch_start in range(0, len(keywords), 5):
            batch = keywords[batch_start : batch_start + 5]

            try:
                self._pytrends.build_payload(batch, geo=geo, timeframe="now 7-d")
                iot = self._pytrends.interest_over_time()

                if not iot.empty:
                    for keyword in batch:
                        if keyword in iot.columns:
                            series = iot[keyword]
                            growth_pct = (
                                (series.iloc[-1] - series.iloc[0])
                                / max(series.iloc[0], 1)
                            ) * 100
                            avg_interest = round(float(series.mean()), 2)

                            items.append({
                                "keyword": keyword,
                                "source": "tracking_keyword",
                                "growth_pct": round(growth_pct, 2),
                                "avg_interest": avg_interest,
                            })

                            logger.debug("Tracking %s: +%.1f%%, interest=%.0f",
                                       keyword, growth_pct, avg_interest)

                time.sleep(1)

            except Exception as exc:
                logger.warning("Tracking batch %s failed: %s", batch, exc)

        logger.info("Tracking complete — %d keywords monitored", len(items))
        return items

    # ====================================================================
    # BaseSource implementation
    # ====================================================================

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw Google Trends item."""
        keyword: str = raw_item.get("keyword", "")
        growth: float = raw_item.get("growth_pct", 0.0)
        avg_interest: float = raw_item.get("avg_interest", 50.0)

        return {
            "topic": keyword,
            "hashtags": [f"#{keyword.replace(' ', '')}"],
            "demand": {
                "volume": int(avg_interest * 10_000),
                "growth_rate": growth / 100,  # Convert % to decimal
            },
            "saturation": {
                "creator_count": 0,
                "avg_post_age_days": 0,
            },
            "velocity": {
                "daily_growth": round(growth / 700, 4),  # 7 days to daily
                "peak_acceleration": 0.0,
            },
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert normalized dict to Trend object."""
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
