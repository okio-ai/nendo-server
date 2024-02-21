# -*- encoding: utf-8 -*-
"""Action routes of the Nendo API Server."""
from __future__ import annotations

from typing import TYPE_CHECKING

from api.response import NendoHTTPResponse
from api.utils import APIRouter
from auth.auth_users import fastapi_users
from fastapi import Depends, HTTPException, Response
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory

if TYPE_CHECKING:
    from auth.auth_db import User

router = APIRouter()

# TODO re-enable this if you want to switch from direct action submission
# to a model where actions are registered upon bootup
# @router.options("/", name="actions:options", response_model=NendoHTTPResponse)
# def get_actions_options(
#     handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
#     user: User = Depends(fastapi_users.current_user()),
# ):
#     actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)
#     try:
#         options = actions_handler.get_actions_options(user_id=user.id)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Nendo error: {e}")
#     return NendoHTTPResponse(data=options, has_next=False, cursor=0)


async def set_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


@router.get("/", name="all_user_actions:status", response_model=NendoHTTPResponse)
async def get_all_action_statuses(
    response: Response,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Retrieve all actions and their statuses for a given user."""
    await set_no_cache_headers(response)
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)
    try:
        all_action_statuses = actions_handler.get_all_action_statuses(
            user_id=str(user.id),
        )
    except Exception as e:
        actions_handler.logger.error(e)
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=all_action_statuses, has_next=False, cursor=0)


@router.get("/{action_id}", name="action:status", response_model=NendoHTTPResponse)
async def get_action_status(
    action_id: str,
    response: Response,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Retrieve the status of an action."""
    await set_no_cache_headers(response)

    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)
    try:
        action_status = actions_handler.get_action_status(
            user_id=str(user.id),
            action_id=action_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=action_status, has_next=False, cursor=0)


# TODO creation of actions should be done by the apps themselves
# if you want to implement a generic "action creation route" in the future,
# create a HTTP PUT method for registering actions, then re-enable and adjust below
# @router.post("/", name="action:post", response_model=NendoHTTPResponse)
# def create_action(
#     trigger_action: TriggerActionMethod,
#     handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
#     user: User = Depends(fastapi_users.current_user()),
# ):
#     """Create a new action."""
#     actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

#     try:
#         action_trigger_response = actions_handler.create(
#             trigger_action_method=trigger_action,
#             user_id=user.id,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

#     return NendoHTTPResponse(data=action_trigger_response, has_next=False, cursor=0)


@router.delete("/{action_id}", name="action:abort", response_model=NendoHTTPResponse)
def abort_action(
    action_id: str,
    handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
    user: User = Depends(fastapi_users.current_user()),
):
    """Cancel an action."""
    actions_handler = handler_factory.create(handler_type=HandlerType.ACTIONS)

    try:
        action_trigger_response = actions_handler.abort_action(
            user_id=str(user.id),
            action_id=action_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data=action_trigger_response, has_next=False, cursor=0)
