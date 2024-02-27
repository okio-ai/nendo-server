# -*- encoding: utf-8 -*-
"""Routes used by the Mashuper app."""
import json
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from auth.auth_db import User
from auth.auth_users import fastapi_users
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory
from pydantic import BaseModel
from sqlalchemy import and_

from .model import Channel, Scene, SceneDB

router = APIRouter()

class MusicParams(BaseModel):
    model: str
    prompts: List[str]
    generation_type: str  # 'unconditional', 'conditional' or 'melody'
    tempo: int
    duration: int = 4
    track_id: str = None
    num_samples: int = 1

@router.post("/scenes")
async def create_scene(
    request: Request,
    scene: Dict = Body(...),
    user: User = Depends(fastapi_users.current_user()),
):
    """Create a new scene."""
    try:
        scene.update({"user_id": user.id})
        scene_obj = Scene(**scene)
        scene_id = 0
        # Add and commit the new scene to the database
        with request.app.state.db.session_scope() as session:
            # Convert the Pydantic model to a dict, then to a SceneDB SQLAlchemy object
            scene_model = SceneDB(**scene_obj.dict())
            session.add(scene_model)
            session.commit()
            session.refresh(scene_model)
            scene_id = scene_model.id

        return {"scene_id": scene_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/scenes/{scene_id}")
async def update_scene(
    request: Request,
    scene_id: int,
    scene: Dict = Body(...),
    user: User = Depends(fastapi_users.current_user()),
):
    """Update an existing scene."""
    try:
        scene.update({"user_id": user.id})
        scene_obj = Scene(**scene)
        with request.app.state.db.session_scope() as session:
            scene_db = (
                session.query(SceneDB)
                .filter(
                    and_(
                        SceneDB.id == scene_id,
                        SceneDB.user_id == user.id,
                    ),
                )
                .first()
            )
            if scene_db is None:
                raise HTTPException(status_code=404, detail="Scene not found")
            scene_model = SceneDB(**scene_obj.dict())
            scene_db.name = scene_model.name
            scene_db.author = scene_model.author
            scene_db.channels = scene_model.channels
            scene_db.tempo = scene_model.tempo
            session.commit()

        return {"message": f"Scene {scene_id} has been updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/scenes/{scene_id}")
async def get_scene(
    request: Request,
    scene_id: int,
    user: User = Depends(fastapi_users.current_user()),
):
    """Get a scene from the DB."""
    # Query the database for the scene
    with request.app.state.db.session_scope() as session:
        scene_model = (
            session.query(SceneDB)
            .filter(
                and_(
                    SceneDB.id == scene_id,
                    SceneDB.user_id == user.id,
                ),
            )
            .first()
        )

        if scene_model is None:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Deserialize the JSON field 'channels' in the scene
        # and create a Pydantic Scene object for the response
        scene_data = scene_model.__dict__
        scene_data["channels"] = Channel.model_validate(
            json.dumps(scene_data["channels"]),
        )

        return Scene(**scene_data)


@router.get("/scenes")
async def get_scenes(
    request: Request,
    user: User = Depends(fastapi_users.current_user()),
):
    with request.app.state.db.session_scope() as session:
        # Query from database
        result = session.query(SceneDB).filter(SceneDB.user_id == user.id).all()

        # Deserialize JSON to Scene object and add to list
        return [Scene.model_validate(r.__dict__) for r in result]


@router.delete("/scenes/{scene_id}")
async def delete_scene(
    request: Request,
    scene_id: int,
    user: User = Depends(fastapi_users.current_user()),
):
    """Delete a scene."""
    # Query the database for the scene
    with request.app.state.db.session_scope() as session:
        scene_model = (
            session.query(SceneDB)
            .filter(
                and_(
                    SceneDB.id == scene_id,
                    SceneDB.user_id == user.id,
                ),
            )
            .first()
        )

        if scene_model is None:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Delete the scene from the database
        session.delete(scene_model)
        session.commit()

    return {"message": f"Scene {scene_id} has been deleted."}


@router.get("/randomfile")
async def get_random_file(
    request: Request,
    filters: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    songbpm: Optional[str] = Query(None),
    duration_min: Optional[float] = Query(None),
    duration_max: Optional[float] = Query(None),
    collection_id: Optional[str] = Query(None),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    filter_list = filters.split(",") if filters else None
    song_bpm = int(songbpm) if songbpm else None
    # key_strings = key.split(",") if key else None
    # target_duration = (float(duration_min), float(
    #     duration_max)) if duration_min and duration_max else None

    matching_tracks = request.app.state.nendo_instance.library.filter_tracks(
        # filters={
        #    "key": key_strings,
        #    "duration": target_duration,
        #    # "tempo": target_bpm,
        # },
        track_type="loop",
        search_meta=filter_list,
        limit=1,
        order_by="random",
        user_id=str(user.id),
        collection_id=collection_id,
    )

    if len(matching_tracks) > 0:
        track = matching_tracks[0]

        if "title" in track.meta and track.meta["title"] is not None:
            track_title = track.meta["title"]
        else:
            track_title = track.resource.meta["original_filename"]

        # check if track already has the right bpm
        track_tempo = track.get_plugin_value(
            key="tempo",
            user_id=str(user.id),
        )
        track_tempo = int(float(track_tempo)) if track_tempo is not None else 0
        if track_tempo == song_bpm:
            return {"track_title": track_title, "track_id": str(track.id)}
        # check if track has already been quantized to the right bpm
        related_tracks = track.get_related_tracks(user_id=str(user.id))
        for rt in related_tracks:
            rt_tempo = rt.get_plugin_value(
                key="tempo",
                user_id=str(user.id),
            )
            rt_tempo = int(float(rt_tempo)) if rt_tempo is not None else 0
            if rt_tempo == song_bpm:
                return {"track_title": track_title, "track_id": str(rt.id)}

        # enqueue quantization job
        actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)
        assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
        if assets_handler.user_reached_storage_limit(str(user.id)):
            raise HTTPException(status_code=507, detail="Storage limit reached")

        try:
            action_id = actions_handler.create_docker_action(
                user_id=str(user.id),
                image="nendo/quantize",
                gpu=False,
                script_path="mashuper/quantize.py",
                plugins=["nendo_plugin_quantize_core"],
                action_name="Quantize",
                container_name="",
                exec_run=False,
                replace_plugin_data=False,
                func_timeout=60,
                target_id=str(track.id),
                target_bpm=song_bpm,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

        return JSONResponse(
            status_code=200,
            content={"track_title": track_title, "action_id": action_id},
        )

    raise HTTPException(status_code=404, detail="No audio files found.")


@router.get("/audio/{track_id}")
async def stream_audio(
    request: Request,
    track_id: str,
    range: Optional[str] = Query(None),
):
    track = request.app.state.nendo_instance.get_track(track_id=track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found.")

    filepath = track.resource.src

    file_size = Path(filepath).stat().st_size
    start, end = 0, file_size - 1
    if range is not None:
        match = re.search(r"(\d+)-(\d*)", range)
        start, end = [
            int(g) if g else start if idx == 0 else end
            for idx, g in enumerate(match.groups())
        ]

    def content():
        with open(filepath, "rb") as file:
            file.seek(start)
            yield file.read(end - start + 1)

    response = StreamingResponse(content(), media_type="audio/x-wav")
    response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response.headers[
        "Content-Disposition"
    ] = f'inline; filename="{urllib.parse.quote(track.resource.file_name)}"'

    return response


@router.get("/quantize/{track_id}")
async def get_quantized(
    request: Request,
    track_id: str,
    songbpm: int,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Route used to quantize a target track."""
    target_track = request.app.state.nendo_instance.library.get_track(
        track_id=track_id,
        user_id=str(user.id),
    )
    if target_track is None:
        raise HTTPException(status_code=404, detail="Track not found.")
    # check if track already has the right bpm
    track_tempo = target_track.get_plugin_value(
        key="tempo",
        user_id=str(user.id),
    )
    track_tempo = int(float(track_tempo)) if track_tempo is not None else 0
    if track_tempo == songbpm:
        return {
            "track_title": (
                target_track.get_meta("title") or
                target_track.resource.meta["original_filename"]
            ),
            "track_id": str(target_track.id),
        }

    # try not to re-quantize tracks
    if target_track.track_type != "loop":
        related_tracks = target_track.get_related_tracks(
            direction="from", user_id=str(user.id),
        )
        for rt in related_tracks:
            track_tempo = rt.get_plugin_value(
                key="tempo",
                user_id=str(user.id),
            )
            track_tempo = int(float(track_tempo)) if track_tempo is not None else 0
            if track_tempo == songbpm:
                return {
                    "track_title": (
                        rt.get_meta("title") or
                        rt.resource.meta["original_filename"]
                    ),
                    "track_id": str(rt.id),
                }
            if rt.track_type == "loop":
                rrts = rt.get_related_tracks(
                    direction="to", user_id=str(user.id),
                )
                for rrt in rrts:
                    track_tempo = rrt.get_plugin_value(
                        key="tempo",
                        user_id=str(user.id),
                    )
                    track_tempo = int(float(track_tempo)) if track_tempo is not None else 0
                    if track_tempo == songbpm:
                        return {
                            "track_title": (
                                rrt.get_meta("title") or
                                rrt.resource.meta["original_filename"]
                            ),
                            "track_id": str(rrt.id),
                        }
                target_track = rt

    # check if storage limit has been reached
    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
    if assets_handler.user_reached_storage_limit(str(user.id)):
        raise HTTPException(status_code=507, detail="Storage limit reached")

    # enqueue quantization job
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    try:
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/quantize",
            gpu=False,
            script_path="mashuper/quantize.py",
            plugins=["nendo_plugin_quantize_core"],
            action_name="Quantize",
            container_name="",
            exec_run=False,
            replace_plugin_data=False,
            func_timeout=60,
            target_id=str(target_track.id),
            target_bpm=songbpm,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={
            "track_title": (
                target_track.get_meta("title") or
                target_track.resource.meta["original_filename"]
            ),
            "action_id": action_id,
        },
    )
    
@router.post("/generate")
async def generate_track(
    request: Request,
    music_params: MusicParams,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user())):
    """Generate a track with musicgen."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
    if assets_handler.user_reached_storage_limit(str(user.id)):
        raise HTTPException(status_code=507, detail="Storage limit reached")

    try:
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/musicgen",
            gpu=True,
            script_path="mashuper/generate.py",
            plugins=[
                "nendo_plugin_musicgen",
                "nendo_plugin_loopify",
            ],
            action_name="Mashuper Generate",
            container_name="",
            exec_run=False,
            replace_plugin_data=False,
            func_timeout=0,
            target_id="",
            prompt=music_params.prompts[0],
            temperature=1.0, # TODO make configurable?
            cfg_coef=3.5, # TODO make configurable?
            bpm=int(music_params.tempo),
            duration=int(music_params.duration),
            # add_to_collection_id=add_to_collection_id,
            # n_samples=music_params.num_samples,
            # key=params["key"],
            # scale=params["scale"],
            # model=music_params.generation_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={"status": "success", "action_id": action_id},
    )
    