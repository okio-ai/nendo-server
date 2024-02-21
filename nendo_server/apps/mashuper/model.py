# -*- encoding: utf-8 -*-
"""Models used by the Mashuper app."""
import uuid
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, MetaData, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base(metadata=MetaData())


class Track(BaseModel):
    id: str
    name: str
    url: str


class Type(BaseModel):
    name: str
    image: str
    color: str
    keys: List[str]
    keywords: List[str]


class Settings(BaseModel):
    volume: str
    mute: bool


class Channel(BaseModel):
    id: str
    name: str
    type: Type
    color: str
    image: str
    settings: Settings
    track: Track


class Scene(BaseModel):
    id: Optional[int] = None
    user_id: uuid.UUID
    name: str
    author: str
    date: str
    channels: List[Channel]
    tempo: int


class SceneDB(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(UUID)
    name = Column(String)
    author = Column(String)
    date = Column(String)
    channels = Column(JSON)
    tempo = Column(Integer)


def init(db):
    """Initialization function to create the table(s)."""
    SceneDB.__table__.create(bind=db, checkfirst=True)
