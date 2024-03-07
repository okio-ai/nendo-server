# -*- encoding: utf-8 -*-
"""Central API router."""
from __future__ import annotations

from api.action import router as action_router
from api.asset import router as asset_router
from api.collection import router as collection_router
from api.core import router as core_router
from api.track import router as track_router
from api.verify import router as verify_router
from api.model import router as model_router
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(verify_router, prefix="/verify", tags=["verify"])
api_router.include_router(asset_router, prefix="/assets", tags=["assets"])
api_router.include_router(track_router, prefix="/tracks", tags=["tracks"])
api_router.include_router(model_router, prefix="/models", tags=["models"])
api_router.include_router(
    collection_router,
    prefix="/collections",
    tags=["collections"],
)
api_router.include_router(action_router, prefix="/actions", tags=["actions"])
api_router.include_router(core_router, tags=["core"])
