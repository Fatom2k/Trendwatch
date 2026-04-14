"""Abstract base classes shared by every TrendWatch source connector.

All platform connectors must inherit from :class:`BaseSource` and implement
the three abstract methods :meth:`fetch`, :meth:`normalize`, and
:meth:`to_trend`.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Trend:
    """Canonical representation of a detected trend.

    This dataclass is the common currency across all modules — sources
    produce it, the scorer enriches it, pipelines consume it.

    Attributes:
        id:               Unique identifier (auto-generated UUID4).
        platform:         Source platform slug (e.g. ``"tiktok"``).
        topic:            Human-readable trend label.
        hashtags:         Associated hashtags (with leading ``#``).
        score:            Composite score 0–100 (set by the scorer).
        demand:           Demand metrics dict (volume, growth_rate).
        saturation:       Saturation metrics dict (creator_count, avg_post_age_days).
        velocity:         Velocity metrics dict (daily_growth, peak_acceleration).
        detected_at:      UTC timestamp of detection.
        suggested_formats: Content formats suitable for this trend.
        pipeline_target:  Downstream pipeline slug (``"digital"`` or ``"physical"``).
        cluster_id:       Thematic cluster assigned by the clusterer.
        summary:          AI-generated actionable insight.
        raw:              Original payload from the source API.
    """

    platform: str
    topic: str
    hashtags: List[str] = field(default_factory=list)
    score: int = 0
    demand: Dict[str, Any] = field(default_factory=dict)
    saturation: Dict[str, Any] = field(default_factory=dict)
    velocity: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    suggested_formats: List[str] = field(default_factory=list)
    pipeline_target: str = "digital"
    cluster_id: Optional[str] = None
    summary: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the trend to a plain dictionary."""
        return {
            "id": self.id,
            "platform": self.platform,
            "topic": self.topic,
            "hashtags": self.hashtags,
            "score": self.score,
            "demand": self.demand,
            "saturation": self.saturation,
            "velocity": self.velocity,
            "detected_at": self.detected_at,
            "suggested_formats": self.suggested_formats,
            "pipeline_target": self.pipeline_target,
            "cluster_id": self.cluster_id,
            "summary": self.summary,
        }


class BaseSource(ABC):
    """Abstract base class for all platform source connectors.

    Subclasses must implement:
    - :meth:`fetch`     — retrieve raw data from the platform.
    - :meth:`normalize` — convert one raw item to a stable dict.
    - :meth:`to_trend`  — convert a normalized dict to a :class:`Trend`.

    The orchestrator calls them in that order::

        raw_items  = source.fetch()
        normalized = [source.normalize(item) for item in raw_items]
        trends     = [source.to_trend(n) for n in normalized]
    """

    @abstractmethod
    def fetch(self) -> List[Any]:
        """Retrieve raw data from the platform.

        Returns:
            List of raw items (dicts, objects, etc.) as returned by the API
            or scraper.
        """

    @abstractmethod
    def normalize(self, raw_item: Any) -> Dict[str, Any]:
        """Convert a single raw API item to a stable intermediate dict.

        The returned dict must contain at minimum:
        - ``topic`` (str)
        - ``hashtags`` (list[str])
        - ``demand`` (dict)
        - ``saturation`` (dict)
        - ``velocity`` (dict)

        Args:
            raw_item: A single item from the :meth:`fetch` result.

        Returns:
            Normalized dictionary ready for :meth:`to_trend`.
        """

    @abstractmethod
    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert a normalized dict to a :class:`Trend` instance.

        Args:
            normalized: Output of :meth:`normalize`.

        Returns:
            A fully populated :class:`Trend` object.
        """
