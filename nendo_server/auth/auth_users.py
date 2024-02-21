# -*- encoding: utf-8 -*-
"""Nendo API Server user manager."""
import time
import uuid
from typing import Optional

from auth.auth_db import User, get_user_db
from config import Settings
from emailer.nendo_emailer import NendoEmailer
from fastapi import Depends, HTTPException, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    settings = Settings()
    reset_password_token_secret = settings.secret
    verification_token_secret = settings.secret

    async def create(
        self,
        user_create: schemas.UC,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> models.UP:
        # THIS CODE IS FOR CLOSED ALPHA ONLY
        invite_code = request.query_params.get("invite_code")

        unclaimed_codes = request.app.state.db.get_unclaimed_invite_codes()
        unclaimed_codes_list = [item["invite_code"] for item in unclaimed_codes]

        if invite_code not in unclaimed_codes_list:
            raise HTTPException(status_code=400, detail="Invalid Invite Code.")

        request.app.state.db.claim_invite_code(invite_code, user_create.email)
        # THIS CODE IS FOR CLOSED ALPHA ONLY

        # create user in DB
        return await super().create(user_create=user_create, safe=safe, request=request)

    async def oauth_callback(
        self: "BaseUserManager[models.UOAP, models.ID]",
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> models.UOAP:
        return await super().oauth_callback(
            oauth_name=oauth_name,
            access_token=access_token,
            account_id=account_id,
            account_email=account_email,
            expires_at=expires_at,
            refresh_token=refresh_token,
            request=request,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
        )

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        request.app.state.logger.info(f"User {user.id} has registered.")
        request.app.state.nendo_instance.library.storage_driver.init_storage_for_user(
            str(user.id),
        )
        # create user queues and workers
        request.app.state.worker_manager.get_user_queues(str(user.id))
        request.app.state.worker_manager.spawn_cpu_workers(str(user.id))
        if self.settings.use_gpu:
            # wait for cpu workers to spawn
            # (needed bc they are used to find user_ids by spawn_gpu_workers)
            time.sleep(2)
            request.app.state.worker_manager.spawn_gpu_workers()

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        request.app.state.logger.info(f"User {user.id} has logged in.")
        try:
            request.app.state.nendo_instance.library.storage_driver.init_storage_for_user(
                str(user.id),
            )
        except Exception as e:
            request.app.state.logger.error(
                f"Error creating bucket for user {user.id}: {e}",
            )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None,
    ):
        target_email = user.email

        subject = "Reset your password"
        body = (
            "Hello, please follow this link to reset your password: "
            + self.settings.password_reset_url_public
            + "/"
            + token
            + "/"
        )

        emailer = NendoEmailer(request.app.state.logger, self.settings)
        emailer.send_email(target_email, subject, body)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None,
    ):
        target_email = user.email

        subject = "Confirm your email"
        body = (
            "Hello, please follow this link to confirm your email: "
            + self.settings.email_verify_url_public_ui
            + "/"
            + token
            + "/"
        )

        emailer = NendoEmailer(request.app.state.logger, self.settings)
        emailer.send_email(target_email, subject, body)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    settings = Settings()
    return JWTStrategy(
        secret=settings.secret, lifetime_seconds=settings.jwt_token_expiry_seconds,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
