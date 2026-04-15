"""Google Trends CSV importer.

Handles CSV files manually exported from:
    https://trends.google.fr/trending?geo=FR&hours=4

Supports flexible column detection: case-insensitive fuzzy matching so that
column names like ``"Query"``, ``"Keyword"``, or ``"Titre de la recherche"``
are all handled correctly without manual configuration.
"""

from __future__ import annotations

import csv
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from importers.base import BaseImporter, ImportContext

logger = logging.getLogger(__name__)


class GoogleTrendsCsvImporter(BaseImporter):
    """Import Google Trends data from manually downloaded CSV files.

    Supported data categories:
    - ``"terms"``    — Search terms (Query + Increase percent columns)
    - ``"trending"`` — Trending topics (all columns kept as-is)

    Column detection is fuzzy: column names are normalised (lowercase,
    stripped of whitespace/punctuation) before comparison, with a
    SequenceMatcher fallback for near-matches.
    """

    SOURCE_KEY = "google_trends"
    SUPPORTED_CATEGORIES = ["terms", "trending"]

    def __init__(self) -> None:
        # Column mappings detected once during parse_rows(), reused in build_document()
        self.column_mapping: Dict[str, str] = {}  # keyword / volume / rank
        self.query_col: Optional[str] = None       # "Query" column for "terms" category
        self.increase_col: Optional[str] = None    # "Increase percent" column

    # ------------------------------------------------------------------
    # BaseImporter implementation
    # ------------------------------------------------------------------

    def parse_rows(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Read the CSV and yield one clean dict per data row.

        Skips header, blank rows, and rows that are entirely empty.
        Detects column mappings once on the first read.

        Args:
            file_path: Absolute path to the CSV file.

        Yields:
            Dict with original column names → stripped string values.
        """
        try:
            with open(file_path, encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    logger.error("CSV file is empty or has no header: %s", file_path)
                    return

                csv_columns = list(reader.fieldnames)
                logger.info("CSV columns detected: %s", csv_columns)
                self._detect_columns(csv_columns)

                for row in reader:
                    if not any(row.values()):
                        continue  # skip fully empty rows
                    yield {k: (v.strip() if v else "") for k, v in row.items()}

        except (OSError, csv.Error) as exc:
            logger.error("Failed to read CSV '%s': %s", file_path, exc)

    def build_document(
        self,
        row: Dict[str, Any],
        row_index: int,
        context: ImportContext,
    ) -> Dict[str, Any]:
        """Build the canonical ES document from a raw CSV row.

        For ``"terms"`` category: extracts ``title`` and ``trend`` from the
        detected Query/Increase-percent columns and nests all raw data under
        ``data``.

        For other categories: stores all columns under ``data`` with empty
        ``title``/``trend`` defaults.

        Args:
            row:       Raw dict from :meth:`parse_rows`.
            row_index: 1-based row index.
            context:   Upload metadata.

        Returns:
            ES document dict with mandatory envelope + category-specific fields.
        """
        envelope: Dict[str, Any] = {
            "_data_source":   context.source,
            "_data_category": context.data_category,
            "_geo":           context.geo,
            "_imported_at":   context.imported_at,
            "_csv_source":    context.filename,
            "_search_type":   context.search_type,
            "_time_range":    context.time_range,
            "_csv_row_index": row_index,
        }

        if context.data_category == "terms":
            return {**envelope, **self._build_terms_doc(row)}

        # Default: keep all columns nested under "data"
        return {**envelope, "title": "", "trend": 0, "data": row}

    def validate(self, file_path: Path, context: ImportContext) -> List[str]:
        """Check that the file exists and has a .csv extension."""
        errors = super().validate(file_path, context)
        if not errors and file_path.suffix.lower() != ".csv":
            errors.append(f"Expected a .csv file, got: {file_path.name}")
        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_terms_doc(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract title + trend value for the ``"terms"`` category."""
        title = row.get(self.query_col, "") if self.query_col else ""

        trend_val = 0
        if self.increase_col:
            raw = row.get(self.increase_col, "") or ""
            try:
                trend_val = int(float(raw.replace("%", "").strip()))
            except (ValueError, AttributeError):
                trend_val = 0

        return {"title": title, "trend": trend_val, "data": row}

    def _detect_columns(self, csv_columns: List[str]) -> None:
        """Detect all relevant column mappings from the CSV header.

        Populates:
        - ``self.column_mapping`` — keyword / volume / rank (legacy trend pipeline)
        - ``self.query_col``      — the "Query" column for terms category
        - ``self.increase_col``   — the "Increase percent" column for terms category
        """
        self.column_mapping = {}

        kw_col = self._find_column(csv_columns, ["Title", "Keyword", "Query", "Search", "Term", "Topic", "Name"])
        vol_col = self._find_column(csv_columns, ["Value", "Volume", "Traffic", "Count", "Trending", "Interest"])
        rank_col = self._find_column(csv_columns, ["Rank", "Position", "Ranking", "Index"])

        if kw_col:
            self.column_mapping["keyword"] = kw_col
        if vol_col:
            self.column_mapping["volume"] = vol_col
        if rank_col:
            self.column_mapping["rank"] = rank_col

        # Terms-specific columns
        self.query_col = self._find_column(csv_columns, ["Query", "Title", "Keyword", "Search", "Term"])
        self.increase_col = self._find_column(csv_columns, ["Increase percent", "Growth", "Change", "Increase"])

        logger.info(
            "Column mapping: %s | query_col=%s | increase_col=%s",
            self.column_mapping,
            self.query_col,
            self.increase_col,
        )

    @staticmethod
    def _normalize_column_name(col: str) -> str:
        """Lowercase + strip whitespace, underscores, and dashes."""
        return col.lower().strip().replace(" ", "").replace("_", "").replace("-", "")

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """SequenceMatcher similarity ratio between two strings (0.0–1.0)."""
        return SequenceMatcher(None, a, b).ratio()

    def _find_column(
        self,
        csv_columns: List[str],
        search_terms: List[str],
        threshold: float = 0.6,
    ) -> Optional[str]:
        """Find the first CSV column matching any search term.

        Tries exact normalised match first, then fuzzy similarity fallback.

        Args:
            csv_columns:  List of column names from the CSV header.
            search_terms: Candidate names to match against.
            threshold:    Minimum similarity score for fuzzy matching.

        Returns:
            Matching column name from ``csv_columns``, or ``None``.
        """
        norm_searches = [self._normalize_column_name(t) for t in search_terms]

        for col in csv_columns:
            norm_col = self._normalize_column_name(col)

            if norm_col in norm_searches:
                return col

            for norm_s in norm_searches:
                if self._similarity(norm_col, norm_s) >= threshold:
                    return col

        return None
