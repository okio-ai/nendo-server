# -*- encoding: utf-8 -*-

"""Nendo core Postgresql library plugin."""
import logging
from typing import List, Optional

from config import Settings
from sqlalchemy import Engine, create_engine

from . import model
from .model import UserInviteCodeDB
from .sqlalchemydb import SQLAlchemyDB


class PostgresDB(SQLAlchemyDB):
    """PostgresDB connector for Nendo server."""

    config: Settings = None
    db: Engine = None
    logger: logging.Logger

    def _connect(self, db: Optional[Engine] = None):
        """Open Postgres session."""
        self.logger.info("Connecting to postgres host %s", self.config.postgres_host)
        engine_string = (
            "postgresql://"
            f"{self.config.postgres_user}:"
            f"{self.config.postgres_password}@"
            f"{self.config.postgres_host}/"
            f"{self.config.postgres_db}"
        )
        self.db = db or create_engine(engine_string)
        model.Base.metadata.create_all(bind=self.db)

        self.logger.info("PostgresDBLibrary initialized successfully.")

    def get_unclaimed_invite_codes(self) -> List[UserInviteCodeDB]:
        unclaimed_invite_codes = []
        with self.session_scope() as session:
            unclaimed = (
                session.query(UserInviteCodeDB)
                .filter(UserInviteCodeDB.claimed_by == None)  # noqa: E711
                .all()
            )

            for code in unclaimed:
                unclaimed_invite_codes.append(
                    {
                        "id": code.id,
                        "invite_code": code.invite_code,
                        "claimed_by": code.claimed_by,
                    },
                )

        return unclaimed_invite_codes

    def claim_invite_code(self, invite_code: str, email: str) -> None:
        with self.session_scope() as session:
            tokens_to_update = (
                session.query(UserInviteCodeDB)
                .filter(UserInviteCodeDB.invite_code == invite_code)
                .all()
            )

            for token in tokens_to_update:
                token.claimed_by = email

            session.commit()
