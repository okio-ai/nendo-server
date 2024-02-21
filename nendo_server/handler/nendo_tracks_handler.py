# -*- encoding: utf-8 -*-
"""Handler for tracks."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from handler.filters import TrackFilter, get_track_filters

if TYPE_CHECKING:
    import logging
    import uuid

    from nendo import Nendo, NendoTrack


class NendoTracksHandler(ABC):
    nendo_instance: Nendo = None
    logger: logging.Logger = None

    @abstractmethod
    def get_track(self, track_id: str, user_id: str) -> NendoTrack:
        """Get a track by ID.

        Args:
        ----
            track_id (str): Track ID
            user_id (str): User ID

        Returns:
        -------
            NendoTrack: The track if it was found. None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_track_filter_options(self) -> [TrackFilter]:
        """Get track filter options.

        Returns:
        -------
            List[str]: List of filter options
        """
        raise NotImplementedError

    @abstractmethod
    def get_tracks(
        self,
        offset: int = 0,
        limit: int = 10,
        search: Optional[List[str]] = None,
        filters: Optional[dict] = None,
        collection_id: Optional[str] = None,
        track_type: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[NendoTrack]:
        """Get tracks.

        Args:
        ----
            offset (int): Offset
            limit (int): Limit
            search (str, optional): Search query
            filters (dict, optional): Filters
            collection_id (str, optional): filter by a Collection
            track_type (str, optional): filter by a Track type
            order (str, optional): Sorting order
            user_id (str, optional): User ID

        Returns:
        -------
            List[NendoTrack]: List of tracks
        """
        raise NotImplementedError

    def get_related_tracks(
        self,
        track_id: str,
        offset: int,
        limit: int,
        user_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        filters: Optional[dict] = None,
        collection_id: Optional[str] = None,
        track_type: Optional[str] = None,
    ) -> List[NendoTrack]:
        """Get tracks that are related to the track with ID given by track_id.

        Args:
        ----
            track_id (str): Track ID
            offset (int): Offset for paging.
            limit (int): Limit for paging.
            user_id (uuid.UUID, optional): User ID.
            search (str, optional): Serch string.
            filters (dict, optional): Filters dictionary.
            collection_id (str, optional): ID of the related collection.
            track_type (str, optional): Type of the track.

        Returns:
        -------
            List[NendoTrack]: List of matching NendoTrack objects.
        """
        raise NotImplementedError

    @abstractmethod
    def create_track(
        self,
        user_id: Optional[Union[str, uuid.UUID]] = None,
        track_type: str = "track",
        meta: Optional[Dict[str, Any]] = None,
        visibility: str = "private",
        images: Optional[List[Any]] = None,
        file_path: str = "",
        resource_type: str = "audio",
        resource_meta: Optional[Dict[str, Any]] = None,
        copy_to_library: bool = True,
    ) -> NendoTrack:
        """Create a new track.

        Args:
        ----
            user_id (Union[str, uuid.UUID], optional): User ID.
            track_type (str, optional): Type of the track. Defaults to "track".
            meta (Dict[str, Any], optional): Metadata dictionary.
            visibility (str, optional): Visibility. Possible values are "public",
                "private", "hidden". Defaults to "private".
            images (List[Any], optional): List of images.
            file_path (str, optional): Path to the resource file. Defaults to "".
            resource_type (str, optional): Resource type. Defaults to "audio".
            resource_meta (Dict[str, Any], optional): Resource metadata dictionary.
            copy_to_library (bool): Flag that specifies whether to copy
                the resource into the library. Defaults to True.

        Raises:
        ------
            NotImplementedError: _description_

        Returns:
        -------
            NendoTrack: _description_
        """
        raise NotImplementedError

    @abstractmethod
    def update_track(
        self,
        user_id: Optional[Union[str, uuid.UUID]] = None,
        track_type: str = "track",
        meta: Optional[Dict[str, Any]] = None,
        visibility: str = "private",
        images: Optional[List[Any]] = None,
        resource_type: str = "text",
        resource_meta: Optional[Dict[str, Any]] = None,
    ) -> NendoTrack:
        """Update an existing track."""
        raise NotImplementedError

    @abstractmethod
    def delete_track(self, track_id: str) -> NendoTrack:
        """Delete track by ID.

        Args:
        ----
            track_id (str): track ID

        Returns:
        -------
            Boolean: True if the track was deleted. False otherwise.
        """
        raise NotImplementedError


class LocalTracksHandler(NendoTracksHandler):
    def __init__(self, nendo_instance, logger):
        self.nendo_instance = nendo_instance
        self.logger = logger

    def get_track(self, track_id: str, user_id: str):
        return self.nendo_instance.library.get_track(
            track_id=track_id,
            user_id=user_id,
        )

    def get_track_filter_options(self) -> [TrackFilter]:
        return get_track_filters()

    def get_tracks(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        search_meta: Optional[Dict[str, List[str]]] = None,
        collection_id: Optional[str] = None,
        track_type: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[NendoTrack]:
        return self.nendo_instance.library.filter_tracks_by_meta(
            search_meta=search_meta,
            filters=filters,
            collection_id=collection_id,
            track_type=track_type,
            order_by=order_by,
            order=order,
            offset=offset,
            limit=limit,
            user_id=user_id,
        )

    def get_related_tracks(
        self,
        track_id: str,
        offset: int,
        limit: int,
        user_id: Optional[uuid.UUID] = None,
        filters: Optional[Dict[str, Any]] = None,
        search_meta: Optional[Dict[str, List[str]]] = None,
        track_type: Optional[str] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
    ) -> List[NendoTrack]:
        return self.nendo_instance.library.filter_related_tracks_by_meta(
            track_id=track_id,
            direction="both",
            filters=filters,
            search_meta=search_meta,
            track_type=track_type,
            user_id=user_id,
            order_by=order_by,
            order=order,
            limit=limit,
            offset=offset,
        )

    def get_similar_tracks(
        self,
        track_id: str,
        offset: int,
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
        search_meta: Optional[Dict[str, List[str]]] = None,
        track_type: Optional[Union[str, List[str]]] = None,
        user_id: Optional[Union[str, uuid.UUID]] = None,
        collection_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> List[NendoTrack]:
        track = self.nendo_instance.library.get_track(
            track_id=track_id,
            user_id=user_id,
        )
        return self.nendo_instance.library.nearest_by_track(
            track=track,
            limit=limit,
            offset=offset,
            filters=filters,
            search_meta=search_meta,
            track_type=track_type,
            user_id=user_id,
            collection_id=collection_id,
            embedding_name="nendo_plugin_embed_clap",
        )

    def create_track(
        self,
        user_id: Optional[Union[str, uuid.UUID]] = None,
        track_type: str = "track",
        meta: Optional[Dict[str, Any]] = None,
        visibility: str = "private",
        images: Optional[List[Any]] = None,
        file_path: str = "",
        resource_type: str = "text",
        resource_meta: Optional[Dict[str, Any]] = None,
        copy_to_library: bool = True,
    ) -> NendoTrack:
        return self.nendo_instance.library.create_object(
            user_id=user_id,
            track_type=track_type,
            meta=meta,
            visibility=visibility,
            images=images,
            file_path=file_path,
            resource_type=resource_type,
            resource_meta=resource_meta,
            copy_to_library=copy_to_library,
        )

    def update_track(
        self,
        track_id: str,
        user_id: Optional[Union[str, uuid.UUID]] = None,
        track_type: str = "track",
        meta: Optional[Dict[str, Any]] = None,
        visibility: str = "private",
        images: Optional[List[Any]] = None,
        resource_type: str = "text",
        resource_meta: Optional[Dict[str, Any]] = None,
    ) -> NendoTrack:
        track = self.nendo_instance.library.get_track(
            track_id=track_id,
            user_id=user_id,
        )
        track.visibility = visibility
        track.track_type = track_type
        track.meta = meta
        track.images = images
        track.resource.resource_type = resource_type
        track.resource.meta = resource_meta
        track.save()
        return track

    def delete_track(self, track_id: str, user_id: str) -> bool:
        try:
            self.nendo_instance.library.remove_track(
                track_id=track_id,
                remove_relationships=True,
                remove_plugin_data=True,
                remove_resources=True,
                remove_embeddings=True,
                user_id=user_id,
            )
            return True
        except Exception as e:
            self.logger.error(e)
            return False


class RemoteTracksHandler(LocalTracksHandler):
    pass
