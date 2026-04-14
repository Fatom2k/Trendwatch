"""Digital content creation pipeline.

Transforms scored trends into structured content briefs for:
- Instagram (captions + hashtag sets)
- TikTok / Reels (video scripts)
- X / Twitter (thread outlines)
- YouTube Shorts (concept briefs)

Output artifacts are plain-text / Markdown files written to
``output/reports/digital/``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sources.base import Trend

logger = logging.getLogger(__name__)


class DigitalContentPipeline:
    """Generates content briefs and scripts from trend data.

    Args:
        output_dir: Directory where artifacts are written.
        webhook_url: Optional HTTP endpoint to POST each artifact.
    """

    def __init__(
        self,
        output_dir: str | Path = "output/reports/digital",
        webhook_url: Optional[str] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.webhook_url = webhook_url

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self, trends: List[Trend]) -> List[Dict]:
        """Generate content artifacts for all trends targeting digital output.

        Args:
            trends: Analysed trends (only ``pipeline_target == 'digital'``
                    are processed).

        Returns:
            List of artifact dicts, one per processed trend.
        """
        digital_trends = [t for t in trends if t.pipeline_target == "digital"]
        artifacts = [self._build_artifact(t) for t in digital_trends]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"digital_briefs_{timestamp}.json"
        out_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Digital pipeline: %d briefs written to %s.", len(artifacts), out_path)

        if self.webhook_url:
            self._post_webhook(artifacts)

        return artifacts

    # ------------------------------------------------------------------
    # Artifact builders
    # ------------------------------------------------------------------

    def _build_artifact(self, trend: Trend) -> Dict:
        """Build a content brief dict for a single trend."""
        formats = trend.suggested_formats or ["reel", "carousel"]
        return {
            "trend_id": trend.id,
            "topic": trend.topic,
            "platform": trend.platform,
            "score": trend.score,
            "hashtags": trend.hashtags,
            "summary": trend.summary,
            "briefs": {
                fmt: self._brief_for_format(trend, fmt) for fmt in formats
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _brief_for_format(self, trend: Trend, fmt: str) -> Dict:
        """Return a format-specific content brief dict."""
        topic = trend.topic
        hashtags_str = " ".join(trend.hashtags[:10])
        summary = trend.summary or f"Emerging trend: {topic}"

        briefs: Dict[str, Dict] = {
            "reel": {
                "type": "video_script",
                "hook": f"Have you heard about {topic}? Here's why it's blowing up ⬆️",
                "body": f"{summary}\n\nShow 3 quick examples or transitions related to {topic}.",
                "cta": "Follow for more trends like this!",
                "hashtags": hashtags_str,
                "duration_seconds": 30,
            },
            "carousel": {
                "type": "carousel_slides",
                "slide_1": f"🔥 Trend Alert: {topic}",
                "slide_2": summary,
                "slide_3": f"Why it matters: score {trend.score}/100",
                "slide_4": f"How to use it: pick one of these formats — {', '.join(trend.suggested_formats)}",
                "slide_5": f"Save this post! {hashtags_str}",
            },
            "thread": {
                "type": "twitter_thread",
                "tweet_1": f"🧵 Thread: Why {topic} is the next big thing (score {trend.score}/100)",
                "tweet_2": summary,
                "tweet_3": f"Key signals: volume={trend.demand.get('volume')}, growth={trend.demand.get('growth_rate')}",
                "tweet_4": f"Best content formats: {', '.join(trend.suggested_formats)}",
                "tweet_5": f"Hashtags to use: {hashtags_str}\n\nRT if useful!",
            },
            "story": {
                "type": "story_sequence",
                "frame_1": f"Did you know {topic} is trending?",
                "frame_2": summary,
                "frame_3": "Swipe up / tap link for the full report!",
            },
        }
        return briefs.get(fmt, {"type": fmt, "description": summary, "hashtags": hashtags_str})

    def _post_webhook(self, artifacts: List[Dict]) -> None:
        """POST artifacts to the configured webhook URL."""
        try:
            import httpx
            resp = httpx.post(self.webhook_url, json=artifacts, timeout=15.0)
            resp.raise_for_status()
            logger.info("Webhook delivered: %s", self.webhook_url)
        except Exception as exc:
            logger.error("Webhook delivery failed: %s", exc)
