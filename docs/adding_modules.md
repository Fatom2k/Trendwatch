# Adding New Modules

TrendWatch has three distinct patterns for data ingestion, each producing Elasticsearch documents with the same unified structure. Choose the pattern that fits your data source.

## Unified Document Structure

All documents indexed into Elasticsearch share this envelope:

```json
{
  "_data_source":   "source_key",
  "_data_category": "category_key",
  "_geo":           "FR",
  "_imported_at":   "2026-04-15T10:00:00Z",
  "title":          "Human-readable label",
  "trend":          1234,
  "data":           { /* source-specific payload */ }
}
```

Optional fields:
- `_snapshot_at` — timestamp for time-series snapshots (YouTube, etc.)
- `_fetch_source` — which API was called
- `_csv_source`, `_csv_row_index`, `_search_type`, `_time_range` — CSV import metadata

---

## Pattern A — BaseImporter (CSV / File Upload)

Use when data comes from an uploaded file (CSV, JSON, etc.).

### Files to create/modify

| Action | File |
|--------|------|
| CREATE | `importers/my_source.py` |
| CREATE | `visualizers/my_source.py` |
| CREATE | `web/templates/viz/my_source.html` |
| MODIFY | `importers/__init__.py` — add to `_FILE_REGISTRY` |
| MODIFY | `visualizers/__init__.py` — add to `_REGISTRY` |

### Importer

```python
# importers/my_source.py
from importers.base import BaseImporter, ImportContext
from pathlib import Path
from typing import Dict, Any, Iterator, List

class MySourceImporter(BaseImporter):
    SOURCE_KEY = "my_source"
    DISPLAY_NAME = "My Source"
    SUPPORTED_CATEGORIES = ["terms", "trending"]

    def validate(self, file_path: Path, context: ImportContext) -> List[str]:
        # Return list of error strings, empty = OK
        if not file_path.exists():
            return ["File not found"]
        return []

    def parse_rows(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        import csv
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield dict(row)

    def build_document(self, row: Dict[str, Any], row_index: int,
                       context: ImportContext) -> Dict[str, Any]:
        return {
            "_data_source":   self.SOURCE_KEY,
            "_data_category": context.data_category,
            "_geo":           context.geo,
            "_imported_at":   context.imported_at,
            "_csv_source":    context.filename,
            "_csv_row_index": row_index,
            "title":          row.get("Keyword", ""),
            "trend":          int(row.get("Volume", 0)),
            "data":           dict(row),
        }
```

### Register

```python
# importers/__init__.py
from importers.my_source import MySourceImporter

_FILE_REGISTRY: Dict[str, Type[BaseImporter]] = {
    # existing entries...
    MySourceImporter.SOURCE_KEY: MySourceImporter,
}
```

---

## Pattern B — BaseFetcher (Live API, triggered from UI)

Use when data comes from an external API called on-demand via a button in the web interface. No file upload needed.

### Files to create/modify

| Action | File |
|--------|------|
| CREATE | `importers/my_source.py` |
| CREATE | `visualizers/my_source.py` |
| CREATE | `web/templates/viz/my_source.html` |
| MODIFY | `importers/__init__.py` — add to `_FETCHER_REGISTRY` |
| MODIFY | `visualizers/__init__.py` — add to `_REGISTRY` |
| MODIFY | `config/settings.py` — add API key setting |
| MODIFY | `.env.example` — add new variable |

### Fetcher

```python
# importers/my_source.py
from importers.base import BaseFetcher, FetchContext, QuotaExhaustedError
from typing import Dict, Any, List

class MyApiFetcher(BaseFetcher):
    SOURCE_KEY = "my_source"
    DISPLAY_NAME = "My API Source"
    SUPPORTED_CATEGORIES = ["trending"]

    def __init__(self):
        from config.settings import Settings
        self._api_key = Settings().my_api_key
        self._units_consumed = 0

    def validate_context(self, context: FetchContext) -> List[str]:
        if not self._api_key:
            return ["MY_API_KEY not configured"]
        return []

    def fetch(self, context: FetchContext) -> List[Dict[str, Any]]:
        # Call your API here
        # Increment self._units_consumed
        # Raise QuotaExhaustedError if quota exceeded
        results = []
        # ... your API call ...
        self._units_consumed += 1
        return results

    def build_document(self, raw_item: Dict[str, Any], item_index: int,
                       context: FetchContext) -> Dict[str, Any]:
        return {
            "_data_source":   self.SOURCE_KEY,
            "_data_category": context.data_category,
            "_geo":           context.geo or "WW",
            "_imported_at":   context.fetched_at,
            "_snapshot_at":   context.fetched_at,  # for time-series tracking
            "_fetch_source":  "my_api_v1",
            "title":          raw_item.get("name", ""),
            "trend":          int(raw_item.get("score", 0)),
            "data":           raw_item,
        }
```

