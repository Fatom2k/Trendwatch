"""FastAPI application factory for the TrendWatch web interface.

Runs as a standalone ASGI service alongside the scheduler:

    uvicorn web.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from web.routes.auth import router as auth_router
from web.routes.trends import router as trends_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application.

    Returns:
        Configured :class:`fastapi.FastAPI` instance.
    """
    application = FastAPI(
        title="TrendWatch",
        description="Manual trend entry interface",
        version="1.0.0",
        docs_url=None,   # disable Swagger UI in production
        redoc_url=None,
    )

    # Signed session cookie (Auth0 user stored server-side)
    secret = os.environ.get("SESSION_SECRET", "change-me-in-production-32chars!")
    application.add_middleware(SessionMiddleware, secret_key=secret, https_only=True)

    # Static files
    application.mount("/static", StaticFiles(directory="web/static"), name="static")

    # Routers
    application.include_router(auth_router)
    application.include_router(trends_router)

    @application.on_event("startup")
    async def _startup() -> None:
        """Ensure the Elasticsearch index exists on boot."""
        try:
            from config.settings import Settings
            from storage.elasticsearch import TrendStore
            s = Settings()
            if s.elasticsearch_enabled:
                store = TrendStore(host=s.elasticsearch_host, index_name=s.elasticsearch_index)
                if store.ping():
                    store.ensure_index()
                    logger.info("ES index ready.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ES not available at startup: %s", exc)

    return application


# Module-level app instance consumed by uvicorn
app = create_app()
