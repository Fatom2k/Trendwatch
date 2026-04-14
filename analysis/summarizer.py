"""AI-powered trend summarizer using the Anthropic Claude API.

Calls ``claude-sonnet-4-20250514`` to produce actionable insights from a
batch of trends, including suggested content formats and pipeline targets.

SDK docs: https://docs.anthropic.com/
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import List, Optional

import anthropic

from sources.base import Trend

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048

SYSTEM_PROMPT = """
You are TrendWatch AI, an expert content strategist and trend analyst.
You receive a JSON array of detected social media trends and must return
a JSON array (same length, same order) where each element contains:
- "summary": a 1-2 sentence actionable insight for content creators.
- "suggested_formats": list of recommended content formats
  (e.g. reel, carousel, thread, short, story, blog, product).
- "pipeline_target": either "digital" or "physical" depending on whether
  the trend is better suited to content creation or physical products.

Respond ONLY with a valid JSON array. No prose, no markdown fences.
"""


class TrendSummarizer:
    """Generates AI summaries and content recommendations for trends.

    Args:
        api_key: Anthropic API key.  If ``None``, summarization is skipped.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._client: Optional[anthropic.Anthropic] = (
            anthropic.Anthropic(api_key=api_key) if api_key else None
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def summarize_batch(self, trends: List[Trend]) -> List[Trend]:
        """Enrich a list of trends with AI-generated summaries.

        Processes trends in a single batched API call (up to 50 at a time)
        to minimize latency and cost.

        Args:
            trends: Scored and clustered trends.

        Returns:
            Trends with ``summary``, ``suggested_formats`` and
            ``pipeline_target`` updated from the AI response.
        """
        if not self._client:
            logger.warning("Anthropic API key not configured — skipping summarization.")
            return trends

        chunks = [trends[i : i + 50] for i in range(0, len(trends), 50)]
        enriched: List[Trend] = []
        for chunk in chunks:
            enriched.extend(self._summarize_chunk(chunk))
        return enriched

    def summarize_single(self, trend: Trend) -> Trend:
        """Enrich a single trend with an AI-generated summary.

        Args:
            trend: A scored trend.

        Returns:
            The same trend with ``summary`` and ``suggested_formats`` set.
        """
        results = self.summarize_batch([trend])
        return results[0] if results else trend

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _summarize_chunk(self, trends: List[Trend]) -> List[Trend]:
        """Call Claude API for a single chunk and merge the results."""
        payload = [
            {
                "topic": t.topic,
                "platform": t.platform,
                "score": t.score,
                "hashtags": t.hashtags[:5],
                "demand": t.demand,
                "velocity": t.velocity,
                "cluster_id": t.cluster_id,
            }
            for t in trends
        ]

        try:
            message = self._client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                ],
            )
            raw_text = message.content[0].text
            ai_results = json.loads(raw_text)
        except Exception as exc:
            logger.error("Claude API call failed: %s", exc)
            return trends

        if len(ai_results) != len(trends):
            logger.warning(
                "AI returned %d results for %d trends — skipping enrichment.",
                len(ai_results), len(trends),
            )
            return trends

        enriched = []
        for trend, ai in zip(trends, ai_results):
            enriched.append(
                replace(
                    trend,
                    summary=ai.get("summary", ""),
                    suggested_formats=ai.get("suggested_formats", trend.suggested_formats),
                    pipeline_target=ai.get("pipeline_target", trend.pipeline_target),
                )
            )
        return enriched
