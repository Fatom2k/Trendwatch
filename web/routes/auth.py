"""Routes d'authentification : login, callback OAuth, logout."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from web.auth import (
    clear_session,
    get_current_user,
    oauth,
    resolve_role,
    set_current_user,
)
from web.templates_config import templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/login")
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request})


@router.get("/auth/login")
async def auth_login(request: Request):
    callback_url = os.environ.get(
        "AUTH0_CALLBACK_URL",
        str(request.url_for("auth_callback")),
    )
    return await oauth.auth0.authorize_redirect(request, callback_url)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    token = await oauth.auth0.authorize_access_token(request)
    user_info = token.get("userinfo") or await oauth.auth0.userinfo(token=token)
    user_dict = dict(user_info)

    email = user_dict.get("email", "").lower().strip()
    role = resolve_role(email)

    if role is None:
        logger.warning("Accès refusé pour %s.", email)
        return RedirectResponse(url="/unauthorized", status_code=302)

    set_current_user(request, user_dict, role)
    logger.info("Connexion : %s (role=%s)", email, role)
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    clear_session(request)
    domain = os.environ.get("AUTH0_DOMAIN", "")
    client_id = os.environ.get("AUTH0_CLIENT_ID", "")
    # Use explicit logout URL from env, or construct from request
    return_to = os.environ.get("AUTH0_LOGOUT_URL", str(request.base_url).rstrip("/"))

    # Build logout URL with properly encoded parameters
    logout_params = urlencode({"client_id": client_id, "returnTo": return_to})
    logout_url = f"https://{domain}/v2/logout?{logout_params}"

    return RedirectResponse(url=logout_url, status_code=302)


@router.get("/unauthorized")
async def unauthorized(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        request,
        "unauthorized.html",
        {"request": request, "user": user},
        status_code=403,
    )
