"""TrendWatch web interface package.

Exposes a FastAPI application with Google OAuth (via Auth0) and
an HTMX-powered form to manually add trends to Elasticsearch.
"""

from web.app import create_app

__all__ = ["create_app"]
