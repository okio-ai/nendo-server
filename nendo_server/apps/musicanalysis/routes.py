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
async def run_musicanalysis(
    target_id: Optional[str] = Query(None),
    replace: bool = Query(False),
    add_to_collection_id: str = Query(""),
    params: Dict = Body(...),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Process a track with musicanalysis."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    try:
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/musicanalysis",
            gpu=True,
            script_path="musicanalysis/musicanalysis.py",
            plugins=[
                "nendo_plugin_embed_clap",
                "nendo_plugin_classify_core",
                "nendo_plugin_caption_lpmusiccaps",
            ],
            action_name="Music Analysis",
            container_name="",
            exec_run=False,
            replace_plugin_data=replace,
            run_without_target=False,
            max_track_duration=420.,  # 7 minutes per track
            max_chunk_duration=3600., # 60 minutes per chunk
            action_timeout=None,
            track_processing_timeout=None,
            target_id=target_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={"status": "success", "action_id": action_id},
    )
