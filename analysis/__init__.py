"""TrendWatch analysis package.

Provides scoring, clustering and AI-powered summarization of trends.
"""

from analysis.scorer import TrendScorer
from analysis.clustering import TrendClusterer
from analysis.summarizer import TrendSummarizer

__all__ = ["TrendScorer", "TrendClusterer", "TrendSummarizer"]
