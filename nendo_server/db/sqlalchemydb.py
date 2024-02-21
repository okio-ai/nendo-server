# -*- encoding: utf-8 -*-
"""NendoServer SQLAlchemy DB."""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

from config import Settings
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    import logging

    from sqlalchemy.engine.base import Engine


class SQLAlchemyDB:
    config: Settings = None
    db: Engine = None
    logger: logging.Logger

    def __init__(
        self,
        config: Optional[Settings] = None,
        db: Optional[Engine] = None,
        logger: Optional[logging.Logger] = None,
        # session: Optional[Session] = None,
    ) -> None:
        self.config = config or Settings()
        self.logger = logger
        self._connect(db)  # , session)

    def _connect(
        self,
        db: Optional[Engine] = None,
        # session: Optional[Session] = None,
    ):
        raise NotImplementedError

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = sessionmaker(autocommit=False, autoflush=False, bind=self.db)()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def _disconnect(self):
        """Dispose the database engine."""
        if hasattr(self, "db"):
            # self.db.close()
            self.db.dispose()
            del self.db
