"""TrendWatch importers package.

Two separate registries coexist:

- **File importers** (``_FILE_REGISTRY``): handle uploaded files (CSV, etc.)
  via ``BaseImporter``. Triggered by ``POST /import/csv``.

- **API fetchers** (``_FETCHER_REGISTRY``): call live APIs on demand via
  ``BaseFetcher``. Triggered by ``POST /import/fetch``.

Both patterns ultimately call ``store.index_document()`` and store data
with the same ``_data_*`` envelope, so the same visualizers apply.

To add a new file importer:
    1. Create ``importers/your_source.py`` inheriting ``BaseImporter``.
    2. Add one line to ``_FILE_REGISTRY``.

To add a new API fetcher:
    1. Create ``importers/your_source.py`` inheriting ``BaseFetcher``.
    2. Add one line to ``_FETCHER_REGISTRY``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from importers.base import (
    BaseImporter,
    BaseFetcher,
    ImportContext,
    FetchContext,
    QuotaExhaustedError,
)
from importers.google_trends_csv import GoogleTrendsCsvImporter
from importers.youtube_viral import YouTubeApiFetcher

# ---------------------------------------------------------------------------
# File importers (CSV uploads)
# ---------------------------------------------------------------------------

_FILE_REGISTRY: Dict[str, Type[BaseImporter]] = {
    GoogleTrendsCsvImporter.SOURCE_KEY: GoogleTrendsCsvImporter,
    # "pinterest":  PinterestCsvImporter,
}


def get_importer(source: str) -> Optional[Type[BaseImporter]]:
    """Return the file importer class for a given source key, or None."""
    return _FILE_REGISTRY.get(source)


def list_sources() -> List[Dict[str, str]]:
    """Return all registered file importer keys with display names."""
    labels = {
        "google_trends": "Google Trends",
    }
    return [
        {"key": key, "label": labels.get(key, key.replace("_", " ").title())}
        for key in _FILE_REGISTRY
    ]


# ---------------------------------------------------------------------------
# API fetchers (live API calls)
# ---------------------------------------------------------------------------

_FETCHER_REGISTRY: Dict[str, Type[BaseFetcher]] = {
    YouTubeApiFetcher.SOURCE_KEY: YouTubeApiFetcher,
    # "tiktok_live": TikTokLiveFetcher,
}


def get_fetcher(source: str) -> Optional[Type[BaseFetcher]]:
    """Return the API fetcher class for a given source key, or None."""
    return _FETCHER_REGISTRY.get(source)


def list_fetchers() -> List[Dict[str, str]]:
    """Return all registered API fetcher keys with display names."""
    return [
        {"key": cls.SOURCE_KEY, "label": cls.DISPLAY_NAME}
        for cls in _FETCHER_REGISTRY.values()
    ]


__all__ = [
    "BaseImporter", "ImportContext", "get_importer", "list_sources",
    "BaseFetcher", "FetchContext", "QuotaExhaustedError", "get_fetcher", "list_fetchers",
]
