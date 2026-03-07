from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..exceptions import DatabaseError


class SessionFactory:
    """Creates database sessions from an engine."""

    def __init__(self, engine: Engine) -> None:
        self._session_maker = sessionmaker(bind=engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transactional session scope.

        Commits on success, rolls back on exception, always closes.
        """
        session = self._session_maker()
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            raise DatabaseError(str(exc)) from exc
        finally:
            session.close()
