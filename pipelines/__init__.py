"""TrendWatch pipelines package.

Pipelines are the output layer of TrendWatch.  They transform scored
trends into actionable artifacts for downstream consumers.
"""

from pipelines.content_digital import DigitalContentPipeline
from pipelines.content_physical import PhysicalContentPipeline

__all__ = ["DigitalContentPipeline", "PhysicalContentPipeline"]
