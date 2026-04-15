"""Routes de gestion des tendances : dashboard, visualisations et ajout manuel."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from config.settings import Settings
from sources.base import Trend
from visualizers import get_visualizer, list_visualizers, VizContext
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


def _group_by_source_category(trends: List[dict]) -> dict:
    """Group trends by source + category and extract top 10 for each group."""
    grouped: dict = {}

    for trend in trends:
        source = trend.get("_data_source", "unknown")
        if source == "youtube_viral":
            continue
        category = trend.get("_data_category", "unknown")
        key = f"{source}_{category}"

        if key not in grouped:
            grouped[key] = {
                "source": source,
                "category": category,
                "trends": [],
            }

        grouped[key]["trends"].append(trend)

    # Sort each group by trend value and keep top 10
    for key in grouped:
        grouped[key]["trends"].sort(
            key=lambda t: t.get("trend", 0) if isinstance(t.get("trend"), (int, float)) else 0,
            reverse=True
        )
        grouped[key]["trends"] = grouped[key]["trends"][:10]

    return grouped


def _prepare_youtube_by_geo(trends: List[dict]) -> dict:
    """Group YouTube trends by country (geo) for donut visualization.

    Non-WW groups have entries that appear in the WW group removed so that
    country-specific donuts show truly local content only.
    """
    youtube_trends = [t for t in trends if t.get("_data_source") == "youtube_viral"]

    if not youtube_trends:
        return {}

    by_geo: dict = {}
    for trend in youtube_trends:
        geo = trend.get("_geo") or "WW"
        if geo not in by_geo:
            by_geo[geo] = []
        by_geo[geo].append(trend)

    # Build index: video_id → set of country geos where it appears (non-WW)
    country_appearance: dict = {}
    for geo, items in by_geo.items():
        if geo in ("WW", ""):
            continue
        for item in items:
            vid = (item.get("data") or {}).get("video_id")
            if vid:
                country_appearance.setdefault(vid, set()).add(geo)

    # Build the set of video_ids present in the worldwide group
    ww_ids: set = set()
    for geo_key in ("WW", ""):
        for item in by_geo.get(geo_key, []):
            vid = (item.get("data") or {}).get("video_id")
            if vid:
                ww_ids.add(vid)

    def _view_count(t: dict) -> int:
        return t.get("data", {}).get("view_count", 0) if isinstance(t.get("data"), dict) else 0

    for geo in list(by_geo.keys()):
        group = by_geo[geo]
        # For country-specific groups, exclude videos already in WW
        if geo not in ("WW", ""):
            group = [
                t for t in group
                if (t.get("data") or {}).get("video_id") not in ww_ids
            ]
        group.sort(key=_view_count, reverse=True)
        by_geo[geo] = group[:10]
        # Drop the group entirely if it has no unique content
        if not by_geo[geo]:
            del by_geo[geo]

    # Annotate WW items with the country geos where they also appear
    for geo_key in ("WW", ""):
        for item in by_geo.get(geo_key, []):
            vid = (item.get("data") or {}).get("video_id")
            item["_also_in"] = sorted(country_appearance.get(vid, set()))

    # Return ordered dict: WW/FR first, then remaining geos alphabetically
    priority = ["", "WW", "FR"]
    ordered: dict = {}
    for key in priority:
        if key in by_geo:
            ordered[key] = by_geo[key]
    for key in sorted(k for k in by_geo if k not in priority):
        ordered[key] = by_geo[key]
    return ordered


@router.get("/")
async def dashboard(request: Request):
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)
    is_admin = user.get("role") == "admin"

    grouped_data: dict = {}
    youtube_by_geo: dict = {}
    store = _get_store()
    if store:
        try:
            # Fetch all trends (or reasonable limit like 1000)
            all_trends = store.search(size=1000)
            grouped_data = _group_by_source_category(all_trends)
            youtube_by_geo = _prepare_youtube_by_geo(all_trends)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erreur fetch tendances : %s", exc)

    donut_colors = [
        "#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4",
        "#3b82f6", "#8b5cf6", "#ec4899", "#f43f5e", "#14b8a6"
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request":         request,
            "user":            user,
            "is_admin":        is_admin,
            "grouped_data":    grouped_data,
            "youtube_by_geo":  youtube_by_geo,
            "donut_colors":    donut_colors,
            "flash":           request.session.pop("flash", None),
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
            trends = store.search(size=1000)
            # Sort by import date descending (newest first)
            trends.sort(key=lambda t: t.get("_imported_at", ""), reverse=True)
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


@router.get("/data")
async def data_view(
    request: Request,
    source: str = Query("google_trends"),
    category: str = Query("terms"),
    geo: str = Query(""),
    time_range: str = Query(""),
    search_type: str = Query(""),
    size: int = Query(50),
):
    """Source-specific data visualization (requires login)."""
    redirect = login_required(request)
    if redirect:
        return redirect

    user = get_current_user(request)

    viz_class = get_visualizer(source)
    if viz_class is None:
        # Unknown source — redirect to dashboard with a flash message
        request.session["flash"] = {
            "type": "error",
            "message": f"Source inconnue : {source}",
        }
        return RedirectResponse(url="/", status_code=302)

    viz = viz_class()
    ctx = VizContext(
        source=source,
        data_category=category,
        geo=geo,
        time_range=time_range,
        search_type=search_type,
        size=min(size, 500),
    )

    store = _get_store()
    viz_data = viz.fetch_data(store, ctx) if store else {
        "items": [],
        "total": 0,
        "source_label": viz.DISPLAY_NAME,
        "categories": viz.SUPPORTED_CATEGORIES,
        "active_source": source,
        "active_category": category,
        "active_geo": geo,
        "active_time": time_range,
        "active_search_type": search_type,
    }

    return templates.TemplateResponse(
        request,
        viz.get_template(category),
        {
            "request":            request,
            "user":               user,
            "available_sources":  list_visualizers(),
            **viz_data,
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
