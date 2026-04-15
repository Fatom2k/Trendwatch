"""Admin routes and settings."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from config.settings import Settings
from storage.elasticsearch import TrendStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="web/templates")


def get_current_user(request: Request):
    """Get current user from session."""
    return request.session.get("user", {})


def is_admin(request: Request) -> bool:
    """Check if user is admin."""
    user = get_current_user(request)
    return user.get("role") == "admin" or user.get("is_admin", False)


@router.get("")
async def admin_page(request: Request):
    """Display admin dashboard."""
    if not is_admin(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)

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
        "admin.html",
        {
            "request": request,
            "user": user,
            "trend_count": trend_count,
            "es_available": es_available,
            "elasticsearch_host": settings.elasticsearch_host,
            "elasticsearch_index": settings.elasticsearch_index,
        },
    )


@router.post("/clear-elasticsearch")
async def clear_elasticsearch(request: Request):
    """Clear all data from Elasticsearch."""
    if not is_admin(request):
        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=403,
        )

    user = get_current_user(request)
    settings = Settings()

    try:
        store = TrendStore(
            host=settings.elasticsearch_host,
            index_name=settings.elasticsearch_index,
        )

        if store._es.indices.exists(index=store.index_name):
            store._es.indices.delete(index=store.index_name)
            store.ensure_index()

            logger.info(
                "Elasticsearch index '%s' cleared by %s",
                store.index_name,
                user.get("email", "unknown"),
            )

            return JSONResponse(
                {
                    "success": True,
                    "message": f"✅ Elasticsearch cleared ({store.index_name})",
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
