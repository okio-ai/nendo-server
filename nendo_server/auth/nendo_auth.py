# -*- encoding: utf-8 -*-
"""Nendo server authentication module."""
import uuid

from fastapi import HTTPException, Request
from nendo.schema import NendoUser


class NendoAuth:
    """Base class for authentication."""

    def extract_user(self, request: Request) -> Request:
        """Exctract a user from a request."""
        authorization_header = request.headers.get("Authorization")

        if not authorization_header:
            request.app.state.logger.debug(
                f"Authorization header not found in request: {request}",
            )
            raise HTTPException(
                status_code=401,
                detail="Authorization header not found in request",
            )

        request.app.state.logger.debug(f"Authorization for request: {request}")

        # if not authorization_header:
        # TODO this is a temporary universal default user for local,
        # we need to implement a proper auth system
        default_user = NendoUser(
            id=uuid.UUID("9167708d-2bdc-4410-a0a9-bc06b21d44e5"),
            name="nendo",
            password="",
            email="",
            verified=True,
        )

        request.state.user = default_user
        request.app.state.logger.debug(
            f"Injected default user into request: {request.state.user}",
        )

        return request
