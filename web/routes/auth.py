"""Authentication routes: login, OAuth callback, logout.

Flow:
    GET /login            → renders login page with "Sign in with Google" button
    GET /auth/login       → redirects to Auth0 (starts OAuth flow)
    GET /auth/callback    → exchanges code → stores user in session → redirect /
    GET /logout           → clears session → redirect /
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.auth import clear_session, get_current_user, oauth, set_current_user

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page.

    Redirects to ``/`` if the user is already authenticated.
    """
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/auth/login")
async def auth_login(request: Request):
    """Initiate the Auth0 / Google OAuth Authorization Code flow."""
    callback_url = os.environ.get(
        "AUTH0_CALLBACK_URL",
        str(request.url_for("auth_callback")),
    )
    return await oauth.auth0.authorize_redirect(request, callback_url)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle the OAuth callback from Auth0.

    Exchanges the authorization code for a token, fetches user info,
    stores it in the session, and redirects to the dashboard.
    """
    token = await oauth.auth0.authorize_access_token(request)
    user_info = token.get("userinfo") or await oauth.auth0.userinfo(token=token)
    set_current_user(request, dict(user_info))
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Clear the session and redirect to the Auth0 logout endpoint."""
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