The route `POST /import/fetch` already handles all fetchers generically — no route changes needed.

### Register

```python
# importers/__init__.py
from importers.my_source import MyApiFetcher

_FETCHER_REGISTRY: Dict[str, Type[BaseFetcher]] = {
    # existing entries...
    MyApiFetcher.SOURCE_KEY: MyApiFetcher,
}
```

### UI button on import page

The import page (`web/templates/import.html`) reads `list_fetchers()` automatically. Add a card in the "API Fetchers" section if you need custom parameters beyond `geo` and `max_results`.

---

## Pattern C — BaseSource (Scheduler, background polling)

Use when data should be collected automatically on a schedule (hourly, daily, weekly).

### Files to create/modify

| Action | File |
|--------|------|
| CREATE | `sources/my_platform.py` |
| MODIFY | `config/settings.py` — add API key |
| MODIFY | `agent/core.py._build_sources()` — register source |

### Source

```python
# sources/my_platform.py
from sources.base import BaseSource, Trend
from typing import List, Dict, Any

class MyPlatformSource(BaseSource):
    def fetch(self) -> List[Dict[str, Any]]:
        """Return list of raw API response items."""
        return []

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw item to common fields."""
        return {
            "topic":    raw_item.get("name", ""),
            "hashtags": raw_item.get("tags", []),
            "demand": {"volume": raw_item.get("volume", 0), "growth_rate": 0},
            "saturation": {"creator_count": 0, "age_days": 0},
            "velocity": {"daily_growth": 0, "acceleration": 0},
        }

    def to_trend(self, normalized: Dict[str, Any]) -> Trend:
        return Trend(
            platform="my_platform",
            topic=normalized["topic"],
            hashtags=normalized["hashtags"],
            content_type="web_searches",
            demand=normalized["demand"],
            saturation=normalized["saturation"],
            velocity=normalized["velocity"],
        )
```

---

## Adding a Visualizer

Every importer/fetcher needs a paired visualizer to display data in the dashboard.

```python
# visualizers/my_source.py
from visualizers.base import BaseVisualizer, VizContext
from typing import Dict, Any

class MySourceVisualizer(BaseVisualizer):
    SOURCE_KEY = "my_source"
    DISPLAY_NAME = "My Source"
    SUPPORTED_CATEGORIES = ["trending"]
    TEMPLATE = "viz/my_source.html"

    def fetch_data(self, store, context: VizContext) -> Dict[str, Any]:
        items = store.search_documents(
            data_source=context.source,
            data_category=context.data_category or None,
            geo=context.geo or None,
            size=context.size,
        )
        return {
            "items":           items,
            "total":           len(items),
            "source_label":    self.DISPLAY_NAME,
            "active_source":   context.source,
            "active_category": context.data_category,
            "active_geo":      context.geo,
        }
```

```python
# visualizers/__init__.py
from visualizers.my_source import MySourceVisualizer

_REGISTRY: Dict[str, Type[BaseVisualizer]] = {
    # existing entries...
    MySourceVisualizer.SOURCE_KEY: MySourceVisualizer,
}
```

### Template

Create `web/templates/viz/my_source.html`. Extend `base.html`:

```html
{% extends "base.html" %}
{% block title %}{{ source_label }} — TrendWatch{% endblock %}

{% block content %}
<!-- your visualisation here -->
{% for item in items %}
  <div>{{ item.title }} — {{ item.trend }}</div>
{% endfor %}
{% endblock %}
```

See `web/templates/viz/google_trends.html` (table layout) or `web/templates/viz/youtube_viral.html` (card grid) for complete examples.

---

## Adding Settings

For any new API key, add to `config/settings.py`:

```python
@property
def my_api_key(self) -> str:
    return os.getenv("MY_API_KEY", "")
```

And add to `.env.example`:

```env
# My Source API
MY_API_KEY=
```

Run `bash scripts/migrate_env.sh` on the production server to add the new variable without overwriting existing values.
