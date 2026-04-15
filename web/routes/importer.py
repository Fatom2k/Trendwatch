"""Routes for importing trends data (CSV uploads, etc.)"""

from __future__ import annotations

import logging

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
                # Add metadata to each document
                doc = {
                    **item,  # Original CSV columns
                    "_csv_source": csv_file.filename,
                    "_data_source": source,
                    "_data_category": data_category,
                    "_search_type": search_type,
                    "_time_range": time_range,
                    "_geo": geo,
                    "_csv_row_index": idx,
                    "_imported_at": __import__("datetime").datetime.utcnow().isoformat(),
                }
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
