"""TrendWatch storage package.

Provides persistent storage backends for detected trends.
Currently implements an Elasticsearch backend suitable for
single-node containerised deployments.
"""

from storage.elasticsearch import TrendStore

__all__ = ["TrendStore"]
