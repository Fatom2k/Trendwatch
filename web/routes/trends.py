"""Routes de gestion des tendances : dashboard et ajout manuel.

Endpoints :
    GET  /           → dashboard (lecture seule pour viewer, formulaire pour admin)
    POST /trends/add → créer une tendance → index ES → redirect /  [admin only]
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import Settings
from sources.base import Trend
from web.auth import admin_required, get_current_user, login_required

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
logger = logging.getLogger(__name__)

ALL_PLATFORMS = [
    "tiktok", "instagram", "twitter",
    "google_trends", "exploding_topics", "youtube", "pinterest",
]
ALL_FORMATS = ["reel", "carousel", "thread", "story", "short", "blog", "product"]


def _get_store():
    """Retourne un TrendStore connecté ou None si ES est indisponible."""
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
    """Dashboard principal. Accessible à tous les utilisateurs authentifiés."""
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
        "dashboard.html",
        context={
            "request":   request,
            "user":      user,
            "is_admin":  is_admin,
            "recent":    recent,
            "platforms": ALL_PLATFORMS,
            "formats":   ALL_FORMATS,
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
    """Crée une tendance depuis le formulaire et l'indexe dans ES.

    Réservé aux utilisateurs avec le rôle ``admin``.
    """
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
            "message": "⚠️ Elasticsearch non disponible. Tendance non persistée.",
        }

    return RedirectResponse(url="/", status_code=303)
