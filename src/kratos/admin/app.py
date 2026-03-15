from fastapi import FastAPI

from . import routes


def create_admin_app(kratos_instance) -> FastAPI:
    """Create a FastAPI admin app wired to the given Kratos instance.

    Usage::

        from kratos import Kratos
        from kratos.admin import create_admin_app

        logger = Kratos(db_url="postgresql://...")
        app = create_admin_app(logger)
        # uvicorn main:app --port 8000
    """
    routes._session_factory = kratos_instance._session_factory

    app = FastAPI(title="Kratos Admin", version="0.1.0")
    app.include_router(routes.router)
    return app
