"""Elasticsearch storage backend for TrendWatch.

Persists scored trends to a single-node Elasticsearch index,
enabling cross-cycle deduplication, historical tracking and
full-text search over trend data.

Requires ``elasticsearch>=8.0.0`` (included in requirements.txt).

Typical usage::

    store = TrendStore(host="http://localhost:9200")
    store.ensure_index()
    store.index_batch(trends)
    results = store.search(query="cottagecore", min_score=50)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk

from sources.base import Trend

logger = logging.getLogger(__name__)

# Elasticsearch index mapping matching the Trend dataclass
INDEX_MAPPING: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "id":                {"type": "keyword"},
            "platform":          {"type": "keyword"},
            "topic":             {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "hashtags":          {"type": "keyword"},
            "score":             {"type": "integer"},
            "demand":            {"type": "object", "dynamic": True},
            "saturation":        {"type": "object", "dynamic": True},
            "velocity":          {"type": "object", "dynamic": True},
            "detected_at":       {"type": "date"},
            "suggested_formats": {"type": "keyword"},
            "pipeline_target":   {"type": "keyword"},
            "cluster_id":        {"type": "keyword"},
            "summary":           {"type": "text"},
        }
    },
    "settings": {
        "number_of_shards": 1,       # single-node — no replica needed
        "number_of_replicas": 0,
    },
}


class TrendStore:
    """Elasticsearch-backed store for :class:`~sources.base.Trend` objects.

    Args:
        host:       Elasticsearch base URL (e.g. ``http://localhost:9200``).
        index_name: Name of the ES index to use.
    """

    def __init__(self, host: str = "http://localhost:9200", index_name: str = "trendwatch_trends") -> None:
        self.index_name = index_name
        self._es = Elasticsearch(host)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def ensure_index(self) -> None:
        """Create the index with the correct mapping if it does not exist.

        Safe to call on every startup — does nothing if the index already
        exists.
        """
        if not self._es.indices.exists(index=self.index_name):
            self._es.indices.create(index=self.index_name, body=INDEX_MAPPING)
            logger.info("Elasticsearch index '%s' created.", self.index_name)
        else:
            logger.debug("Elasticsearch index '%s' already exists.", self.index_name)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_trend(self, trend: Trend) -> None:
        """Index a single trend document.

        Uses ``trend.id`` as the document ``_id`` so re-indexing the same
        trend (same UUID) updates the existing document rather than creating
        a duplicate.

        Args:
            trend: A fully scored and analysed :class:`~sources.base.Trend`.
        """
        self._es.index(
            index=self.index_name,
            id=trend.id,
            document=trend.to_dict(),
        )
        logger.debug("Indexed trend '%s' (id=%s).", trend.topic, trend.id)

    def index_batch(self, trends: List[Trend]) -> int:
        """Bulk-index a list of trends.

        Uses ``elasticsearch.helpers.bulk`` for efficiency.  Each document
        uses ``trend.id`` as ``_id``.

        Args:
            trends: List of scored trends to persist.

        Returns:
            Number of successfully indexed documents.
        """
        if not trends:
            return 0

        actions = [
            {
                "_index": self.index_name,
                "_id": trend.id,
                "_source": trend.to_dict(),
            }
            for trend in trends
        ]

        success, errors = bulk(self._es, actions, raise_on_error=False)
        if errors:
            logger.warning("%d bulk indexing errors: %s", len(errors), errors[:3])
        logger.info("Bulk-indexed %d/%d trends to Elasticsearch.", success, len(trends))
        return success

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def exists_today(self, platform: str, topic: str) -> bool:
        """Check whether a trend with the same platform + topic was already
        indexed today (UTC day boundary).

        Used by the agent to skip re-processing trends that have already
        been stored in the current day's cycle.

        Args:
            platform: Platform slug (e.g. ``"tiktok"``).
            topic:    Trend label.

        Returns:
            ``True`` if a matching document exists with today's date.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"platform": platform}},
                        {"term": {"topic.keyword": topic}},
                        {"range": {"detected_at": {"gte": today}}},
                    ]
                }
            }
        }
        try:
            resp = self._es.count(index=self.index_name, body=query)
            return resp["count"] > 0
        except Exception as exc:
            logger.warning("exists_today check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: Optional[str] = None,
        platform: Optional[str] = None,
        min_score: int = 0,
        date_from: Optional[str] = None,
        size: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search indexed trends with optional filters.

        Args:
            query:     Full-text query applied to ``topic`` and ``summary``.
            platform:  Filter by platform slug.
            min_score: Minimum composite score (0–100).
            date_from: ISO date string lower bound for ``detected_at``
                       (e.g. ``"2025-04-01"``).
            size:      Maximum number of results to return.

        Returns:
            List of trend dicts sorted by score descending.
        """
        must: List[Dict[str, Any]] = []
        filter_: List[Dict[str, Any]] = []

        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": ["topic^3", "summary", "hashtags"],
                }
            })

        if platform:
            filter_.append({"term": {"platform": platform}})

        if min_score > 0:
            filter_.append({"range": {"score": {"gte": min_score}}})

        if date_from:
            filter_.append({"range": {"detected_at": {"gte": date_from}}})

        body: Dict[str, Any] = {
            "query": {"bool": {"must": must or [{"match_all": {}}], "filter": filter_}},
            "sort": [{"score": {"order": "desc"}}],
            "size": size,
        }

        resp = self._es.search(index=self.index_name, body=body)
        hits = resp["hits"]["hits"]
        return [hit["_source"] for hit in hits]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of indexed trend documents."""
        try:
            resp = self._es.count(index=self.index_name)
            return resp["count"]
        except NotFoundError:
            return 0

    def ping(self) -> bool:
        """Return ``True`` if the Elasticsearch cluster is reachable."""
        return self._es.ping()
