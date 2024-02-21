# -*- encoding: utf-8 -*-
"""Nendo API Server track routes."""
from __future__ import annotations

import json
import os
import re
import sys
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import unquote

from api.response import NendoHTTPResponse
from api.utils import APIRouter
from auth.auth_users import fastapi_users
from dto.core import TrackSmall
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory
from pydantic import BaseModel, parse_obj_as

from nendo import NendoLibraryError

if TYPE_CHECKING:
    from auth.auth_db import User

router = APIRouter()

DEFAULT_PAGE_SIZE = 10
RESOURCE_TYPES = {
    "track": "audio",
    "image": "image",
    "text": "text",
    "website": "text",
}

class TrackObj(BaseModel):
    """Object used when creating NendoTracks."""

    track_type: str
    meta: dict = {}
    resource: dict = {}
    images: list = []

class TrackSearchFilterParams(BaseModel):
    """Filter parameters object."""

    search: str = ""
    filters: List = []


def extract_search_filter(searchfilter: Optional[str] = None):
    search_params = TrackSearchFilterParams()
    # URL decode the JSON parameter
    if searchfilter is not None and searchfilter != "":
        decoded_search_filter = unquote(searchfilter)
        if decoded_search_filter is not None:
            search_params = parse_obj_as(
                TrackSearchFilterParams,
                json.loads(decoded_search_filter),
            )

    matched = re.findall(r'(?:"([^"]*)")|(\S+)', search_params.search)
    search_list = [x[0] if x[0] else x[1] for x in matched]
    search_meta = {"": search_list}
    filters = {}
    for f in search_params.filters:
        if f["search"] == "metadata":
            matched = re.findall(r'(?:"([^"]*)")|(\S+)', f["value"])
            search_list = [x[0] if x[0] else x[1] for x in matched]
            search_meta.update({f["key"]: search_list})
        elif f["type"] == "range":
            value_min = (
                float(f["value_min"]) if
                f["value_min"] is not None else
                sys.float_info.min
            )
            value_max = (
                float(f["value_max"]) if
                f["value_max"] is not None else
                sys.float_info.max
            )
            filter_value = (value_min, value_max)
            filters.update({f["key"]: filter_value})
        elif f["type"] == "key":
            filters.update({
                "key": f["value_key"],
                "scale": f["value_scale"],
            })
        elif f["type"] == "multiselect":
            for value in f["values"]:
                filters.update({f["key"]: value})
        else:
            filter_value = f["value"]
            filters.update({f["key"]: filter_value})
    return {
        "search_meta": search_meta,
        "filters": filters,
    }


@router.post("/", name="track:create", response_model=NendoHTTPResponse)
async def create_track(
    track_obj: TrackObj,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        new_track = tracks_handler.create_track(
            user_id=user.id,
            track_type=track_obj.track_type,
            meta=track_obj.meta,
            images=track_obj.images,
            file_path="",  # TODO
            resource_type=RESOURCE_TYPES[track_obj.track_type],
            # resource_meta={}, #TODO track_obj.resource_meta,
        )
        if new_track is not None and hasattr(new_track, "nendo_instance"):
            delattr(new_track, "nendo_instance")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating object: {e}",
        ) from e

    return NendoHTTPResponse(data=new_track, has_next=False, cursor=0)


@router.patch("/{track_id}", name="track:update", response_model=NendoHTTPResponse)
async def update_track(
    track_id: str,
    track_obj: TrackObj,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        updated_track = tracks_handler.update_track(
            track_id=track_id,
            user_id=user.id,
            track_type=track_obj.track_type,
            meta=track_obj.meta,
            images=track_obj.images,
            resource_type=RESOURCE_TYPES[track_obj.track_type],
            resource_meta={},  # TODO track_obj.resource_meta,
        )
        if updated_track is not None and hasattr(updated_track, "nendo_instance"):
            delattr(updated_track, "nendo_instance")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating object: {e}",
        ) from e

    return NendoHTTPResponse(data=updated_track, has_next=False, cursor=0)


@router.get("/{track_id}", name="track:get", response_model=NendoHTTPResponse)
async def get_track(
    track_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        track = tracks_handler.get_track(track_id=track_id, user_id=str(user.id))
        if track is not None and hasattr(track, "nendo_instance"):
            delattr(track, "nendo_instance")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    if track is None:
        return JSONResponse(status_code=404, content={"detail": "Track not found"})

    return NendoHTTPResponse(data=track, has_next=False, cursor=0)


@router.get("/", name="tracks:get", response_model=NendoHTTPResponse)
async def get_tracks(
    cursor: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    search_filter: Optional[str] = None,
    collection_id: Optional[str] = None,
    track_type: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    try:
        search_filters = extract_search_filter(search_filter)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search filter: {e}",
        ) from e

    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        offset = cursor * limit
        if track_type is None or track_type == "all":
            track_type_list = None
        else:
            track_type_list = track_type.split(",")
        order_by = "collection" if collection_id is not None else "updated_at"
        order = "desc"
        tracks = tracks_handler.get_tracks(
            limit=limit,
            offset=offset,
            filters=search_filters["filters"],
            search_meta=search_filters["search_meta"],
            collection_id=collection_id,
            track_type=track_type_list,
            order_by=order_by,
            order=order,
            user_id=str(user.id),
        )
        tracks = [TrackSmall.parse_obj(track.dict()) for track in tracks]
        for track in tracks:
            for i, pd in enumerate(track.plugin_data):
                if isinstance(pd.value, str) and len(pd.value) > 2000:
                    track.plugin_data[i].value = track.plugin_data[i].value[:2000] + " [...]"

        has_next = len(tracks) == limit
        next_cursor = cursor + 1 if has_next else cursor
    except Exception as e:
        tracks_handler.logger.exception(f"Nendo error: {e}")
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=tracks, has_next=has_next, cursor=next_cursor)


