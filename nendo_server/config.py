# -*- encoding: utf-8 -*-
"""The Nendo Server configuration."""
from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Environment(Enum):
    """Environment in which the server is running."""
    TEST = "test"
    LOCAL = "local"
    REMOTE = "remote"


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(base_dir, "VERSION")) as version_file:
    version = version_file.read().strip()


class Settings(BaseSettings):
    """The Nendo Serer config class."""

    environment: Environment = Field(default=Environment.REMOTE)
    log_level: str = Field(default="warning")
    server_name: str = Field(default="Nendo server")
    base_dir: str = Field(default=base_dir)
    version: str = Field(default=version)
    plugins: List[str] = Field(default_factory=list)
    use_gpu: bool = Field(default=True)
    docker_network_name: str = Field(default="nendo-internal")
    num_user_cpu_workers: int = Field(default=3)
    num_gpu_workers: int = Field(default=1)
    user_storage_size: int = Field(default=-1)

    """
    Google OAuth integration
    """

    secret: str = Field(default="DUMMY_SECRET")
    client_id: str = Field(default="DUMMY_ID")
    client_secret: str = Field(default="DUMMY_CLIENT_SECRET")
    # redirect to the frontend which intercepts the callback with the token
    redirect_url: str = Field(default="http://localhost/callback")

    """
    Google Cloud Storage
    """

    google_storage_credentials: str = Field(default=r"{}")

    """
    AUTH
    """

    auth_database_connection: str = Field(
        default="sqlite+aiosqlite:///./auth_db/auth_db.db",
    )
    jwt_token_expiry_seconds: int = Field(default=36000)

    """
    POSTGRES SERVER CONFIG
    """

    postgres_user: str = Field(default="nendo")
    postgres_password: str = Field(default="nendo")
    postgres_host: str = Field(default="localhost:5432")
    postgres_db: str = Field(default="nendo")

    """
    REDIS SERVER CONFIG
    """

    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_user: str = Field(default="")
    redis_password: str = Field(default="")

    """
    CONTAINER ENVIRONMENT VARS
    """

    container_log_level: str = Field(default="warning")
    container_library_plugin: str = Field(default="nendo_plugin_library_postgres")
    container_library_path: str = Field(default="/home/nendo/nendo_library")
    container_host_base_path: str = Field(default="./")
    container_host_apps_path: str = Field(default="./nendo_server/apps")
    container_postgres_host: str = Field(default="postgres:5432")
    container_postgres_user: str = Field(default="nendo")
    container_postgres_password: str = Field(default="nendo")
    container_postgres_db: str = Field(default="nendo")

    """
    EMAILER
    """

    email_from_address: str = Field(default="")
    mailgun_api_key: str = Field(default="")

    email_verify_url_internal: str = Field(
        default="http://127.0.0.1:8000/api/auth/verify",
    )  # triggers the sending of the email with the token

    email_verify_url_public_ui: str = Field(
        default="http://localhost:5173/verified/",
    )  # ui page that will relay the token to the backend

    password_reset_url_public: str = Field(
        default="http://localhost:5173/setpassword/",
    )  # send the reset password token to UI where the user can enter a new password


@lru_cache()
def get_settings() -> Settings:
    """Return the server configuration, cached."""
    return Settings()
