# -*- encoding: utf-8 -*-
"""Routes used by the Mashuper app."""
from typing import Dict, Optional

from auth.auth_db import User
from auth.auth_users import fastapi_users
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory

router = APIRouter()


@router.post("")
async def run_musicgen_training(
    target_id: Optional[str] = Query(None),
    replace: bool = Query(False),
    add_to_collection_id: str = Query(""),
    params: Dict = Body(...),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Train a model based on MusicGen with a collection."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
    if assets_handler.user_reached_storage_limit(str(user.id)):
        raise HTTPException(status_code=507, detail="Storage limit reached")

    try:
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/musicgentrain",
            gpu=True,
            script_path="musicgentrain/musicgentrain.py",
            plugins=[
                "nendo_plugin_musicgen",
                "nendo_plugin_stemify_demucs",
                "nendo_plugin_classify_core",
            ],
            action_name="MusicGen training",
            container_name="",
            exec_run=False,
            replace_plugin_data=replace,
            run_without_target=True,
            max_track_duration=-1.,
            max_chunk_duration=-1.,
            action_timeout=None,
            track_processing_timeout=None,
            target_id=target_id,
            prompt=params["musicgentrain"]["prompt"],
            model=params["musicgentrain"]["model"],
            remove_vocals=params["musicgentrain"]["remove_vocals"],
            batch_size=params["musicgentrain"]["batch_size"],
            epochs=params["musicgentrain"]["epochs"],
            lr=params["musicgentrain"]["lr"],
            add_to_collection_id=add_to_collection_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={"status": "success", "action_id": action_id},
    )
