# -*- encoding: utf-8 -*-
"""SQLAlchemy ORM model for the nendo schema."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base(metadata=MetaData())


class UserInviteCodeDB(Base):
    __tablename__ = "user_invite_code"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invite_code = Column(String, nullable=False)
    claimed_by = Column(String, default=None)

    def __repr__(self):
        return (
            f"<UserInviteCodeDB("
            f"id={self.id}, "
            f"invite_code={self.invite_code}, "
            f"claimed_by={self.claimed_by})"
        )
