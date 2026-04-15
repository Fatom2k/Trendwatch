"""Base classes for all data visualizers.

Each visualizer knows how to query Elasticsearch for a specific data source
and return the context needed to render its associated template.
Visualizers are paired with importers via the same SOURCE_KEY string.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class VizContext:
    """Parameters controlling what data to fetch and how to display it.

    Built from HTTP query params by the route and passed to fetch_data().

    Attributes:
        source:        Source key matching BaseImporter.SOURCE_KEY.
        data_category: Data category to display (e.g. ``"terms"``).
        geo:           Geographic filter (``"FR"``, ``"US"``, ``""`` = all).
        time_range:    Time range filter (``"hours"``, ``"days"``, ``""`` = all).
        search_type:   Property type filter (``"web"``, ``""`` = all).
        size:          Maximum number of items to return.
        filters:       Extra source-specific filter params.
    """

    source: str
    data_category: str = "terms"
    geo: str = ""
    time_range: str = ""
    search_type: str = ""
    size: int = 50
    filters: Dict[str, Any] = field(default_factory=dict)


class BaseVisualizer(ABC):
    """Abstract base class for all data visualizers.

    Each visualizer is paired with an importer via ``SOURCE_KEY``.
    It queries Elasticsearch and returns template context for rendering.

    Subclass contract:
        1. Set ``SOURCE_KEY`` — must match the paired importer's SOURCE_KEY.
        2. Set ``DISPLAY_NAME`` — human-readable label for the UI.
        3. Set ``SUPPORTED_CATEGORIES`` — list of data_category values handled.
        4. Set ``TEMPLATE`` — path relative to ``web/templates/``.
        5. Implement :meth:`fetch_data` — query ES, return template context dict.
    """

    SOURCE_KEY: str = ""
    DISPLAY_NAME: str = ""
    SUPPORTED_CATEGORIES: List[str] = []
    TEMPLATE: str = ""

    @abstractmethod
    def fetch_data(
        self,
        store: Any,
        context: VizContext,
    ) -> Dict[str, Any]:
        """Query Elasticsearch and return the template context dict.

        The returned dict is merged into the TemplateResponse context.
        It must contain at minimum:
        - ``items`` (list[dict]) — rows to display
        - ``total`` (int) — total matching documents
        - ``source_label`` (str) — human-readable source name

        Args:
            store:   A :class:`~storage.elasticsearch.TrendStore` instance.
            context: Viz parameters from the HTTP request.

        Returns:
            Dict passed directly to the Jinja2 template.
        """

    def get_template(self, data_category: str = "") -> str:
        """Return the template path for the given category.

        Override to return a different template per category.
        Default returns ``self.TEMPLATE`` for all categories.

        Args:
            data_category: The requested data category.

        Returns:
            Template path relative to ``web/templates/``.
        """
        return self.TEMPLATE
