from api.response import NendoHTTPResponse
from api.utils import APIRouter
from auth.auth_db import User
from auth.auth_users import fastapi_users
from fastapi import Depends, HTTPException
from handler.nendo_handler_factory import HandlerType, NendoHandlerFactory
from handler.nendo_models_handler import ModelsHandler

router = APIRouter()

@router.options("/", name="models:options", response_model=NendoHTTPResponse)
async def get_models_options(
        user: User = Depends(fastapi_users.current_user()),
        handler_factory: NendoHandlerFactory = Depends(NendoHandlerFactory),
):
    models_handler: ModelsHandler = handler_factory.create(handler_type=HandlerType.MODELS)

    try:
        options = models_handler.scan_available_models(str(user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e
    return NendoHTTPResponse(data=options, has_next=False, cursor=0)

