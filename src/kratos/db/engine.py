from sqlalchemy import Engine, create_engine

from ..exceptions import ConfigurationError


def build_engine(db_url: str) -> Engine:
    """Create a SQLAlchemy engine with PostgreSQL connection pooling."""
    if not db_url:
        raise ConfigurationError("db_url must not be empty")

    if not db_url.startswith("postgresql"):
        raise ConfigurationError("Only PostgreSQL is supported. db_url must start with 'postgresql'")

    return create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
