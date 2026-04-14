"""Routes de gestion des tendances : dashboard et ajout manuel."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from config.settings import Settings
from sources.base import Trend
from web.auth import admin_required, get_current_user, login_required
from web.templates_config import templates

router = APIRouter()
logger = logging.getLogger(__name__)

ALL_PLATFORMS = [
    "tiktok", "instagram", "twitter",
    "google_trends", "exploding_topics", "youtube", "pinterest",
]
ALL_FORMATS = ["reel", "carousel", "thread", "story", "short", "blog", "product"]


def _get_store():
    try:
        from storage.elasticsearch import TrendStore
        s = Settings()
        store = TrendStore(host=s.elasticsearch_host, index_name=s.elasticsearch_index)
        return store if store.ping() else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ES indisponible : %s", exc)
        return None


@router.get("/")
async def dashboard(request: Request):
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    is_admin = user.get("role") == "admin"

    recent: list = []
    store = _get_store()
    if store:
        try:
            recent = store.search(size=20)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erreur fetch tendances : %s", exc)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request":   request,
            "user":      user,
            "is_admin":  is_admin,
            "recent":    recent,
            "flash":     request.session.pop("flash", None),
        },
    )


@router.post("/trends/add")
async def add_trend(
    request: Request,
    topic: str = Form(...),
    sources: List[str] = Form(default=[]),
    hashtags_raw: str = Form(default=""),
    suggested_formats: List[str] = Form(default=[]),
    pipeline_target: str = Form(default="digital"),
    notes: str = Form(default=""),
    score: int = Form(default=0),
):
    redirect = admin_required(request)
    if redirect:
        return redirect

    hashtags = [
        h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
        for h in hashtags_raw.split(",")
        if h.strip()
    ]

    platform = sources[0] if sources else "manual"

    trend = Trend(
        platform=platform,
        topic=topic.strip(),
        hashtags=hashtags,
        score=max(0, min(100, score)),
        suggested_formats=suggested_formats,
        pipeline_target=pipeline_target,
        summary=notes.strip() or None,
        raw={"sources": sources, "manually_added": True},
    )

    store = _get_store()
    if store:
        try:
            store.index_trend(trend)
            request.session["flash"] = {
                "type": "success",
                "message": f"✅ Tendance « {topic} » ajoutée.",
            }
        except Exception as exc:
            logger.error("Erreur indexation : %s", exc)
            request.session["flash"] = {
                "type": "error",
                "message": f"❌ Erreur ES : {exc}",
            }
    else:
        request.session["flash"] = {
            "type": "warning",
            "message": "⚠️ Elasticsearch non disponible.",
        }

    return RedirectResponse(url="/", status_code=303)


@router.get("/trends-explorer")
async def trends_explorer(request: Request):
    """Explore all collected trends from Elasticsearch."""
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    trends = []
    es_status = "unknown"

    store = _get_store()
    if store:
        try:
            es_status = "connected"
            trends = store.search(size=500)
            # Sort by score descending
            trends.sort(key=lambda t: t.get("score", 0), reverse=True)
        except Exception as exc:
            logger.warning("Error fetching trends: %s", exc)
            es_status = f"error: {exc}"
    else:
        es_status = "disconnected"

    return templates.TemplateResponse(
        request,
        "trends_explorer.html",
        {
            "request": request,
            "user": user,
            "trends": trends,
            "total_trends": len(trends),
            "es_status": es_status,
        },
    )


@router.get("/import")
async def import_page(request: Request):
    """Dedicated page for manually importing trends."""
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
            "platforms": ALL_PLATFORMS,
            "formats": ALL_FORMATS,
        },
    )


@router.get("/statistics")
async def statistics(request: Request):
    """Display trend statistics and metrics."""
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    stats = {
        "total_trends": 0,
        "by_platform": {},
        "avg_score": 0,
        "top_trends": [],
    }

    store = _get_store()
    if store:
        try:
            trends = store.search(size=500)
            stats["total_trends"] = len(trends)

            # Count by platform
            for t in trends:
                platform = t.get("platform", "unknown")
                stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

            # Average score
            if trends:
                avg = sum(t.get("score", 0) for t in trends) / len(trends)
                stats["avg_score"] = round(avg, 1)

            # Top 5 trends
            stats["top_trends"] = sorted(trends, key=lambda t: t.get("score", 0), reverse=True)[:5]
        except Exception as exc:
            logger.warning("Error fetching statistics: %s", exc)

    return templates.TemplateResponse(
        request,
        "statistics.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
        },
    )


@router.get("/settings")
async def settings(request: Request):
    """User settings page."""
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "user": user,
        },
    )
