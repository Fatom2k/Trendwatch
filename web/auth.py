"""Auth0 / Google OAuth helpers for the TrendWatch web interface.

Uses ``authlib`` to implement the Authorization Code flow against Auth0.
The authenticated user is stored in a signed session cookie managed by
Starlette's :class:`~starlette.middleware.sessions.SessionMiddleware`.

Required environment variables::

    AUTH0_DOMAIN          your-tenant.auth0.com
    AUTH0_CLIENT_ID       ...
    AUTH0_CLIENT_SECRET   ...
    AUTH0_CALLBACK_URL    https://yourdomain.com/auth/callback
"""

from __future__ import annotations

import os
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from fastapi.responses import RedirectResponse

# ---------------------------------------------------------------------------
# Auth0 OAuth client
# ---------------------------------------------------------------------------

oauth = OAuth()
oauth.register(
    name="auth0",
    client_id=os.environ.get("AUTH0_CLIENT_ID", ""),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET", ""),
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=(
        f"https://{os.environ.get('AUTH0_DOMAIN', 'example.auth0.com')}"
        "/.well-known/openid-configuration"
    ),
)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

SESSION_KEY = "user"


def get_current_user(request: Request) -> Optional[dict]:
    """Return the logged-in user dict from the session, or ``None``.

    Args:
        request: Current HTTP request.

    Returns:
        Dict with at least ``name``, ``email``, ``picture`` keys,
        or ``None`` if the user is not authenticated.
    """
    return request.session.get(SESSION_KEY)


def set_current_user(request: Request, user: dict) -> None:
    """Persist *user* in the signed session cookie.

    Args:
        request: Current HTTP request.
        user:    User info dict returned by Auth0 userinfo endpoint.
    """
    request.session[SESSION_KEY] = {
        "sub": user.get("sub", ""),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "picture": user.get("picture", ""),
    }


def clear_session(request: Request) -> None:
    """Remove user data from the session cookie."""
    request.session.pop(SESSION_KEY, None)


def login_required(request: Request) -> RedirectResponse | None:
    """Return a redirect to ``/login`` if the user is not authenticated.

    Intended for use at the top of route handlers::

        redirect = login_required(request)
        if redirect:
            return redirect

    Args:
        request: Current HTTP request.

    Returns:
        :class:`~fastapi.responses.RedirectResponse` to ``/login``, or
        ``None`` if the user is authenticated.
    """
    if not get_current_user(request):
        return RedirectResponse(url="/login", status_code=302)
    return None
