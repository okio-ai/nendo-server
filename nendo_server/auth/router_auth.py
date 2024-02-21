# -*- encoding: utf-8 -*-
"""Nendo API Server authentication and authorization routes."""
from auth.auth_schema import UserCreate, UserRead, UserUpdate
from auth.auth_users import auth_backend, fastapi_users
from config import Settings
from fastapi import APIRouter
from httpx_oauth.clients.google import GoogleOAuth2

settings = Settings()
auth_router = APIRouter()  # new router for non-prefixed routes

# AUTH ROUTES
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"],
)

auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
auth_router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
auth_router.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

google_oauth_client = GoogleOAuth2(
    settings.client_id,
    settings.client_secret,
    scopes=["openid", "email", "profile"],
)

auth_router.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        settings.secret,
        redirect_url=settings.redirect_url,
        associate_by_email=True,
        is_verified_by_default=True,
    ),
    prefix="/auth/google",
    tags=["auth"],
)
