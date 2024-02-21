# -*- encoding: utf-8 -*-
"""Verification routes."""
import json

import httpx
from api.response import NendoHTTPResponse
from config import Settings
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/{token}", name="verify email")
async def verify_email(token: str):
    """Verify the user's email address."""
    settings = Settings()

    try:
        url = settings.email_verify_url_internal
        payload = json.dumps({"token": token})
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            await client.post(url, headers=headers, data=payload)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nendo error: {e}") from e

    return NendoHTTPResponse(data="success")
