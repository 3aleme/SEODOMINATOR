"""PostgreSQL database initialisation and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.storage.models import Base


class Database:
    """Wraps SQLAlchemy engine; creates tables on init and provides sessions."""

    def __init__(self, url: str, engine: Engine | None = None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_engine(url, pool_pre_ping=True)
        self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        sess = self._Session()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    @property
    def engine(self) -> Engine:
        return self._engine


def init_db(url: str) -> Database:
    db = Database(url=url)
    Base.metadata.create_all(db.engine)
    return db
