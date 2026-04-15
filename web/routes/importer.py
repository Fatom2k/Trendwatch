"""Routes for importing trends data (CSV uploads, etc.)"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from sources.google_trends_csv_importer import GoogleTrendsCSVImporter
from storage.elasticsearch import TrendStore
from config.settings import Settings
from web.auth import admin_required, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["import"])

# Templates
templates = Jinja2Templates(directory="web/templates")


def _normalize_column_name(col: str) -> str:
    """Normalize column name for comparison."""
    return col.lower().strip().replace(" ", "").replace("_", "").replace("-", "")


def _similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a, b).ratio()


def _find_column(
    csv_columns: list,
    search_terms: list,
    threshold: float = 0.6,
) -> Optional[str]:
    """Find a column in CSV that matches any of the search terms."""
    normalized_searches = [_normalize_column_name(term) for term in search_terms]

    for csv_col in csv_columns:
        normalized_csv = _normalize_column_name(csv_col)

        # Check for exact match
        if normalized_csv in normalized_searches:
            return csv_col

        # Check for fuzzy match with similarity
        for search_term, norm_search in zip(search_terms, normalized_searches):
            similarity = _similarity(normalized_csv, norm_search)
            if similarity >= threshold:
                return csv_col

    return None


def _process_google_trends_terms(item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a Google Trends CSV row for 'terms' category.

    Extracts:
    - 'Query' field → 'title'
    - 'Increase percent' field → 'trend'
    - All CSV columns → nested 'data' object
    """
    csv_columns = list(item.keys())

    # Find 'query' column
    query_col = _find_column(csv_columns, ["Query", "Title", "Keyword", "Search", "Term"])
    query_val = item.get(query_col, "") if query_col else ""

    # Find 'increase percent' column
    increase_col = _find_column(csv_columns, ["Increase percent", "Growth", "Change", "Increase"])
    trend_val = 0
    if increase_col:
        try:
            # Remove % sign and convert to int
            increase_str = item.get(increase_col, "0").replace("%", "").strip()
            trend_val = int(float(increase_str)) if increase_str else 0
        except (ValueError, AttributeError):
            trend_val = 0

    # Return processed document
    return {
        "title": query_val,
        "trend": trend_val,
        "data": item,  # Nested: all CSV data
    }


@router.get("")
async def import_page(request: Request):
    """Display CSV import form (requires admin)."""
    # Check admin access
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/csv")
async def csv_upload_page(request: Request):
    """Display CSV upload form (requires admin)."""
    # Check admin access
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.post("/csv")
async def upload_csv(
    request: Request,
    csv_file: UploadFile = File(...),
    source: str = Form("google_trends"),
    data_category: str = Form("terms"),
    search_type: str = Form(""),
    time_range: str = Form("hours"),
    geo: str = Form("FR"),
):
    """Handle CSV file upload and import (requires admin)."""
    # Check admin access
    redirect = admin_required(request)
    if redirect:
        return JSONResponse(
            {"error": "Unauthorized", "details": "Admin access required"},
            status_code=403,
        )

    if not csv_file.filename.endswith(".csv"):
        return JSONResponse(
            {"error": "Only CSV files are supported"},
            status_code=400,
        )

    # Validate required fields
    if not source or not data_category:
        return JSONResponse(
            {"error": "Missing required fields", "details": "Source and Data Category are required"},
            status_code=400,
        )

    # For "terms" category, search_type is required
    if data_category == "terms" and not search_type:
        return JSONResponse(
            {"error": "Missing required fields", "details": "Search Type is required for Search Terms"},
            status_code=400,
        )

    # Set search_type to "trending" if category is "trending"
    if data_category == "trending":
        search_type = "trending"

    try:
        # Read file content
        content = await csv_file.read()

        # Save to donnees/uploads/ directory
        from pathlib import Path
        upload_dir = Path("donnees/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        csv_path = upload_dir / csv_file.filename
        with open(csv_path, "wb") as f:
            f.write(content)

        logger.info(
            "Processing CSV upload: %s (source=%s, category=%s, search_type=%s, time_range=%s, geo=%s)",
            csv_file.filename,
            source,
            data_category,
            search_type,
            time_range,
            geo,
        )

        # Import using GoogleTrendsCSVImporter
        # Only need geo, other params use defaults
        settings = Settings()
        importer = GoogleTrendsCSVImporter(
            csv_path=str(csv_path),
            geo=geo,
            settings=settings,
        )

        # Fetch raw CSV rows (preserving original column names)
        raw_items = importer.fetch()
        if not raw_items:
            return JSONResponse(
                {
                    "error": "No valid rows found in CSV",
                    "details": "CSV appears to be empty or contains only blank rows.",
                },
                status_code=400,
            )

        # Store raw CSV data directly with original column names
        store = TrendStore(
            host=settings.elasticsearch_host,
            index_name=settings.elasticsearch_index,
        )
        store.ensure_index()

        # Index each CSV row as a document with original column names
        imported_count = 0
        for idx, item in enumerate(raw_items, start=1):
            try:
                # Build base document
                doc = {
                    "_csv_source": csv_file.filename,
                    "_data_source": source,
                    "_data_category": data_category,
                    "_search_type": search_type,
                    "_time_range": time_range,
                    "_geo": geo,
                    "_csv_row_index": idx,
                    "_imported_at": __import__("datetime").datetime.utcnow().isoformat(),
                }

                # Special processing for Google Trends 'terms' category
                if source == "google_trends" and data_category == "terms":
                    processed = _process_google_trends_terms(item)
                    doc.update(processed)
                else:
                    # Default: keep all CSV columns at root level
                    doc.update(item)

                store._es.index(index=store.index_name, document=doc)
                imported_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to index row %d from CSV '%s': %s",
                    idx,
                    csv_file.filename,
                    exc,
                )

        return JSONResponse(
            {
                "success": True,
                "message": f"✅ Successfully imported {imported_count} rows from CSV",
                "count": imported_count,
                "filename": csv_file.filename,
                "source": source,
                "data_category": data_category,
                "search_type": search_type,
                "time_range": time_range,
                "geo": geo,
            },
            status_code=200,
        )

    except Exception as exc:
        logger.error("CSV import failed: %s", exc)
        return JSONResponse(
            {
                "error": "Failed to process CSV",
                "details": str(exc),
            },
            status_code=500,
        )
