# -*- encoding: utf-8 -*-
"""Handler for collections."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    import uuid

    from nendo import Nendo, NendoCollection, NendoTrack

logger = logging.getLogger(__name__)


class NendoCollectionsHandler(ABC):
    nendo_instance: Nendo = None
    logger: logging.Logger = None

    @abstractmethod
    def get_collection(self, collection_id: str) -> NendoCollection:
        """Get a collection by ID.

        Args:
        ----
            collection_id (str): track ID

        Returns:
        -------
            NendoCollection: The collection if it was found. None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_collection_size(self, collection_id: str) -> int:
        """Get the size of the collection, i.e. the number of tracks in it.

        Args:
            collection_id (str): The ID of the collection.

        Returns:
            int: Number of tracks in the collection.
        """
        raise NotImplementedError

    @abstractmethod
    def get_collections(
        self, limit: Optional[int] = None, offset: Optional[int] = None,
    ) -> List[NendoCollection]:
        """Get all collections.

        Args:
        ----
            limit (int, optional): Number of collections to return. Defaults to None.
            offset (int, optional): Offset to start from. Defaults to None.

        Returns:
        -------
            List[NendoCollection]: List of collections.
        """
        raise NotImplementedError

    @abstractmethod
    def create_collection(
        self,
        name: str,
        description: str,
        collection_type: str,
        track_ids: List[str],
        user_id: Optional[uuid.UUID] = None,
    ) -> NendoCollection:
        """Create a collection.

        Args:
        ----
            name (str): Name of the collection.
            user_id (Optional[uuid.UUID], optional): ID of the user who created the collection. Defaults to None.
            description (str): Description of the collection.
            collection_type (str): Type of the collection.
            track_ids (List[str]): List of track IDs to add to the collection.

        Returns:
        -------
            NendoCollection: The created collection.
        """
        raise NotImplementedError

    @abstractmethod
    def update_collection(
        self,
        collection_id: Union[str, uuid.UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
        collection_type: Optional[str] = None,
        user_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> NendoCollection:
        """Update a collection.

        Args:
        ----
            collection_id (uuid.UUID): ID of the collection.
            name (str): Name of the collection.
            user_id (Optional[uuid.UUID], optional): ID of the user who created the collection. Defaults to None.
            description (str): Description of the collection.
            collection_type (str): Type of the collection.
            track_ids (List[str]): List of track IDs to add to the collection.

        Returns:
        -------
            NendoCollection: The updated collection.
        """
        raise NotImplementedError

    @abstractmethod
    def add_track_to_collection(self, collection_id: str, track_id: str) -> NendoCollection:
        """Add a track to a collection.

        Args:
        ----
            collection_id (str): ID of the collection.
            track_id (str): ID of the track to add to the collection.

        Returns:
        -------
            NendoCollection: The updated collection.
        """
        raise NotImplementedError
    
    @abstractmethod
    def add_tracks_to_collection(self, collection_id: str, track_ids: List[str]) -> NendoCollection:
        """Add tracks to a collection.

        Args:
        ----
            collection_id (str): ID of the collection.
            track_ids (List[str]): IDs of the tracks to add to the collection.

        Returns:
        -------
            NendoCollection: The updated collection.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection.

        Args:
        ----
            collection_id (str): ID of the collection.

        Returns:
        -------
            bool: True if the collection was deleted. False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def remove_track_from_collection(
        self,
        track_id: str,
        collection_id: str,
    ) -> bool:
        """Remove a track from a collection.

        Args:
        ----
            collection_id (str): ID of the collection.
            track_id (str): ID of the track to remove from the collection.

        Returns:
        -------
            Bool
        """
        raise NotImplementedError

    @abstractmethod
    def add_related_collection(
        self,
        track_ids: List[Union[str, uuid.UUID]],
        collection_id: Union[str, uuid.UUID],
        name: str,
        description: str = "",
        user_id: Optional[uuid.UUID] = None,
        relationship_type: str = "relationship",
        meta: Optional[Dict[str, Any]] = None,
    ) -> NendoCollection:
        """Adds a new collection that is related to another collection.

        Args:
        ----
            tracks (List[Union[str, uuid.UUID]]): List of track ids.
            collection_id (Union[str, uuid.UUID]): Existing collection id.
            name (str): Name of the new related collection.
            description (str): Description of the new related collection.
            user_id (Optional[uuid.UUID]): ID of the user who created the new related collection.
            relationship_type (str): Type of the relationship.
            meta (Dict[str, Any]): Meta of the new related collection.

        Returns:
        -------
            schema.NendoCollection: The newly added NendoCollection object.
        """
        raise NotImplementedError

    @abstractmethod
    def get_related_collections(self, collection_id: str) -> List[NendoCollection]:
        """Get all related collections for a given collection.

        Args:
        ----
            collection_id (str): ID of the collection.

        Returns:
        -------
            List[NendoCollection]: List of related collections.
        """
        raise NotImplementedError


class LocalCollectionsHandler(NendoCollectionsHandler):
    def __init__(self, nendo_instance, logger):
        self.nendo_instance = nendo_instance
        self.logger = logger

    def get_collection(self, collection_id: str) -> NendoCollection:
        return self.nendo_instance.library.get_collection(
            collection_id=collection_id,
            get_related_tracks=False,
        )

    def get_collection_size(self, collection_id: str) -> int:
        return self.nendo_instance.library.collection_size(
            collection_id=collection_id,
        )

    def get_collection_tracks(self, collection_id: str) -> List[NendoTrack]:
        return self.nendo_instance.library.get_collection_tracks(
            collection_id=collection_id,
            order="desc",
        )

    def get_collections(
        self,
        user_id: Optional[uuid.UUID] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        name: Optional[str] = None,
        collection_types: Optional[List[str]] = None,
    ) -> List[NendoCollection]:
        return self.nendo_instance.library.find_collections(
            value=name,
            collection_types=collection_types,
            user_id=user_id,
            limit=limit,
            offset=offset,
            order="desc",
            order_by="created_at",
        )

    def create_collection(
        self,
        name: str,
        description: str,
        collection_type: str,
        track_ids: List[str],
        user_id: Optional[uuid.UUID] = None,
    ) -> NendoCollection:
        return self.nendo_instance.library.add_collection(
            name=name,
            user_id=user_id,
            description=description,
            collection_type=collection_type,
            track_ids=track_ids,
        )

    def update_collection(
        self,
        collection_id: Union[str, uuid.UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
        collection_type: Optional[str] = None,
        user_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> NendoCollection:
        collection = self.get_collection(collection_id=collection_id)
        collection.name = name
        collection.description = description
        collection.collection_type = collection_type
        return self.nendo_instance.library.update_collection(
            collection=collection,
        )

    def add_track_to_collection(
        self, collection_id: str, track_id: str,
    ) -> NendoCollection:
        return self.nendo_instance.library.add_track_to_collection(
            collection_id=collection_id,
            track_id=track_id,
        )
    
    def add_tracks_to_collection(
        self, collection_id: str, track_ids: List[str]
    ) -> NendoCollection:
        return self.nendo_instance.library.add_tracks_to_collection(
            track_ids=track_ids,
            collection_id=collection_id,
        )
        

    def save_collection_from_temp(
        self,
        collection_id: str,
        name: str,
    ) -> NendoCollection:
        collection = self.get_collection(collection_id=collection_id)
        track_ids = [rt.relationship_source.id for rt in collection.related_tracks]
        return self.nendo_instance.library.add_collection(
            name=name,
            user_id=collection.user_id,
            track_ids=track_ids,
            description=collection.description,
            collection_type="collection",
            visibility=collection.visibility,
            meta=collection.meta,
        )

    def delete_collection(self, collection_id: str, user_id: str) -> bool:
        return self.nendo_instance.library.remove_collection(
            collection_id=collection_id,
            user_id=user_id,
            remove_relationships=True,
        )

    def remove_track_from_collection(
        self,
        track_id: str,
        collection_id: str,
    ) -> bool:
        return self.nendo_instance.library.remove_track_from_collection(
            track_id=track_id,
            collection_id=collection_id,
        )
        
    def remove_tracks_from_collection(
        self,
        track_ids: List[str],
        collection_id: str,
    ) -> bool:
        return self.nendo_instance.library.remove_tracks_from_collection(
            collection_id=collection_id,
            track_ids=track_ids,
        )

    def add_related_collection(
        self,
        track_ids: List[Union[str, uuid.UUID]],
        collection_id: Union[str, uuid.UUID],
        name: str,
        description: str = "",
        user_id: Optional[uuid.UUID] = None,
        relationship_type: str = "relationship",
        meta: Optional[Dict[str, Any]] = None,
    ) -> NendoCollection:
        return self.nendo_instance.library.add_related_collection(
            track_ids=track_ids,
            collection_id=collection_id,
            name=name,
            description=description,
            user_id=user_id,
            relationship_type=relationship_type,
            meta=meta,
        )

    def get_related_collections(
        self,
        collection_id: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[NendoCollection]:
        return self.nendo_instance.library.get_related_collections(
            user_id=user_id, collection_id=collection_id,
        )


class RemoteCollectionsHandler(LocalCollectionsHandler):
    pass
