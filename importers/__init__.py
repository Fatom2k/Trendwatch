"""TrendWatch file importers package.

The registry maps source keys to importer classes.
Routes never import a concrete importer directly — they call get_importer().

To add a new importer:
    1. Create ``importers/your_source.py`` inheriting ``BaseImporter``.
    2. Add one line to ``_REGISTRY`` below.
    3. Nothing else changes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from importers.base import BaseImporter, ImportContext
from importers.google_trends_csv import GoogleTrendsCsvImporter

_REGISTRY: Dict[str, Type[BaseImporter]] = {
    GoogleTrendsCsvImporter.SOURCE_KEY: GoogleTrendsCsvImporter,
    # "pinterest":  PinterestCsvImporter,
    # "tiktok_csv": TikTokCsvImporter,
}


def get_importer(source: str) -> Optional[Type[BaseImporter]]:
    """Return the importer class for a given source key, or None.

    Args:
        source: Value from the upload form's ``source`` field.

    Returns:
        Importer class (not an instance), or ``None`` if unregistered.
    """
    return _REGISTRY.get(source)


def list_sources() -> List[Dict[str, str]]:
    """Return all registered source keys with their display names.

    Used to populate the source dropdown in the import form.

    Returns:
        List of ``{"key": ..., "label": ...}`` dicts.
    """
    labels = {
        "google_trends": "Google Trends",
    }
    return [
        {"key": key, "label": labels.get(key, key.replace("_", " ").title())}
        for key in _REGISTRY
    ]


__all__ = ["BaseImporter", "ImportContext", "get_importer", "list_sources"]
