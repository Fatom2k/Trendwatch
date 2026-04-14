"""Routes d'authentification : login, callback OAuth, logout.

Flux :
    GET /login          → page de connexion
    GET /auth/login     → redirect vers Auth0 (démarrage OAuth)
    GET /auth/callback  → échange du code → vérification email → session → redirect /
    GET /logout         → vide la session → redirect Auth0 logout
    GET /unauthorized   → page 403 pour les emails non autorisés
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from web.auth import (
    clear_session,
    get_current_user,
    oauth,
    resolve_role,
    set_current_user,
)

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
logger = logging.getLogger(__name__)


@router.get("/login")
async def login_page(request: Request):
    """Affiche la page de connexion. Redirige vers / si déjà connecté."""
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/auth/login")
async def auth_login(request: Request):
    """Lance le flux Authorization Code vers Auth0."""
    callback_url = os.environ.get(
        "AUTH0_CALLBACK_URL",
        str(request.url_for("auth_callback")),
    )
    return await oauth.auth0.authorize_redirect(request, callback_url)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """Callback OAuth0 : vérifie l'email, assigne le rôle, ouvre la session."""
    token = await oauth.auth0.authorize_access_token(request)
    user_info = token.get("userinfo") or await oauth.auth0.userinfo(token=token)
    user_dict = dict(user_info)

    email = user_dict.get("email", "").lower().strip()
    role = resolve_role(email)

    if role is None:
        logger.warning("Accès refusé pour %s (non dans la whitelist).", email)
        return RedirectResponse(url="/unauthorized", status_code=302)

    set_current_user(request, user_dict, role)
    logger.info("Connexion réussie : %s (role=%s)", email, role)
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Vide la session et redirige vers le logout Auth0."""
    clear_session(request)
    domain = os.environ.get("AUTH0_DOMAIN", "")
    client_id = os.environ.get("AUTH0_CLIENT_ID", "")
    return_to = str(request.base_url)
    logout_url = (
        f"https://{domain}/v2/logout"
        f"?client_id={client_id}"
        f"&returnTo={return_to}"
    )
    return RedirectResponse(url=logout_url, status_code=302)


@router.get("/unauthorized")
async def unauthorized(request: Request):
    """Page 403 affichée quand l'email n'est pas dans la whitelist."""
    user = get_current_user(request)
    return templates.TemplateResponse(
        "unauthorized.html",
        {"request": request, "user": user},
        status_code=403,
    )
