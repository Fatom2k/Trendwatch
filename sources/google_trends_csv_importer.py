"""CSV importer for Google Trends data.

Users manually download CSVs from https://trends.google.fr/trending?geo=FR&hours=4
This module parses and normalizes them into Trend objects.

Supports ANY CSV format by intelligently detecting columns:
- Handles case-insensitive column names (Title, title, TITLE)
- Fuzzy matches column names with whitespace/underscore variations
- Gracefully falls back to defaults for missing columns
- Auto-detects column types based on content
"""

from __future__ import annotations

import csv
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import Settings
from sources.base import BaseSource, Trend

logger = logging.getLogger(__name__)


class GoogleTrendsCSVImporter(BaseSource):
    """Import Google Trends data from manually downloaded CSV files.

    Args:
        csv_path: Path to the CSV file (absolute or relative to output/).
        content_type: Data category (web_searches, news, shopping, etc.)
        geo: Geographic code (FR, US, etc.). "" = worldwide.
        gprop: Property type (web, youtube, news, shopping, images).
        settings: Global configuration.

    Example:
        importer = GoogleTrendsCSVImporter(
            csv_path="google_trends_FR_4h.csv",
            content_type="web_searches",
            geo="FR"
        )
        trends = importer.fetch()
    """

    PLATFORM = "google_trends"

    def __init__(
        self,
        csv_path: str,
        content_type: str = "web_searches",
        geo: str = "FR",
        gprop: str = "web",
        settings: Optional[Settings] = None,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.content_type = content_type
        self.geo = geo
        self.gprop = gprop
        self.settings = settings or Settings()
        self.column_mapping: Dict[str, str] = {}  # Maps detected cols to standard names

        # If path is relative, search in donnees/uploads/ and donnees/samples/
        if not self.csv_path.is_absolute():
            search_paths = [
                Path("donnees/uploads") / self.csv_path,
                Path("donnees/samples") / self.csv_path,
                Path(self.csv_path),
            ]
            for candidate in search_paths:
                if candidate.exists():
                    self.csv_path = candidate
                    break

    @staticmethod
    def _normalize_column_name(col: str) -> str:
        """Normalize column name for comparison.

        Converts to lowercase and removes spaces/underscores/dashes.
        Example: "Search Volume" -> "searchvolume"
        """
        return col.lower().strip().replace(" ", "").replace("_", "").replace("-", "")

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, a, b).ratio()

    def _find_column(
        self,
        csv_columns: List[str],
        search_terms: List[str],
        threshold: float = 0.6,
    ) -> Optional[str]:
        """Find a column in CSV that matches any of the search terms.

        Uses fuzzy matching with a similarity threshold.
        Returns the matching CSV column name, or None if not found.
        """
        normalized_searches = [self._normalize_column_name(term) for term in search_terms]

        for csv_col in csv_columns:
            normalized_csv = self._normalize_column_name(csv_col)

            # Check for exact match
            if normalized_csv in normalized_searches:
                logger.debug(f"Exact match found: '{csv_col}' -> {search_terms}")
                return csv_col

            # Check for fuzzy match with similarity
            for search_term, norm_search in zip(search_terms, normalized_searches):
                similarity = self._similarity(normalized_csv, norm_search)
                if similarity >= threshold:
                    logger.debug(
                        f"Fuzzy match: '{csv_col}' matched '{search_term}' "
                        f"(similarity: {similarity:.2f})"
                    )
                    return csv_col

        return None

    def _detect_columns(self, csv_columns: List[str]) -> None:
        """Detect and map CSV columns to standard names.

        Stores mapping in self.column_mapping for later use.
        """
        # Column detection groups with priority order
        keyword_terms = ["Title", "Keyword", "Query", "Search", "Term", "Topic", "Name"]
        volume_terms = ["Value", "Volume", "Traffic", "Count", "Trending", "Interest"]
        rank_terms = ["Rank", "Position", "Ranking", "Index"]

        keyword_col = self._find_column(csv_columns, keyword_terms)
        volume_col = self._find_column(csv_columns, volume_terms)
        rank_col = self._find_column(csv_columns, rank_terms)

        self.column_mapping = {}
        if keyword_col:
            self.column_mapping["keyword"] = keyword_col
        if volume_col:
            self.column_mapping["volume"] = volume_col
        if rank_col:
            self.column_mapping["rank"] = rank_col

        logger.info(
            "Column mapping detected: %s (from CSV columns: %s)",
            self.column_mapping,
            csv_columns,
        )

    def fetch(self) -> List[Dict[str, Any]]:
        """Parse the CSV file and return raw rows with original column names.

        Returns each row as-is with column names preserved from the CSV.
        """
        if not self.csv_path.exists():
            logger.error("CSV file not found: %s", self.csv_path)
            return []

        items: List[Dict[str, Any]] = []

        try:
            with open(self.csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    logger.error("CSV file is empty or malformed: %s", self.csv_path)
                    return []

                csv_columns = list(reader.fieldnames)
                logger.info("CSV raw columns: %s", csv_columns)

                # Detect and map columns for optional trend enrichment
                self._detect_columns(csv_columns)

                total_rows = 0
                for idx, row in enumerate(reader, start=1):
                    total_rows = idx
                    # Store raw CSV data as-is with original column names
                    if any(row.values()):  # Skip completely empty rows
                        # Clean up empty values
                        clean_row = {k: v.strip() if v else "" for k, v in row.items()}
                        items.append(clean_row)

        except (IOError, csv.Error) as exc:
            logger.error("Failed to read CSV file: %s", exc)
            return []

        logger.info(
            "✅ Imported %d rows from CSV: %s (columns: %s)",
            len(items),
            self.csv_path.name,
            csv_columns if 'csv_columns' in locals() else [],
        )

        return items

    def _parse_row(self, row: Dict[str, str], rank: int) -> Optional[Dict[str, Any]]:
        """Parse a single CSV row using detected column mapping.

        Uses the column mapping detected in fetch() to extract values.
        Provides sensible defaults for missing columns.
        """
        # Extract keyword using detected column mapping
        keyword = None
        if "keyword" in self.column_mapping:
            col = self.column_mapping["keyword"]
            if col in row and row[col].strip():
                keyword = row[col].strip()

        if not keyword:
            logger.debug("Row %d: no keyword found, skipping", rank)
            return None

        # Extract volume using detected column mapping
        volume = 1000  # Default volume if not found
        if "volume" in self.column_mapping:
            col = self.column_mapping["volume"]
            if col in row and row[col].strip():
                try:
                    # Handle percentage values (e.g., "100%")
                    vol_str = row[col].strip().replace("%", "").strip()
                    volume = max(1, int(float(vol_str)))  # Ensure at least 1
                except (ValueError, AttributeError):
                    logger.debug("Row %d: could not parse volume '%s', using default", rank, row[col])

        # Extract rank using detected column mapping
        item_rank = rank
        if "rank" in self.column_mapping:
            col = self.column_mapping["rank"]
            if col in row and row[col].strip():
                try:
                    item_rank = int(row[col].strip())
                except ValueError:
                    logger.debug("Row %d: could not parse rank '%s', using row index", rank, row[col])

        return {
            "keyword": keyword,
            "rank": item_rank,
            "search_volume": volume,
            "geo": self.geo or "worldwide",
            "gprop": self.gprop,
            "source": "google_trends_csv_import",
        }

    # ====================================================================
    # BaseSource implementation
    # ====================================================================

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Return raw CSV row with original column names.

        Preserves all column names from the CSV as-is.
        Just adds metadata for tracking.
        """
        return {
            **raw_item,  # Keep all original CSV columns
            "_csv_imported": True,
            "_geo": self.geo or "worldwide",
            "_gprop": self.gprop,
            "_import_source": "google_trends_csv_import",
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        """Convert normalized dict to Trend object."""
        metadata = normalized.pop("raw_metadata", {})

        return Trend(
            platform=self.PLATFORM,
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
            suggested_formats=["thread", "carousel", "reel"],
            pipeline_target="digital",
            content_type=self.content_type,
            raw={
                **normalized,
                **metadata,
            },
        )
