"""TrendWatch sources package.

Each sub-module exposes a connector for a specific platform.
All connectors inherit from :class:`~sources.base.BaseSource`.
"""

from sources.base import BaseSource, Trend

__all__ = ["BaseSource", "Trend"]
