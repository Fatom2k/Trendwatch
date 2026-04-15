"""Base classes for all file-based data importers.

Importers are intentionally separate from sources/ (live API connectors).
They receive an uploaded file on disk and produce raw Elasticsearch documents
without going through the Trend dataclass pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List


@dataclass(frozen=True)
class ImportContext:
    """Immutable metadata attached to a single file upload.

    Built once by the route and passed unchanged to every build_document() call.

    Attributes:
        filename:      Original uploaded filename (e.g. ``trends_FR_4h.csv``).
        source:        Source key (e.g. ``"google_trends"``).
        data_category: Data category (e.g. ``"terms"``, ``"trending"``).
        search_type:   Property type (``"web"``, ``"youtube"``, ``""`` if N/A).
        time_range:    Export time window (``"hours"``, ``"days"``, ``"months"``).
        geo:           Geographic code (``"FR"``, ``"US"``, ``""`` = worldwide).
        imported_at:   UTC ISO-8601 timestamp, set once by the route.
    """

    filename: str
    source: str
    data_category: str
    search_type: str
    time_range: str
    geo: str
    imported_at: str


class BaseImporter(ABC):
    """Abstract base class for all file-based importers.

    Subclass contract:
        1. Set ``SOURCE_KEY`` (str) — the value callers pass in the ``source``
           form field, e.g. ``"google_trends"``.
        2. Set ``SUPPORTED_CATEGORIES`` (list[str]) — ``data_category`` values
           this importer handles, e.g. ``["terms", "trending"]``.
        3. Implement :meth:`parse_rows` — reads the file, yields raw row dicts.
        4. Implement :meth:`build_document` — converts one raw row + context
           into the canonical ES document structure.

    The route calls them in this order::

        rows = list(importer.parse_rows(file_path))
        docs = [importer.build_document(row, idx, context) for ...]
    """

    SOURCE_KEY: str = ""
    SUPPORTED_CATEGORIES: List[str] = []

    @abstractmethod
    def parse_rows(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Read the file and yield one dict per data row.

        Implementations must:
        - Skip header lines, blank lines, and malformed rows silently.
        - Yield raw dicts preserving original column names.
        - Never raise on a single bad row; log a warning and continue.

        Args:
            file_path: Absolute path to the uploaded file on disk.

        Yields:
            One dict per data row, column names as keys.
        """

    @abstractmethod
    def build_document(
        self,
        row: Dict[str, Any],
        row_index: int,
        context: ImportContext,
    ) -> Dict[str, Any]:
        """Convert a single raw row into the canonical ES document.

        The returned dict must include the mandatory envelope fields:
        ``_data_source``, ``_data_category``, ``_geo``, ``_imported_at``,
        ``title``, ``trend``, ``data``.

        Args:
            row:       Raw dict from :meth:`parse_rows`.
            row_index: 1-based position of this row in the file.
            context:   Immutable upload metadata.

        Returns:
            Dict ready to pass to ``store.index_document()``.
        """

    def validate(self, file_path: Path, context: ImportContext) -> List[str]:
        """Optional pre-flight checks before parsing starts.

        Returns a list of human-readable error strings.
        An empty list means the file is valid and parsing can proceed.
        The base implementation only checks file existence.

        Args:
            file_path: Path to the uploaded file.
            context:   Upload metadata.

        Returns:
            List of error messages (empty = OK).
        """
        if not file_path.exists():
            return [f"File not found: {file_path}"]
        return []
