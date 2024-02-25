# -*- encoding: utf-8 -*-
"""Nendo server asset routes."""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, List, Optional

import aiofiles
from api.response import NendoHTTPResponse
from api.utils import APIRouter
from auth.auth_users import fastapi_users
from fastapi import Body, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory
from starlette.responses import (
    FileResponse,
)
from utils import create_spectrogram

if TYPE_CHECKING:
    from auth.auth_db import User

router = APIRouter()

ACTIONS = {
    "voiceanalysis": {
        "name": "Voice Analysis",
        "image": "nendo/voiceanalysis",
        "script": "voiceanalysis/voiceanalysis.py",
        "plugins": [
            "nendo_plugin_embed_clap",
            "nendo_plugin_transcribe_whisper",
            "nendo_plugin_textgen",
        ],
    },
    "musicanalysis": {
        "name": "Music Analysis",
        "image": "nendo/musicanalysis",
        "script": "musicanalysis/musicanalysis.py",
        "plugins": [
            "nendo_plugin_embed_clap",
            "nendo_plugin_classify_core",
            "nendo_plugin_caption_lpmusiccaps",
        ],
    },
}


@router.post("/audio", name="audio:post")
async def upload_audio_post(
    request: Request,
    file: UploadFile,
    collection_id: Optional[str] = Query(""),
    run_action: Optional[str] = Query(""),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
    action_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    if assets_handler.user_reached_storage_limit(str(user.id)):
        raise HTTPException(status_code=507, detail="Storage limit reached")

    try:
        temp_dir = tempfile.TemporaryDirectory()

        track_ids = []

        async with aiofiles.open(
            os.path.join(temp_dir.name, file.filename),
            "wb",
        ) as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
            request.app.state.logger.info(f"Done writing tempfile: {out_file.name}")

            tracks = assets_handler.add_to_library(
                file_path=out_file.name,
                user_id=user.id,
            )

    except Exception as e:
        assets_handler.logger.exception(f"Error uploading: {e}")
    finally:
        temp_dir.cleanup()

    if len(tracks) == 0:
        # TODO handle unsupported file type and throw 422
        # raise HTTPException(status_code=422, detail="Filetype not supported")
        return JSONResponse(status_code=500, content={"status": "failed"})

    for track in tracks:
        if not any([image.meta["image_type"] == "spectrogram" for image in track.images]):
            action_handler.create_action(
                user_id=str(user.id),
                action_name="Render spectrogram",
                gpu=False,
                func=create_spectrogram,
                track_ids=[track.id],
            )

    return_id = str(tracks[0].id)
    # add track(s) to collection
    if len(collection_id) > 0:
        collection_handler = handler_factory.create(
            handler_type=HandlerType.COLLECTIONS,
        )
        for track in tracks:
            collection_handler.add_track_to_collection(
                collection_id=collection_id,
                track_id=track.id,
            )
        return_id = f"collection/{collection_id}"


    return_dict = {"status": "success", "result_id": return_id}
    if len(run_action) > 0:
        if run_action not in ACTIONS:
            return JSONResponse(status_code=400, content={"status": "Unknown action"})
        for track in tracks:
            action_id = action_handler.create_docker_action(
                user_id=str(user.id),
                image=ACTIONS[run_action]["image"],
                gpu=True,
                script_path=ACTIONS[run_action]["script"],
                plugins=ACTIONS[run_action]["plugins"],
                action_name=ACTIONS[run_action]["name"],
                container_name="",
                exec_run=False,
                replace_plugin_data=False,
                func_timeout=0,
                target_id=track.id,
            )
        return_dict.update({"action_id": action_id})

    return JSONResponse(
        status_code=200,
        content=return_dict,
    )


@router.get("/audio/{track_id}", name="audio:get")
async def serve_audio_asset(
    track_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: Optional[User] = Depends(fastapi_users.current_user(optional=True)),
):
    if track_id is None or track_id == "":
        raise HTTPException(status_code=400, detail="track_id is required")

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    # if config.get_settings().environment == Environment.LOCAL.value:
    filepath = assets_handler.get_audio_path(track_id)
    if filepath is None:
        raise HTTPException(status_code=404, detail="Track not found")

    # simple transcoding
    filepath_mp3 = f"{os.path.splitext(filepath)[0]}.mp3"
    if os.path.isfile(filepath_mp3):
        filepath = filepath_mp3

    headers = {
        "Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"',
        "Accept-Ranges": "bytes",
    }
    return FileResponse(filepath, headers=headers, media_type="audio/wav")

    # TODO re-enable bucket storage at some point
    # if config.get_settings().environment == Environment.REMOTE.value:
    #     bucket_name = "BUCKET_NOT_FOUND"
    #     if user is not None:
    #         bucket_name = f"{user.id}-nendo"

    #     filepath = assets_handler.get_audio_path(
    #         track_id=track_id, user_id=str(user.id),
    #     )

    #     # HACK cheap transcoding, fix later
    #     filepath = os.path.splitext(filepath)[0] + ".mp3"

    #     if filepath is None:
    #         raise HTTPException(status_code=404, detail="Track not found")

    #     # Make a GET request to GCS
    #     response = requests.get(filepath, stream=True)

    #     # Check if the request was successful
    #     if response.status_code != 200:
    #         # Handle the error in some way, here we just return a simple message
    #         return {"error": "Could not retrieve the file"}

    #     # Return the streamed content as a response
    #     return StreamingResponse(
    #         response.iter_content(chunk_size=8192), media_type="audio/wav",
    #     )

    raise HTTPException(status_code=500, detail="Nendo error: Not implemented")


@router.get("/audio/download/track/{track_id}", name="track:download")
async def download_track(
    track_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    if track_id is None or track_id == "":
        raise HTTPException(status_code=400, detail="track_id is required")

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    # if config.get_settings().environment == Environment.LOCAL:
    filepath = assets_handler.get_audio_path(track_id, user_id=str(user.id))
    if filepath is None:
        raise HTTPException(status_code=404, detail="Track not found")

    headers = {
        "Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"',
    }
    return FileResponse(filepath, headers=headers, media_type="audio/wav")

    # if config.get_settings().environment == Environment.REMOTE:
    #     # bucket_name = "BUCKET_NOT_FOUND"
    #     # if user is not None:
    #     #     bucket_name = f"{user.id}-nendo"

    #     filepath = assets_handler.get_audio_path(
    #         track_id=track_id, user_id=str(user.id),
    #     )
    #     if filepath is None:
    #         raise HTTPException(status_code=404, detail="Track not found")

    #     # Make a GET request to GCS
    #     response = requests.get(filepath, stream=True)
    #     temp_path = ""
    #     with NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
    #         shutil.copyfileobj(response.raw, tmpfile)
    #         temp_path = tmpfile.name

    #     # Check if the request was successful
    #     if response.status_code != 200:
    #         # Handle the error in some way, here we just return a simple message
    #         return {"error": "Could not retrieve the file"}

    #     headers = {
    #         "Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"'
    #     }

    #     # Return the streamed content as a response
    #     return FileResponse(
    #         temp_path, headers=headers, media_type="audio/mpeg",
    #     )

    raise HTTPException(
        status_code=500,
        detail="Nendo error: Environment Not implemented",
    )


@router.get("/audio/download/collection/{collection_id}", name="collection:download")
def download_collection(
    request: Request,
    collection_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    if collection_id is None or collection_id == "":
        raise HTTPException(status_code=400, detail="collection_id is required")

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    # if config.get_settings().environment == Environment.LOCAL.value:
    track_paths = assets_handler.get_collection_audio_paths(collection_id)
    if track_paths is None:
        raise HTTPException(status_code=404, detail="Collection is empty")

    zip_file_name = os.path.join(
        "/tmp/",
        f"collection_{collection_id}_{time.time_ns() // 1000000}.zip",
    )
    files_str = " ".join(track_paths)
    subprocess.run(f"zip {zip_file_name} {files_str}", check=True, shell=True)

    headers = {
        "Content-Disposition": f'attachment; filename="{os.path.basename(zip_file_name)}"',
    }
    return FileResponse(zip_file_name, headers=headers, media_type="application/zip")

    # TODO re-enable bucket storage at some point
    # if config.get_settings().environment == Environment.REMOTE:
    #     bucket_name = "BUCKET_NOT_FOUND"
    #     if user is not None:
    #         bucket_name = f"{user.id}-nendo"

    #     track_paths = assets_handler.get_collection_audio_paths(
    #         collection_id=collection_id, bucket_name=bucket_name
    #     )
    #     if track_paths is None:
    #         raise HTTPException(status_code=404, detail="Collection is empty")

    #     temp_paths = []
    #     # Make a GET request to GCS
    #     for filepath in track_paths:
    #         response = requests.get(filepath, stream=True)
    #         temp_path = ""
    #         with NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
    #             shutil.copyfileobj(response.raw, tmpfile)
    #             temp_path = tmpfile.name

    #         # Check if the request was successful
    #         if response.status_code != 200:
    #             # Handle the error in some way, here we just return a simple message
    #             return {"error": "Could not retrieve the file"}
    #         temp_paths.append(temp_path)

    #     zip_file_name = (
    #         f"/tmp/collection_{collection_id}_" f"{time.time_ns() // 1000000}.zip"
    #     )
    #     subprocess.run(["zip", zip_file_name, *temp_paths], check=True)

    #     # Return the streamed content as a response
    #     return FileResponse(zip_file_name, media_type="application/zip")

    raise HTTPException(
        status_code=500,
        detail="Nendo error: Environment Not implemented",
    )

@router.post("/audio/download/tracks", name="tracks:download")
def download_tracks(
    request: Request,
    track_ids: List = Body(...),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    if track_ids is None or len(track_ids) == 0:
        raise HTTPException(status_code=400, detail="track IDs are required")

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    track_paths = assets_handler.get_tracks_audio_paths(track_ids)
    if track_paths is None:
        raise HTTPException(status_code=404, detail="Collection is empty")

    zip_file_name = os.path.join(
        "/tmp/",
        f"tracks_{time.time_ns() // 1000000}.zip",
    )
    files_str = " ".join(track_paths)
    subprocess.run(f"zip {zip_file_name} {files_str}", check=True, shell=True)

    headers = {
        "Content-Disposition": f'attachment; filename="{os.path.basename(zip_file_name)}"',
    }
    return FileResponse(zip_file_name, headers=headers, media_type="application/zip")

@router.get("/image/{image_file_name}", name="image:get")
async def serve_image_asset(
    image_file_name: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: Optional[User] = Depends(fastapi_users.current_user(optional=True)),
):
    if image_file_name is None or image_file_name == "":
        raise HTTPException(status_code=400, detail="image_file_name is required")

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    # if config.get_settings().environment == Environment.LOCAL:
    filepath = assets_handler.get_image_path(image_file_name)
    if filepath is None:
        raise HTTPException(status_code=404, detail="Track not found")

    return FileResponse(
        filepath,
        media_type=f"image/{os.path.splitext(filepath)[1][1:]}",
    )

@router.get("/info", name="info:get")
async def get_asset_info(
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)

    # if config.get_settings().environment == Environment.LOCAL:
    space_available = assets_handler.get_user_storage_size(str(user.id))
    space_used = assets_handler.get_user_storage_used(str(user.id))
    num_tracks = assets_handler.get_user_num_tracks(str(user.id))

    returned_info = {
        "space_used": space_used,
        "space_available": space_available,
        "num_tracks": num_tracks,
    }

    return NendoHTTPResponse(data=returned_info, has_next=False, cursor=0)
