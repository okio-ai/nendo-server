# -*- encoding: utf-8 -*-
"""Nendo API Server middleware to extract user auth information."""
from auth.nendo_auth import NendoAuth
from fastapi import HTTPException, Request


async def extract_auth(request: Request):
    """Extract user authentication information."""
    try:
        # inspect Authorization header and inject user into request context
        request = NendoAuth().extract_user(request)

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
