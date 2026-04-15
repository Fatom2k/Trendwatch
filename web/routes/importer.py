"""Routes for importing trend data from uploaded files (CSV, etc.).

All routes require admin access — regular viewers have no import privileges.
The import logic is fully delegated to the importers/ package; this route
handles only: auth, file I/O, context assembly, and ES persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.requests import Request

from config.settings import Settings
from importers import (
    get_importer, list_sources, ImportContext,
    get_fetcher, list_fetchers, FetchContext, QuotaExhaustedError,
)
from storage.elasticsearch import TrendStore
from web.auth import admin_required, get_current_user
from web.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/fetch")
async def api_fetch(
    request: Request,
    source: str = Form("youtube_viral"),
    data_category: str = Form("trending"),
    geo: str = Form("FR"),
    max_results: int = Form(50),
):
    """Trigger a live API fetch and index results into Elasticsearch (admin only)."""
    redirect = admin_required(request)
    if redirect:
        return JSONResponse(
            {"error": "Unauthorized", "details": "Admin access required"},
            status_code=403,
        )

    fetcher_class = get_fetcher(source)
    if fetcher_class is None:
        return JSONResponse(
            {
                "error": f"Unsupported source: '{source}'",
                "details": f"Available: {[f['key'] for f in list_fetchers()]}",
            },
            status_code=400,
        )

    context = FetchContext(
        source=source,
        data_category=data_category,
        geo=geo,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        extra={"max_results": min(max_results, 50)},
    )

    fetcher = fetcher_class()

    errors = fetcher.validate_context(context)
    if errors:
        return JSONResponse({"error": errors[0]}, status_code=400)

    try:
        raw_items = fetcher.fetch(context)
    except QuotaExhaustedError as exc:
        logger.warning("YouTube quota exhausted: %s", exc)
        return JSONResponse(
            {"error": "Quota API épuisé", "details": str(exc)},
            status_code=429,
        )
    except Exception as exc:
        logger.error("API fetch failed (%s): %s", source, exc)
        return JSONResponse(
            {"error": "Fetch failed", "details": str(exc)},
            status_code=500,
        )

    if not raw_items:
        return JSONResponse(
            {"error": "Aucun résultat retourné par l'API"},
            status_code=400,
        )

    settings = Settings()
    store = TrendStore(
        host=settings.elasticsearch_host,
        index_name=settings.elasticsearch_index,
    )
    store.ensure_index()

    imported_count = 0
    for idx, item in enumerate(raw_items, start=1):
        try:
            doc = fetcher.build_document(item, idx, context)
            store.index_document(doc)
            imported_count += 1
        except Exception as exc:
            logger.warning("Failed to index item %d from '%s': %s", idx, source, exc)

    quota_used = getattr(fetcher, "_units_consumed", 0)
    logger.info(
        "API fetch complete: %d documents indexed (source=%s, geo=%s, quota_used=%d)",
        imported_count, source, geo, quota_used,
    )

    return JSONResponse(
        {
            "success":       True,
            "message":       f"✅ {imported_count} vidéos importées ({geo or 'Mondial'})",
            "count":         imported_count,
            "source":        source,
            "data_category": data_category,
            "geo":           geo or "WW",
            "quota_used":    quota_used,
        },
        status_code=200,
    )


@router.get("")
async def import_page(request: Request):
    """Display the import hub (requires admin)."""
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "user":    user,
            "sources": list_sources(),
        },
    )


@router.get("/csv")
async def csv_upload_page(request: Request):
    """Display the CSV upload form (requires admin)."""
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "request": request,
            "user":    user,
            "sources": list_sources(),
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
    """Handle CSV file upload and import into Elasticsearch (requires admin)."""
    # Auth guard — admin only
    redirect = admin_required(request)
    if redirect:
        return JSONResponse(
            {"error": "Unauthorized", "details": "Admin access required"},
            status_code=403,
        )

    # File extension check
    if not csv_file.filename.endswith(".csv"):
        return JSONResponse(
            {"error": "Only CSV files are supported"},
            status_code=400,
        )

    # Required field validation
    if not source or not data_category:
        return JSONResponse(
            {"error": "Missing required fields", "details": "Source and Data Category are required"},
            status_code=400,
        )

    # search_type required for "terms" category
    if data_category == "terms" and not search_type:
        return JSONResponse(
            {"error": "Missing required fields", "details": "Search Type is required for Search Terms"},
            status_code=400,
        )

    # Normalise search_type for "trending" category
    if data_category == "trending":
        search_type = "trending"

    # Resolve importer
    importer_class = get_importer(source)
    if importer_class is None:
        return JSONResponse(
            {"error": f"Unsupported source: '{source}'", "details": f"Available: {[s['key'] for s in list_sources()]}"},
            status_code=400,
        )

    try:
        # Save uploaded file to donnees/uploads/
        content = await csv_file.read()
        upload_dir = Path("donnees/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        csv_path = upload_dir / csv_file.filename
        csv_path.write_bytes(content)

        # Build import context (immutable — passed to every build_document call)
        context = ImportContext(
            filename=csv_file.filename,
            source=source,
            data_category=data_category,
            search_type=search_type,
            time_range=time_range,
            geo=geo,
            imported_at=datetime.now(timezone.utc).isoformat(),
        )

        # Instantiate importer and validate
        importer = importer_class()
        errors = importer.validate(csv_path, context)
        if errors:
            return JSONResponse({"error": errors[0]}, status_code=400)

        # Parse rows
        raw_rows = list(importer.parse_rows(csv_path))
        if not raw_rows:
            return JSONResponse(
                {
                    "error": "No valid rows found in CSV",
                    "details": "The file appears to be empty or contains only blank rows.",
                },
                status_code=400,
            )

        logger.info(
            "Importing %d rows from '%s' (source=%s, category=%s, geo=%s)",
            len(raw_rows),
            csv_file.filename,
            source,
            data_category,
            geo,
        )

        # Index to Elasticsearch
        settings = Settings()
        store = TrendStore(
            host=settings.elasticsearch_host,
            index_name=settings.elasticsearch_index,
        )
        store.ensure_index()

        imported_count = 0
        for idx, row in enumerate(raw_rows, start=1):
            try:
                doc = importer.build_document(row, idx, context)
                store.index_document(doc)
                imported_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to index row %d from '%s': %s",
                    idx,
                    csv_file.filename,
                    exc,
                )

        return JSONResponse(
            {
                "success":       True,
                "message":       f"✅ {imported_count} lignes importées depuis {csv_file.filename}",
                "count":         imported_count,
                "filename":      csv_file.filename,
                "source":        source,
                "data_category": data_category,
                "search_type":   search_type,
                "time_range":    time_range,
                "geo":           geo,
            },
            status_code=200,
        )

    except Exception as exc:
        logger.error("CSV import failed: %s", exc)
        return JSONResponse(
            {"error": "Failed to process CSV", "details": str(exc)},
            status_code=500,
        )
