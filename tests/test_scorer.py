"""Unit tests for the analysis.scorer module."""

from __future__ import annotations

import pytest

from analysis.scorer import TrendScorer
from sources.base import Trend


def _make_trend(**kwargs) -> Trend:
    defaults = dict(
        platform="test",
        topic="test topic",
        demand={"volume": 500_000, "growth_rate": 0.2},
        saturation={"creator_count": 1000, "avg_post_age_days": 15},
        velocity={"daily_growth": 0.05, "peak_acceleration": 1.0},
    )
    defaults.update(kwargs)
    return Trend(**defaults)


def test_scorer_returns_trend():
    scorer = TrendScorer()
    trend = _make_trend()
    scored = scorer.score(trend)
    assert isinstance(scored, Trend)


def test_scorer_score_range():
    scorer = TrendScorer()
    trend = _make_trend()
    scored = scorer.score(trend)
    assert 0 <= scored.score <= 100


def test_high_demand_raises_score():
    scorer = TrendScorer()
    low = _make_trend(demand={"volume": 100, "growth_rate": 0.01})
    high = _make_trend(demand={"volume": 50_000_000, "growth_rate": 1.5})
    assert scorer.score(high).score > scorer.score(low).score


def test_high_saturation_lowers_score():
    scorer = TrendScorer()
    fresh = _make_trend(saturation={"creator_count": 10, "avg_post_age_days": 1})
    saturated = _make_trend(saturation={"creator_count": 500_000, "avg_post_age_days": 180})
    assert scorer.score(fresh).score > scorer.score(saturated).score


def test_score_is_immutable():
    """Original trend must not be mutated."""
    scorer = TrendScorer()
    trend = _make_trend()
    original_score = trend.score
    scorer.score(trend)
    assert trend.score == original_score


def test_zero_volume_does_not_crash():
    scorer = TrendScorer()
    trend = _make_trend(demand={"volume": 0, "growth_rate": 0.0})
    scored = scorer.score(trend)
    assert scored.score >= 0
