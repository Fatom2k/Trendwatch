"""Integration tests for the TrendWatchAgent orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.core import TrendWatchAgent
from config.settings import Settings
from sources.base import Trend


def _make_trend(topic: str = "test", score: int = 50) -> Trend:
    return Trend(
        platform="test",
        topic=topic,
        score=score,
        demand={"volume": 100_000, "growth_rate": 0.15},
        saturation={"creator_count": 500, "avg_post_age_days": 7},
        velocity={"daily_growth": 0.03, "peak_acceleration": 0.8},
    )


@patch("agent.core.TrendWatchAgent._build_sources")
def test_agent_run_no_sources(mock_sources):
    """Agent should gracefully return empty string when no trends collected."""
    mock_sources.return_value = []
    agent = TrendWatchAgent(settings=Settings())
    result = agent.run()
    assert result == ""


@patch("agent.core.TrendWatchAgent._build_sources")
@patch("agent.core.TrendSummarizer.summarize_batch")
@patch("agent.core.ReportWriter.write")
def test_agent_full_cycle(mock_write, mock_summarize, mock_sources):
    """Full cycle should call collect, analyze and report."""
    mock_trend = _make_trend(score=60)
    mock_source = MagicMock()
    mock_source.fetch.return_value = [{"topic": "test"}]
    mock_source.normalize.return_value = {
        "topic": "test",
        "hashtags": ["#test"],
        "demand": {"volume": 100_000, "growth_rate": 0.15},
        "saturation": {"creator_count": 500, "avg_post_age_days": 7},
        "velocity": {"daily_growth": 0.03, "peak_acceleration": 0.8},
    }
    mock_source.to_trend.return_value = mock_trend
    mock_sources.return_value = [mock_source]
    mock_summarize.side_effect = lambda t: t
    mock_write.return_value = "/tmp/report.md"

    agent = TrendWatchAgent(settings=Settings())
    result = agent.run()
    assert result == "/tmp/report.md"
    mock_write.assert_called_once()


def test_agent_analyze_filters_low_scores():
    """analyze() should drop trends below min_score_threshold."""
    settings = Settings()
    settings.min_score_threshold = 50
    settings.anthropic_api_key = ""  # disable AI summarization
    agent = TrendWatchAgent(settings=settings)

    low = _make_trend(topic="low", score=10)
    high = _make_trend(topic="high", score=80)

    with patch.object(agent._scorer, "score", side_effect=lambda t: t):
        with patch.object(agent._clusterer, "cluster", side_effect=lambda t: t):
            result = agent.analyze([low, high])

    topics = [t.topic for t in result]
    assert "high" in topics
    assert "low" not in topics
