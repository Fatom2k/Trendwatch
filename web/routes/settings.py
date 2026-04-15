"""Routes for application settings and administration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from config.settings import Settings
from storage.elasticsearch import TrendStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="web/templates")


# Auth helpers
def admin_required(request: Request):
    """Check if user is admin."""
    user = request.session.get("user")
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=302)
    return None


def get_current_user(request: Request):
    """Get current user from session."""
    return request.session.get("user", {})


@router.get("")
async def settings_page(request: Request):
    """Display application settings."""
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    settings = Settings()

    # Get Elasticsearch stats
    try:
        store = TrendStore(
            host=settings.elasticsearch_host,
            index_name=settings.elasticsearch_index,
        )
        trend_count = store.count()
        es_available = store.ping()
    except Exception as exc:
        logger.warning("Failed to get ES stats: %s", exc)
        trend_count = 0
        es_available = False

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "user": user,
            "trend_count": trend_count,
            "es_available": es_available,
            "elasticsearch_host": settings.elasticsearch_host,
            "elasticsearch_index": settings.elasticsearch_index,
        },
    )


@router.post("/clear-data")
async def clear_elasticsearch_data(request: Request):
    """Clear all trends from Elasticsearch."""
    # Auth check
    redirect = admin_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    settings = Settings()

    try:
        store = TrendStore(
            host=settings.elasticsearch_host,
            index_name=settings.elasticsearch_index,
        )

        # Delete the index (this removes all data)
        if store._es.indices.exists(index=store.index_name):
            store._es.indices.delete(index=store.index_name)
            logger.info("Elasticsearch index '%s' deleted by %s", store.index_name, user.get("email", "unknown"))

            # Recreate empty index
            store.ensure_index()

            return JSONResponse(
                {
                    "success": True,
                    "message": f"✅ All data cleared from '{store.index_name}'",
                    "timestamp": str(__import__("datetime").datetime.now()),
                },
                status_code=200,
            )
        else:
            return JSONResponse(
                {
                    "error": "Index not found",
                    "message": f"Index '{store.index_name}' does not exist",
                },
                status_code=404,
            )

    except Exception as exc:
        logger.error("Failed to clear Elasticsearch: %s", exc)
        return JSONResponse(
            {
                "error": "Failed to clear data",
                "details": str(exc),
            },
            status_code=500,
        )
