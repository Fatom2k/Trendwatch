"""Unit tests for the sources module."""

from __future__ import annotations

import pytest

from sources.base import BaseSource, Trend
from sources.google_trends import GoogleTrendsSource
from sources.exploding_topics import ExplodingTopicsSource


# ---------------------------------------------------------------------------
# BaseSource contract
# ---------------------------------------------------------------------------

class MinimalSource(BaseSource):
    """Minimal concrete implementation for testing the abstract contract."""

    def fetch(self):
        return [{"keyword": "test trend", "growth_pct": 0.5, "avg_interest": 60.0}]

    def normalize(self, raw_item):
        return {
            "topic": raw_item["keyword"],
            "hashtags": [f"#{raw_item['keyword'].replace(' ', '')}"],
            "demand": {"volume": 600_000, "growth_rate": raw_item["growth_pct"]},
            "saturation": {"creator_count": 100, "avg_post_age_days": 5},
            "velocity": {"daily_growth": 0.07, "peak_acceleration": 1.2},
        }

    def to_trend(self, normalized):
        return Trend(
            platform="test",
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
        )


def test_base_source_contract():
    source = MinimalSource()
    raw = source.fetch()
    assert len(raw) == 1
    normalized = source.normalize(raw[0])
    assert "topic" in normalized
    trend = source.to_trend(normalized)
    assert isinstance(trend, Trend)
    assert trend.platform == "test"
    assert trend.topic == "test trend"


def test_trend_to_dict():
    trend = Trend(
        platform="tiktok",
        topic="cottagecore",
        hashtags=["#cottagecore"],
        score=75,
        demand={"volume": 1_000_000, "growth_rate": 0.25},
        saturation={"creator_count": 5000, "avg_post_age_days": 10},
        velocity={"daily_growth": 0.05, "peak_acceleration": 1.1},
    )
    d = trend.to_dict()
    assert d["platform"] == "tiktok"
    assert d["score"] == 75
    assert "demand" in d
    assert "saturation" in d
    assert "velocity" in d


def test_google_trends_normalize():
    source = GoogleTrendsSource()
    raw = {"keyword": "quiet luxury", "growth_pct": 0.42, "avg_interest": 72.0}
    normalized = source.normalize(raw)
    assert normalized["topic"] == "quiet luxury"
    assert normalized["demand"]["growth_rate"] == 0.42
    assert normalized["hashtags"] == ["#quietluxury"]


def test_google_trends_to_trend():
    source = GoogleTrendsSource()
    raw = {"keyword": "gorpcore", "growth_pct": 0.3, "avg_interest": 55.0}
    trend = source.to_trend(source.normalize(raw))
    assert isinstance(trend, Trend)
    assert trend.platform == "google_trends"
    assert trend.topic == "gorpcore"