@router.get(
    "/{track_id}/related", name="get related tracks", response_model=NendoHTTPResponse,
)
async def get_related_tracks(
    track_id: str,
    cursor: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    search_filter: Optional[str] = None,
    track_type: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    try:
        search_filters = extract_search_filter(search_filter)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search filter: {e}",
        ) from e

    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)
    try:
        offset = cursor * limit
        if track_type is None or track_type == "all":
            track_type_list = None
        else:
            track_type_list = track_type.split(",")
        order_by = "updated_at"
        order = "desc"
        tracks = tracks_handler.get_related_tracks(
            track_id=track_id,
            limit=limit,
            offset=offset,
            user_id=user.id,
            filters=search_filters["filters"],
            search_meta=search_filters["search_meta"],
            track_type=track_type_list,
            order_by=order_by,
            order=order,
        )
        tracks = [TrackSmall.parse_obj(track.dict()) for track in tracks]
        for track in tracks:
            for i, pd in enumerate(track.plugin_data):
                if isinstance(pd.value, str) and len(pd.value) > 2000:
                    track.plugin_data[i].value = track.plugin_data[i].value[:2000] + " [...]"

        has_next = len(tracks) == limit
        next_cursor = cursor + 1 if has_next else cursor
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=tracks, has_next=has_next, cursor=next_cursor)


@router.get(
    "/{track_id}/similar",
    name="get similar tracks",
    response_model=NendoHTTPResponse,
)
async def get_similar_tracks(
    track_id: str,
    cursor: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    search_filter: Optional[str] = None,
    collection_id: Optional[str] = None,
    track_type: Optional[str] = None,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)
    try:
        search_filters = extract_search_filter(search_filter)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search filter: {e}",
        ) from e
    try:
        offset = cursor * limit
        if track_type is None or track_type == "all":
            track_type_list = None
        else:
            track_type_list = track_type.split(",")
        tracks = tracks_handler.get_similar_tracks(
            track_id=track_id,
            limit=limit,
            filters=search_filters["filters"],
            search_meta=search_filters["search_meta"],
            offset=offset,
            track_type=track_type_list,
            user_id=str(user.id),
            collection_id=collection_id,
        )
        tracks = [TrackSmall.parse_obj(track.dict()) for track in tracks]
        for track in tracks:
            for i, pd in enumerate(track.plugin_data):
                if isinstance(pd.value, str) and len(pd.value) > 2000:
                    track.plugin_data[i].value = track.plugin_data[i].value[:2000] + " [...]"

        # currently no paging
        has_next = len(tracks) == limit
        next_cursor = cursor + 1 if has_next else cursor
    except NendoLibraryError as e:
        raise HTTPException(status_code=422, detail=f"Nendo error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=tracks, has_next=has_next, cursor=next_cursor)


@router.options("/", name="tracks:options", response_model=NendoHTTPResponse)
async def get_tracks_options(
    user: User = Depends(fastapi_users.current_user()),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)

    try:
        options = tracks_handler.get_track_filter_options()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e
    return NendoHTTPResponse(data=options, has_next=False, cursor=0)


@router.delete("/{track_id}", name="track:delete", status_code=204)
async def delete_track(
    track_id: str,
    user: User = Depends(fastapi_users.current_user()),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
):
    tracks_handler = handler_factory.create(handler_type=HandlerType.TRACKS)
    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    track = tracks_handler.get_track(track_id=track_id, user_id=str(user.id))
    filepath = assets_handler.get_audio_path(track_id)

    result = tracks_handler.delete_track(track_id=track_id, user_id=str(user.id))

    # also delete transcoded version
    filepath_mp3 = f"{os.path.splitext(filepath)[0]}.mp3"
    if os.path.isfile(filepath_mp3):
        os.remove(filepath_mp3)

    # also delete related images
    for image in track.images:
        os.remove(os.path.join(image.file_path, image.file_name))

    if not result:
        raise HTTPException(status_code=404, detail="Unable to delete track")
    return JSONResponse(status_code=200, content={"detail": "Track deleted"})
