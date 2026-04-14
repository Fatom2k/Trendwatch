"""Multi-criteria trend scoring engine.

Each trend is evaluated on three axes and assigned a composite score
between 0 and 100:

* **Demand**     (40 pts) — search / view volume + growth rate.
* **Saturation** (30 pts) — inverse of creator count and content age.
* **Velocity**   (30 pts) — speed of ascent and peak acceleration.

Weights are configurable via :class:`~config.settings.Settings`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from typing import Optional

from config.settings import Settings
from sources.base import Trend

logger = logging.getLogger(__name__)

# Default axis weights (must sum to 1.0)
DEFAULT_WEIGHTS = {
    "demand": 0.40,
    "saturation": 0.30,
    "velocity": 0.30,
}


class TrendScorer:
    """Scores a :class:`~sources.base.Trend` on demand, saturation and velocity.

    Args:
        settings: Optional global config used to read per-platform weight overrides.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._weights = {
            **DEFAULT_WEIGHTS,
            **self.settings.scorer_weight_overrides,
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def score(self, trend: Trend) -> Trend:
        """Compute and attach a composite score to *trend*.

        Args:
            trend: An unscored :class:`~sources.base.Trend`.

        Returns:
            A new :class:`~sources.base.Trend` instance with ``score`` set.
        """
        demand_score = self._score_demand(trend)
        saturation_score = self._score_saturation(trend)
        velocity_score = self._score_velocity(trend)

        composite = (
            demand_score * self._weights["demand"]
            + saturation_score * self._weights["saturation"]
            + velocity_score * self._weights["velocity"]
        )
        final_score = max(0, min(100, round(composite)))

        logger.debug(
            "Scored %r: demand=%d sat=%d vel=%d → %d",
            trend.topic, demand_score, saturation_score, velocity_score, final_score,
        )
        return replace(trend, score=final_score)

    # ------------------------------------------------------------------
    # Axis scoring helpers
    # ------------------------------------------------------------------

    def _score_demand(self, trend: Trend) -> float:
        """Score the demand axis (0–100).

        Combines absolute volume (log-normalized) and growth rate.

        Args:
            trend: Trend to evaluate.

        Returns:
            Demand sub-score between 0 and 100.
        """
        volume: int = trend.demand.get("volume", 0)
        growth: float = trend.demand.get("growth_rate", 0.0)

        # Log-normalize volume: 1M views ≈ 60 pts
        volume_score = min(100.0, math.log10(max(volume, 1)) / math.log10(10_000_000) * 100)

        # Growth rate: cap at 100% growth = 100 pts
        growth_score = min(100.0, max(0.0, growth * 100))

        return (volume_score * 0.6) + (growth_score * 0.4)

    def _score_saturation(self, trend: Trend) -> float:
        """Score the saturation axis (0–100, higher = less saturated).

        A low creator count and recent content age yields a high score.

        Args:
            trend: Trend to evaluate.

        Returns:
            Saturation sub-score between 0 and 100.
        """
        creator_count: int = trend.saturation.get("creator_count", 0)
        avg_age_days: float = trend.saturation.get("avg_post_age_days", 0)

        # Inverse creator density: < 100 creators ≈ 100 pts; > 100K ≈ 0
        creator_score = max(0.0, 100.0 - math.log10(max(creator_count, 1)) / math.log10(100_000) * 100)

        # Content freshness: 0 days = 100 pts; 90+ days = 0 pts
        age_score = max(0.0, 100.0 - (avg_age_days / 90.0) * 100)

        return (creator_score * 0.7) + (age_score * 0.3)

    def _score_velocity(self, trend: Trend) -> float:
        """Score the velocity axis (0–100).

        Measures how fast the trend is climbing.

        Args:
            trend: Trend to evaluate.

        Returns:
            Velocity sub-score between 0 and 100.
        """
        daily_growth: float = trend.velocity.get("daily_growth", 0.0)
        acceleration: float = trend.velocity.get("peak_acceleration", 0.0)

        # Daily growth: 10%/day = 100 pts
        daily_score = min(100.0, max(0.0, daily_growth * 1000))

        # Acceleration bonus: multiplicative factor
        accel_score = min(100.0, max(0.0, acceleration * 50))

        return (daily_score * 0.7) + (accel_score * 0.3)
