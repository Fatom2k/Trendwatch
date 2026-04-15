"""TrendWatch data visualizers package.

The registry maps source keys to visualizer classes.
Routes never import a concrete visualizer directly — they call get_visualizer().

To add a new visualizer (paired with a new importer):
    1. Create ``visualizers/your_source.py`` inheriting ``BaseVisualizer``.
    2. Create ``web/templates/viz/your_source.html``.
    3. Add one line to ``_REGISTRY`` below.
    4. Nothing else changes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from visualizers.base import BaseVisualizer, VizContext
from visualizers.google_trends import GoogleTrendsVisualizer

_REGISTRY: Dict[str, Type[BaseVisualizer]] = {
    GoogleTrendsVisualizer.SOURCE_KEY: GoogleTrendsVisualizer,
    # "pinterest": PinterestVisualizer,
    # "tiktok_csv": TikTokVisualizer,
}


def get_visualizer(source: str) -> Optional[Type[BaseVisualizer]]:
    """Return the visualizer class for a given source key, or None.

    Args:
        source: Source key (e.g. ``"google_trends"``).

    Returns:
        Visualizer class (not an instance), or ``None`` if unregistered.
    """
    return _REGISTRY.get(source)


def list_visualizers() -> List[Dict[str, str]]:
    """Return all registered visualizers with display names.

    Used to populate source selector menus in the UI.

    Returns:
        List of ``{"key": ..., "label": ...}`` dicts.
    """
    return [
        {"key": cls.SOURCE_KEY, "label": cls.DISPLAY_NAME}
        for cls in _REGISTRY.values()
    ]


__all__ = ["BaseVisualizer", "VizContext", "get_visualizer", "list_visualizers"]
