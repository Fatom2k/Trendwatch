"""Core orchestrator for the TrendWatch agent.

This module defines TrendWatchAgent, the main entry point that coordinates
a full watch cycle: collect → analyze → store → report.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from analysis.clustering import TrendClusterer
from analysis.scorer import TrendScorer
from analysis.summarizer import TrendSummarizer
from agent.output import ReportWriter
from config.settings import Settings
from sources.base import Trend
from sources.google_trends_api import GoogleTrendsSource
from sources.exploding_topics import ExplodingTopicsSource

logger = logging.getLogger(__name__)


class TrendWatchAgent:
    """Orchestrates a complete trend-watching cycle.

    A single call to :meth:`run` will:
    1. Collect raw signals from all active sources.
    2. Analyse and cluster the collected trends.
    3. Score each trend on demand / saturation / velocity axes.
    4. Generate an AI-powered summary via the Claude API.
    5. Persist trends to Elasticsearch (if configured).
    6. Write a structured report to the output directory.

    Args:
        settings: Global configuration.  Defaults to :class:`~config.settings.Settings`.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._sources = self._build_sources()
        self._scorer = TrendScorer()
        self._clusterer = TrendClusterer()
        self._summarizer = TrendSummarizer(api_key=self.settings.anthropic_api_key)
        self._writer = ReportWriter(output_dir=self.settings.output_dir)
        self._store = self._build_store()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Execute a complete watch cycle and return the path to the report.

        Returns:
            Absolute path to the generated report file.
        """
        logger.info("TrendWatch cycle started at %s", datetime.now(timezone.utc).isoformat())

        trends = self.collect()
        if not trends:
            logger.warning("No trends collected — aborting cycle.")
            return ""

        trends = self.analyze(trends)

        # Persist to Elasticsearch when configured
        if self._store:
            try:
                self._store.index_batch(trends)
            except Exception as exc:  # noqa: BLE001
                logger.error("Elasticsearch indexing failed: %s", exc)

        report_path = self.report(trends)
        logger.info("Cycle complete.  Report: %s", report_path)
        return report_path

    def collect(self) -> List[Trend]:
        """Fetch raw trend signals from all active sources.

        Returns:
            Flat list of :class:`~sources.base.Trend` objects, deduplicated by
            (platform, topic) pair.
        """
        all_trends: List[Trend] = []
        seen: set[tuple[str, str]] = set()

        for source in self._sources:
            try:
                raw = source.fetch()
                normalized = [source.to_trend(source.normalize(item)) for item in raw]
                for trend in normalized:
                    key = (trend.platform, trend.topic.lower())
                    if key not in seen:
                        seen.add(key)
                        all_trends.append(trend)
            except Exception as exc:  # noqa: BLE001
                logger.error("Source %s failed: %s", source.__class__.__name__, exc)

        logger.info("Collected %d unique trends from %d sources.", len(all_trends), len(self._sources))
        return all_trends

    def analyze(self, trends: List[Trend]) -> List[Trend]:
        """Score, cluster and summarize a list of trends.

        Args:
            trends: Raw, unscored trends from :meth:`collect`.

        Returns:
            Enriched trends with ``score``, ``cluster_id`` and ``summary``
            fields populated.
        """
        scored = [self._scorer.score(t) for t in trends]

        filtered = [
            t for t in scored
            if t.score >= self.settings.min_score_threshold
        ]
        logger.info("%d/%d trends passed the score threshold.", len(filtered), len(scored))

        clustered = self._clusterer.cluster(filtered)

        if self.settings.anthropic_api_key:
            clustered = self._summarizer.summarize_batch(clustered)

        return clustered

    def report(self, trends: List[Trend]) -> str:
        """Persist an analysis report for the given trends.

        Args:
            trends: Analysed and scored trends.

        Returns:
            Path to the generated report.
        """
        return self._writer.write(trends)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_sources(self) -> list:
        """Instantiate active sources from configuration."""
        sources = []
        active = self.settings.active_platforms

        if "google_trends" in active:
            # GoogleTrendsSource: fetch top 50 trending searches
            # Backend options: "mock" (dev), "rapidapi" (prod), "direct" (blocked)
            # Content types: web_searches, social_video, news, shopping
            backend = getattr(self.settings, 'google_trends_backend', 'mock')
            rapidapi_key = getattr(self.settings, 'google_trends_rapidapi_key', '')
            sources.append(
                GoogleTrendsSource(
                    settings=self.settings,
                    backend=backend,
                    rapidapi_key=rapidapi_key,
                )
            )
        if "exploding_topics" in active:
            sources.append(
                ExplodingTopicsSource(
                    api_key=self.settings.exploding_topics_api_key,
                    settings=self.settings,
                )
            )
        return sources

    def _build_store(self):
        """Instantiate the Elasticsearch store if ES is enabled and reachable."""
        if not self.settings.elasticsearch_enabled:
            return None
        try:
            from storage.elasticsearch import TrendStore
            store = TrendStore(
                host=self.settings.elasticsearch_host,
                index_name=self.settings.elasticsearch_index,
            )
            if store.ping():
                store.ensure_index()
                logger.info("Elasticsearch store ready at %s.", self.settings.elasticsearch_host)
                return store
            logger.warning("Elasticsearch unreachable at %s — storage disabled.", self.settings.elasticsearch_host)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not initialise Elasticsearch store: %s", exc)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    agent = TrendWatchAgent()
    agent.run()
