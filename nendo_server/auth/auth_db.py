# -*- encoding: utf-8 -*-
"""Nendo API Server authentication and authorization database schema and functions."""
import asyncio
from typing import AsyncGenerator, List

from config import Settings
from fastapi import Depends
from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from sqlalchemy import Column, ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import Mapped, relationship, sessionmaker

settings = Settings()
DATABASE_URL = settings.auth_database_connection
Base: DeclarativeMeta = declarative_base()


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    oauth_accounts: Mapped[List[OAuthAccount]] = relationship(
        "OAuthAccount", foreign_keys=[OAuthAccount.user_id], lazy="joined",
    )


engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


async def get_active_user_ids() -> List[str]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.id).where(User.is_active == True),  # noqa: E712
        )
        user_ids = result.scalars().all()
        return [str(user_id) for user_id in user_ids]


def close_db():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(engine.dispose())
