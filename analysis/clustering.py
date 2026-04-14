"""Thematic clustering of detected trends.

Groups trends by semantic proximity using TF-IDF + cosine similarity.
For larger datasets, a sentence-transformer embedding approach is
prepared as a drop-in replacement.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Dict, List, Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config.settings import Settings
from sources.base import Trend

logger = logging.getLogger(__name__)


class TrendClusterer:
    """Clusters a list of trends into thematic groups.

    Uses TF-IDF vectorisation of topic labels and hashtags, then applies
    agglomerative clustering.  Each trend receives a ``cluster_id`` string
    of the form ``"cluster_N``".

    Args:
        n_clusters:    Target number of clusters.  ``None`` triggers automatic
                       selection (sqrt heuristic).
        distance_threshold: Used when ``n_clusters`` is ``None``.
        settings:      Global configuration.
    """

    def __init__(
        self,
        n_clusters: Optional[int] = None,
        distance_threshold: float = 0.5,
        settings: Optional[Settings] = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.distance_threshold = distance_threshold
        self.settings = settings or Settings()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def cluster(self, trends: List[Trend]) -> List[Trend]:
        """Assign a ``cluster_id`` to each trend.

        Falls back to assigning every trend to ``cluster_0`` when the list
        is too small to cluster meaningfully (< 3 items).

        Args:
            trends: Scored trends without cluster assignment.

        Returns:
            Same trends with ``cluster_id`` populated.
        """
        if len(trends) < 3:
            return [replace(t, cluster_id="cluster_0") for t in trends]

        texts = self._build_texts(trends)
        labels = self._fit(texts)
        return [
            replace(trend, cluster_id=f"cluster_{label}")
            for trend, label in zip(trends, labels)
        ]

    def get_cluster_summary(self, trends: List[Trend]) -> Dict[str, List[str]]:
        """Return a dict mapping cluster_id → list of topic labels.

        Args:
            trends: Clustered trends (must have ``cluster_id`` set).

        Returns:
            Dict of ``{cluster_id: [topic, ...]}``, sorted by cluster id.
        """
        result: Dict[str, List[str]] = {}
        for trend in trends:
            key = trend.cluster_id or "cluster_0"
            result.setdefault(key, []).append(trend.topic)
        return dict(sorted(result.items()))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_texts(self, trends: List[Trend]) -> List[str]:
        """Build the corpus string for each trend."""
        texts = []
        for t in trends:
            hashtags_str = " ".join(h.lstrip("#") for h in t.hashtags)
            texts.append(f"{t.topic} {hashtags_str}")
        return texts

    def _fit(self, texts: List[str]) -> List[int]:
        """Vectorise texts and run agglomerative clustering."""
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        X = vectorizer.fit_transform(texts).toarray()

        n = self.n_clusters or max(2, int(np.sqrt(len(texts))))
        n = min(n, len(texts))

        model = AgglomerativeClustering(
            n_clusters=n,
            metric="cosine",
            linkage="average",
        )
        labels: List[int] = model.fit_predict(X).tolist()
        logger.debug("Clustered %d trends into %d groups.", len(texts), n)
        return labels
