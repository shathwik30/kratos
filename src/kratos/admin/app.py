from fastapi import FastAPI

from . import routes
from .auth import ApiKeyAuthMiddleware


def create_admin_app(kratos_instance) -> FastAPI:
    """Create a FastAPI admin app wired to the given Kratos instance.

    All endpoints require a valid ``x-api-key`` header.
    Use ``kratos_instance.create_api_key(name="...")`` to bootstrap
    the first key, then pass it via the header for subsequent requests.

    Usage::

        from kratos import Kratos
        from kratos.admin import create_admin_app

        logger = Kratos(db_url="postgresql://...")
        key = logger.create_api_key(name="default")
        print(f"Your API key: {key.key}")   # store this!

        app = create_admin_app(logger)
        # uvicorn main:app --port 8000
        # curl -H "x-api-key: <key>" http://localhost:8000/admin/stats
    """
    routes._session_factory = kratos_instance._session_factory

    app = FastAPI(title="Kratos Admin", version="0.1.0")
    app.add_middleware(ApiKeyAuthMiddleware, session_factory=kratos_instance._session_factory)
    app.include_router(routes.router)
    return app
