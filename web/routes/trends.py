"""Trend management routes: dashboard listing and manual trend creation.

Endpoints:
    GET  /           → dashboard with recent trends and the add-trend form
    POST /trends/add → create a Trend from form data → index in ES → redirect /
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import Settings
from sources.base import Trend
from web.auth import get_current_user, login_required

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
logger = logging.getLogger(__name__)

ALL_PLATFORMS = [
    "tiktok", "instagram", "twitter",
    "google_trends", "exploding_topics", "youtube", "pinterest",
]
ALL_FORMATS = ["reel", "carousel", "thread", "story", "short", "blog", "product"]


def _get_store():
    """Return a connected TrendStore or None if ES is unavailable."""
    try:
        from storage.elasticsearch import TrendStore
        s = Settings()
        store = TrendStore(host=s.elasticsearch_host, index_name=s.elasticsearch_index)
        return store if store.ping() else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ES unavailable: %s", exc)
        return None


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the dashboard with the manual entry form and recent trends.

    Redirects to ``/login`` if the user is not authenticated.
    """
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    recent: list = []
    store = _get_store()
    if store:
        try:
            recent = store.search(size=20)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch recent trends: %s", exc)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "recent": recent,
            "platforms": ALL_PLATFORMS,
            "formats": ALL_FORMATS,
            "flash": request.session.pop("flash", None),
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
    """Create a :class:`~sources.base.Trend` from form input and index it.

    Args:
        request:           HTTP request (session access).
        topic:             Free-text trend label.
        sources:           Selected platform slugs.
        hashtags_raw:      Comma-separated hashtag string.
        suggested_formats: Checked content format slugs.
        pipeline_target:   ``"digital"`` or ``"physical"``.
        notes:             Free-text note stored as ``summary``.
        score:             Optional manual score (0–100).

    Returns:
        Redirect to ``/`` with a flash message.
    """
    redirect = login_required(request)
    if redirect:
        return redirect

    # Parse hashtags
    hashtags = [
        h.strip() if h.strip().startswith("#") else f"#{h.strip()}"
        for h in hashtags_raw.split(",")
        if h.strip()
    ]

    # Use first selected source as platform, or "manual" as fallback
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
            request.session["flash"] = {"type": "success", "message": f"✅ Tendance \u00ab {topic} \u00bb ajoutée."}
        except Exception as exc:
            logger.error("Failed to index trend: %s", exc)
            request.session["flash"] = {"type": "error", "message": f"❌ Erreur ES : {exc}"}
    else:
        request.session["flash"] = {"type": "warning", "message": "⚠️ Elasticsearch non disponible. Tendance non persistée."}

    return RedirectResponse(url="/", status_code=303)
