"""Auth0 / Google OAuth helpers avec gestion des rôles et whitelist email.

Rôles disponibles :
- ``admin``  — peut voir le dashboard ET ajouter des tendances.
- ``viewer`` — peut uniquement consulter le dashboard (lecture seule).

Contrôle d'accès via variables d'environnement ::

    ADMIN_EMAILS   = fatom@example.com,autre@example.com
    ALLOWED_EMAILS = viewer1@example.com,viewer2@example.com

Logique de résolution du rôle :
- Email dans ADMIN_EMAILS                        → role = "admin"
- Email dans ALLOWED_EMAILS (ou liste vide)       → role = "viewer"
- Email absent des deux listes (si l'une est définie) → non autorisé (403)
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
# Email whitelist & rôles (chargés une fois au démarrage)
# ---------------------------------------------------------------------------

def _load_email_set(env_key: str) -> set[str]:
    """Parse une liste d’emails depuis une variable d’environnement."""
    raw = os.environ.get(env_key, "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


ADMIN_EMAILS: set[str] = _load_email_set("ADMIN_EMAILS")
ALLOWED_EMAILS: set[str] = _load_email_set("ALLOWED_EMAILS")


def resolve_role(email: str) -> Optional[str]:
    """Déterminer le rôle d’un utilisateur à partir de son email.

    Args:
        email: Adresse email normalisée (minuscules).

    Returns:
        ``"admin"``, ``"viewer"``, ou ``None`` si non autorisé.
    """
    email = email.lower().strip()

    if email in ADMIN_EMAILS:
        return "admin"

    # Si ALLOWED_EMAILS est vide ET que l'email n'est pas admin
    # → viewer ouvert (comportement par défaut si aucune liste configurée)
    if not ALLOWED_EMAILS:
        return "viewer"

    if email in ALLOWED_EMAILS:
        return "viewer"

    return None  # non autorisé


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

SESSION_KEY = "user"


def get_current_user(request: Request) -> Optional[dict]:
    """Retourne le dict utilisateur depuis la session, ou ``None``."""
    return request.session.get(SESSION_KEY)


def set_current_user(request: Request, user: dict, role: str) -> None:
    """Persiste l’utilisateur et son rôle dans le cookie de session signé.

    Args:
        request: Requête HTTP courante.
        user:    Dict userinfo retourné par Auth0.
        role:    Rôle résolu (``"admin"`` ou ``"viewer"``).
    """
    request.session[SESSION_KEY] = {
        "sub":     user.get("sub", ""),
        "name":    user.get("name", ""),
        "email":   user.get("email", ""),
        "picture": user.get("picture", ""),
        "role":    role,
    }


def clear_session(request: Request) -> None:
    """Supprime les données utilisateur du cookie de session."""
    request.session.pop(SESSION_KEY, None)


# ---------------------------------------------------------------------------
# Guards (utilisés dans les routes)
# ---------------------------------------------------------------------------

def login_required(request: Request) -> Optional[RedirectResponse]:
    """Redirige vers ``/login`` si l’utilisateur n’est pas connecté.

    Returns:
        :class:`RedirectResponse` vers ``/login``, ou ``None`` si connecté.
    """
    if not get_current_user(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


def admin_required(request: Request) -> Optional[RedirectResponse]:
    """Redirige vers ``/unauthorized`` si l’utilisateur n’est pas admin.

    Returns:
        :class:`RedirectResponse` vers ``/unauthorized``, ou ``None`` si admin.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.get("role") != "admin":
        return RedirectResponse(url="/unauthorized", status_code=302)
    return None
