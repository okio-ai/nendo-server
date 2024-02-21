# -*- encoding: utf-8 -*-
"""Routes used by the Mashuper app."""
from typing import Dict

from auth.auth_db import User
from auth.auth_users import fastapi_users
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory

router = APIRouter()


@router.post("/{target_id}")
async def run_getpage(
    target_id: str,
    replace: bool = Query(True),
    params: Dict = Body(...),
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Crawl a webpage, summarize it and create an embedding of it."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    try:
        action_id = actions_handler.create_docker_action(
            user_id=str(user.id),
            image="nendo/getpage",
            gpu=False,
            script_path="getpage/getpage.py",
            plugins=[
                "nendo_plugin_embed_uae",
                "nendo_plugin_textgen",
            ],
            action_name="Get Page",
            container_name="",
            exec_run=False,
            replace_plugin_data=replace,
            env={
              "embedding_plugin": "nendo_plugin_embed_uae",
            },
            func_timeout=0,
            target_id=target_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return JSONResponse(
        status_code=200,
        content={"status": "success", "action_id": action_id},
    )
