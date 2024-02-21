# -*- encoding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import config
import uvicorn
from api.router_api import api_router
from auth.auth_db import close_db, create_db_and_tables, get_active_user_ids
from auth.router_auth import auth_router
from db import PostgresDB
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from handler.nendo_handler_factory import (
    LocalNendoHandlerFactory,
    NendoHandlerFactory,
    RemoteNendoHandlerFactory,
)
from logger.nendo_logger import create_logger
from nendo import Nendo
from redis import Redis
from worker.worker_manager import LocalWorkerManager, RemoteWorkerManager

LOCK_FILE = "/tmp/rq_init.lock"

def is_master_process() -> bool:
    """Check if this is the master process by attempting to create a lock file."""
    try:
        # Try to create the lock file without overwriting it if it exists
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False

# create app
def create_app():
    # configure app
    server_config = config.get_settings()
    app = FastAPI(title=server_config.server_name)

    # load all app routes
    project_root = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(project_root)
    modules_dir = os.path.join(project_root, "apps")
    for subdir in os.listdir(modules_dir):
        sub_path = os.path.join(modules_dir, subdir)
        if os.path.isdir(sub_path):
            app_routes = importlib.import_module(f"apps.{subdir}.routes")
            for attribute_name in dir(app_routes):
                attribute = getattr(app_routes, attribute_name)
                if isinstance(attribute, APIRouter):
                    api_router.include_router(
                        attribute, prefix=f"/{subdir}", tags=[subdir],
                    )

    # api router
    app.include_router(api_router, prefix="/api")
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(api_router, prefix="/api/latest")

    # auth router
    app.include_router(auth_router, prefix="/api")

    origins = [
        "*",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        logger = create_logger(server_config.log_level)

        try:
            app.state.logger = logger
            app.state.config = server_config

            app.state.logger.info(
                f'SERVER STARTING in "{server_config.environment}"',
            )

            if server_config.environment == config.Environment.LOCAL:
                app.state.db = PostgresDB(logger=logger)

                app.state.redis = Redis(
                    host=server_config.redis_host,
                    port=server_config.redis_port,
                    db=server_config.redis_db,
                    username=server_config.redis_user,
                    password=server_config.redis_password,
                )

                app.state.worker_manager = LocalWorkerManager(
                    server_config=server_config,
                    logger=logger,
                    redis=app.state.redis,
                )

                app.state.nendo_instance = Nendo(
                    logger=logger,
                )

                app.dependency_overrides[
                    NendoHandlerFactory
                ] = lambda: LocalNendoHandlerFactory(app.state)

            if server_config.environment == config.Environment.REMOTE:
                app.state.db = PostgresDB(logger=logger)

                app.state.redis = Redis(
                    host=server_config.redis_host,
                    port=server_config.redis_port,
                    db=server_config.redis_db,
                    username=server_config.redis_user,
                    password=server_config.redis_password,
                )

                app.state.worker_manager = RemoteWorkerManager(
                    server_config=server_config,
                    logger=logger,
                    redis=app.state.redis,
                )

                # nendo_config = NendoConfig()
                # nendo_config.google_storage_credentials = (
                #     server_config.google_storage_credentials
                # )
                # nendo_config.storage_location = "remote"

                app.state.nendo_instance = Nendo(
                    logger=logger,
                )

                app.dependency_overrides[
                    NendoHandlerFactory
                ] = lambda: RemoteNendoHandlerFactory(app.state)

            # load app models
            for subdir in os.listdir(modules_dir):
                sub_path = os.path.join(modules_dir, subdir)
                if os.path.isdir(sub_path):
                    module_name = f"apps.{subdir}.model"
                    # Check if the model.py file exists in the directory
                    model_path = os.path.join(sub_path, "model.py")
                    if os.path.exists(model_path):
                        # Check if the module can be imported
                        spec = importlib.util.find_spec(module_name)
                        if spec is not None:
                            app_model = importlib.import_module(module_name)
                            for attribute_name in dir(app_model):
                                if attribute_name == "init":
                                    init_func = getattr(app_model, attribute_name)
                                    init_func(app.state.db.db)

            # create auth tables
            await create_db_and_tables()

            # create images dir
            images_path = os.path.join(
                app.state.nendo_instance.config.library_path,
                "images/",
            )
            os.makedirs(images_path, exist_ok=True)

            # initialize queues and workers
            if is_master_process():
                user_ids = await get_active_user_ids()
                app.state.worker_manager.init_queues_and_workers(user_ids)

        except Exception as e:
            logger.error(f"Nendo startup error: {e}")
            sys.exit()

    return app

    @app.on_event("shutdown")
    async def shutdown_event():
        if is_master_process():
            # Cleanup, e.g., remove the lock file
            os.remove(LOCK_FILE)
        close_db_connections()
    return None


app = create_app()


def close_db_connections():
    try:
        app.state.db._disconnect()
    except Exception as e:
        app.state.logger(
            f"ERROR attempting to close app.state.db._disconnect(): {e}",
        )

    try:
        app.state.nendo_instance.library._disconnect()
    except Exception as e:
        app.state.logger(
            "ERROR attempting to close "
            f"app.state.nendo_instance.library._disconnect(): {e}",
        )

    try:
        close_db()
    except Exception as e:
        app.state.logger(
            f"ERROR attempting to close the authdb close_db(): {e}",
        )


app.mount(
    "/assets",
    StaticFiles(directory=Path(__file__).parent / "static/dist/assets"),
    name="assets",
)

if __name__ == "__main__":
    settings = config.get_settings()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level=settings.log_level,
        log_config=os.path.join(settings.base_dir, "log_conf.yaml"),
    )
