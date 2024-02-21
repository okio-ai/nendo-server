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
async def run_polymath(
    target_id: Optional[str] = Query(None),
    replace: bool = Query(False),
    add_to_collection_id: str = Query(""),
    params: Dict = Body(...),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Process a track with polymath."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    assets_handler = handler_factory.create(handler_type=HandlerType.ASSETS)
    if assets_handler.user_reached_storage_limit(str(user.id)):
        raise HTTPException(status_code=507, detail="Storage limit reached")

    try:
        plugins = []
        if params["classify"]["isActive"]:
            plugins.append("nendo_plugin_classify_core")
        if params["quantize"]["isActive"]:
            plugins.append("nendo_plugin_quantize_core")
        if params["stemify"]["isActive"]:
            plugins.append("nendo_plugin_stemify_demucs")
        if params["loopify"]["isActive"]:
            plugins.append("nendo_plugin_loopify")
        if params["embeddings"]["isActive"]:
            plugins.append("nendo_plugin_embed_clap")
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/polymath",
            gpu=True,
            script_path="polymath/polymath.py",
            plugins=plugins,
            action_name="Polymath",
            container_name="",
            exec_run=False,
            replace_plugin_data=replace,
            env={"PYTORCH_NO_CUDA_MEMORY_CACHING": 1},
            func_timeout=0,
            target_id=target_id,
            classify=params["classify"]["isActive"],
            stemify=params["stemify"]["isActive"],
            stem_types=params["stemify"]["stemtype"],
            quantize=params["quantize"]["isActive"],
            quantize_to_bpm=int(params["quantize"]["tempo"]),
            loopify=params["loopify"]["isActive"],
            n_loops=int(params["loopify"]["n_loops"]),
            beats_per_loop=int(params["loopify"]["beats_per_loop"]),
            embed=params["embeddings"]["isActive"],
            add_to_collection_id=add_to_collection_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={"status": "success", "action_id": action_id},
    )
