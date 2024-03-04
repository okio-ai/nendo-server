# -*- encoding: utf-8 -*-
"""Nendo server collection routes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID  # noqa: TCH003

from api.response import NendoHTTPResponse
from api.utils import APIRouter
from auth.auth_users import fastapi_users
from dto.core import CollectionSmall, TrackSmall
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory
from pydantic import BaseModel

from utils import extract_search_filter

if TYPE_CHECKING:
    from auth.auth_db import User


router = APIRouter()

DEFAULT_PAGE_SIZE = 10


@router.get("/", name="collections:get", response_model=NendoHTTPResponse)
async def get_collections(
    cursor: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    name: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collection_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        offset = cursor * limit
        collections = collection_handler.get_collections(
            user_id=user.id,
            limit=limit,
            offset=offset,
            name=name,
            collection_types=["collection", "playlist", "favorites"],
        )
        collections = [CollectionSmall.parse_obj(c.dict()) for c in collections]

        has_next = len(collections) == limit
        next_cursor = cursor + 1 if has_next else cursor
    except Exception as e:
        collection_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=collections, has_next=False, cursor=next_cursor)


@router.get("/{collection_id}", name="collection:get", response_model=NendoHTTPResponse)
async def get_collection(
    collection_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collection_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collection_handler.get_collection(collection_id=collection_id)
        delattr(collection, "nendo_instance")
        collection_size = collection_handler.get_collection_size(
            collection_id=collection_id,
        )
    except Exception as e:
        collection_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(status_code=404, content={"detail": "Collection not found"})

    return NendoHTTPResponse(
        data={"collection": collection, "size": collection_size},
        has_next=False,
        cursor=0,
    )


@router.get(
    "/{collection_id}/tracks", name="collection:get", response_model=NendoHTTPResponse,
)
async def get_collection_tracks(
    collection_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        tracks = tracks_handler.get_collection_tracks(collection_id=collection_id)
        tracks = [TrackSmall.parse_obj(track.dict()) for track in tracks]
    except Exception as e:
        tracks_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if tracks is None:
        return JSONResponse(status_code=404, content={"detail": "Collection not found"})

    return NendoHTTPResponse(data=tracks, has_next=False, cursor=0)


class CreateCollectionParam(BaseModel):
    name: str
    description: str = ""
    collection_type: str = "generic"
    track_ids: List[str] = []


@router.post("/", name="collection:post", response_model=NendoHTTPResponse)
async def create_collection(
    create_collection_param: CreateCollectionParam,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collections_handler.create_collection(
            name=create_collection_param.name,
            description=create_collection_param.description,
            user_id=user.id,
            collection_type="collection",
            track_ids=create_collection_param.track_ids,
        )
        delattr(collection, "nendo_instance")
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=500, content={"detail": "Error creating collection"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)


class UpdateCollectionParam(BaseModel):
    name: Optional[str] = (None,)
    description: Optional[str] = (None,)
    collection_type: Optional[str] = (None,)


@router.patch(
    "/update/{collection_id}",
    name="collection:update",
    response_model=NendoHTTPResponse,
)
async def update_collection(
    collection_id: str,
    update_collection_param: UpdateCollectionParam,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collections_handler.update_collection(
            collection_id=collection_id,
            name=update_collection_param.name,
            description=update_collection_param.description,
            collection_type=update_collection_param.collection_type,
            user_id=user.id,
        )
        delattr(collection, "nendo_instance")
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=500, content={"detail": "Error updating collection"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)


@router.put("/{collection_id}", name="collection:put", response_model=NendoHTTPResponse)
async def add_track_to_collection(
    collection_id: str,
    track_id: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    if track_id is None:
        return JSONResponse(
            status_code=400, content={"detail": "Error track_id is required"},
        )

    try:
        collection = collections_handler.add_track_to_collection(
            track_id=track_id,
            collection_id=collection_id,
        )
        delattr(collection, "nendo_instance")
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=500, content={"detail": "Error adding track to a collection"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)

@router.put(
    "/{collection_id}/tracks",
    name="collection: add tracks to collection",
    response_model=NendoHTTPResponse,
)
async def add_tracks_to_collection(
    collection_id: str,
    search_filter: Optional[str] = None,
    related_collection_id: Optional[str] = None,
    track_type: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        search_filters = extract_search_filter(search_filter)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search filter: {e}",
        ) from e
    if track_type is None or track_type == "all":
        track_type_list = None
    else:
        track_type_list = track_type.split(",")
    tracks, _ = tracks_handler.get_tracks(
        filters=search_filters["filters"],
        search_meta=search_filters["search_meta"],
        track_type=track_type_list,
        collection_id=related_collection_id if len(related_collection_id) > 0 else None,
        user_id=str(user.id),
    )
    
    track_ids = [str(track.id) for track in tracks]

    try:
        collection = collections_handler.add_tracks_to_collection(
            collection_id=collection_id,
            track_ids=track_ids,
        )
        delattr(collection, "nendo_instance")
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=500, content={"detail": "Error adding track to a collection"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)

@router.patch(
    "/{collection_id}/remove/tracks",
    name="collection: remove tracks from collection",
    response_model=NendoHTTPResponse,
)
async def remove_tracks_from_collection(
    collection_id: str,
    search_filter: Optional[str] = None,
    track_type: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        search_filters = extract_search_filter(search_filter)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search filter: {e}",
        ) from e
    if track_type is None or track_type == "all":
        track_type_list = None
    else:
        track_type_list = track_type.split(",")
    tracks, _ = tracks_handler.get_tracks(
        filters=search_filters["filters"],
        search_meta=search_filters["search_meta"],
        track_type=track_type_list,
        user_id=str(user.id),
        collection_id=str(collection_id),
    )
    
    track_ids = [str(track.id) for track in tracks]

    try:
        result = collections_handler.remove_tracks_from_collection(
            collection_id=collection_id,
            track_ids=track_ids,
        )
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=result)



@router.patch(
    "/{collection_id}/remove/{track_id}",
    name="collection:remove track from collection",
    response_model=NendoHTTPResponse,
)
async def remove_track_from_collection(
    collection_id: str,
    track_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        result = collections_handler.remove_track_from_collection(
            track_id=track_id, collection_id=collection_id,
        )
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=result)

@router.put(
    "/{collection_id}/save",
    name="collection:make temporary collection permanent",
    response_model=NendoHTTPResponse,
)
async def save_collection_from_temp(
    collection_id: str,
    name: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collections_handler.save_collection_from_temp(
            collection_id=collection_id,
            name=name,
        )
        delattr(collection, "nendo_instance")
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=collection)


@router.delete(
    "/{collection_id}", name="collection:delete", response_model=NendoHTTPResponse,
)
async def delete_collection(
    collection_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        result = collections_handler.delete_collection(
            collection_id=collection_id,
            user_id=str(user.id),
        )
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=result)


class AddRelatedCollectionModel(BaseModel):
    track_ids: List[Union[str, UUID]]
    collection_id: Union[str, UUID]
    name: str
    description: str = ""
    relationship_type: str = "relationship"
    meta: Dict[str, Any] = {}


@router.post(
    "/related", name="related_collection:post", response_model=NendoHTTPResponse,
)
async def create_related_collection(
    add_related_collection_model: AddRelatedCollectionModel,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collections_handler.add_related_collection(
            track_ids=add_related_collection_model.track_ids,
            collection_id=add_related_collection_model.collection_id,
            name=add_related_collection_model.name,
            description=add_related_collection_model.description,
            user_id=user.id,
            relationship_type=add_related_collection_model.relationship_type,
            meta=add_related_collection_model.meta,
        )
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=422,
            content={"detail": "Error creating related collection"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)


@router.get(
    "/related/{collection_id}",
    name="related_collection:get",
    response_model=NendoHTTPResponse,
)
async def get_related_collection(
    collection_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    collections_handler = handler_factory.create(handler_type=HandlerType.COLLECTIONS)

    try:
        collection = collections_handler.get_related_collections(
            user_id=user.id,
            collection_id=collection_id,
        )
    except Exception as e:
        collections_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if collection is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Collection not found"},
        )

    return NendoHTTPResponse(data=collection, has_next=False, cursor=0)
