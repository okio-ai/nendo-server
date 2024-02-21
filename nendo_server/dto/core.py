# -*- encoding: utf-8 -*-
# ruff: noqa: TCH001, TCH003
"""Track Data Transfer Objects."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from nendo import NendoCollectionSlim, NendoTrackSlim


class PluginDataSmall(BaseModel):
    """Plugin data (small) class."""

    id: UUID
    user_id: UUID
    plugin_name: str
    plugin_version: str
    key: str
    value: str

class ResourceMetaSmall(BaseModel):
    """ResourceMeta (small) class."""
    sr: Optional[int] = None
    original_filename: Optional[str] = None
    image_type: Optional[str] = None

class ResourceSmall(BaseModel):
    """Resource (small) class."""

    id: UUID
    file_path: str
    file_name: str
    resource_type: str
    location: str
    meta: ResourceMetaSmall

class RelationshipSmall(BaseModel):
    """Relationship (small) class."""

    id: UUID
    source_id: UUID
    target_id: UUID
    relationship_type: str
    meta: Dict[str, Any]

class TrackTrackRelationshipSmall(RelationshipSmall):
    """TrackTrackRelationship (small) class."""
    source: Optional[NendoTrackSlim] = None
    target: Optional[NendoTrackSlim] = None

class TrackCollectionRelationshipSmall(RelationshipSmall):
    """TrackCollectionRelationship (small) class."""
    source: Optional[NendoTrackSlim] = None
    target: Optional[NendoCollectionSlim] = None

class CollectionCollectionRelationshipSmall(RelationshipSmall):
    """CollectionCollectionRelationship (small) class."""
    source: Optional[NendoCollectionSlim] = None
    target: Optional[NendoCollectionSlim] = None

class TrackSmall(BaseModel):
    """Track (small) class."""

    id: UUID
    user_id: UUID
    track_type: str
    visibility: str
    images: List[ResourceSmall]
    resource: ResourceSmall
    related_tracks: List[TrackTrackRelationshipSmall]
    related_collections: List[TrackCollectionRelationshipSmall]
    meta: Dict[str, Any]
    plugin_data: List[PluginDataSmall]

class CollectionSmall(BaseModel):
    """Collection (small) class."""

    id: UUID
    name: str
    description: str
    collection_type: str
    user_id: UUID
    visibility: str
    meta: Dict[str, Any]
    related_tracks: List[TrackCollectionRelationshipSmall]
    related_collections: List[CollectionCollectionRelationshipSmall]
