# -*- encoding: utf-8 -*-
"""Core API routes."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def read_example():
    return {"message": "This is the nendo API."}


@router.get("/healthz")
async def liveness_check():
    return {"status": "ok"}


@router.get("/readyz")
async def readiness_check():
    # TODO replace with a proper Nendo Library connection check
    if True:  # check_db_connection():
        return {"status": "ok"}
    return {"status": "error"}, 500
