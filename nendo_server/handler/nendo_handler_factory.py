# -*- encoding: utf-8 -*-
"""Factory for creating handlers."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from handler.nendo_actions_handler import LocalActionsHandler, RemoteActionsHandler
from handler.nendo_assets_handler import LocalAssetsHandler
from handler.nendo_collections_handler import (
    LocalCollectionsHandler,
    RemoteCollectionsHandler,
)
from handler.nendo_tracks_handler import LocalTracksHandler, RemoteTracksHandler

if TYPE_CHECKING:
    from nendo import Nendo


class HandlerType(Enum):
    TRACKS = "tracks"
    USERS = "users"
    ASSETS = "assets"
    ACTIONS = "actions"
    COLLECTIONS = "collections"


class NendoHandlerFactory(ABC):
    def __init__(self, app_state):
        self.nendo_instance: Nendo = app_state.nendo_instance
        self.logger = app_state.logger
        self.db = app_state.db
        self.redis = app_state.redis
        self.config = app_state.config
        self.worker_manager = app_state.worker_manager

    @abstractmethod
    def create(self, handler_type: HandlerType):
        raise NotImplementedError


class LocalNendoHandlerFactory(NendoHandlerFactory):
    def create(self, handler_type: HandlerType):
        if handler_type == HandlerType.TRACKS:
            return LocalTracksHandler(self.nendo_instance, self.logger)
        if handler_type == HandlerType.ASSETS:
            return LocalAssetsHandler(self.nendo_instance, self.config, self.logger)
        if handler_type == HandlerType.ACTIONS:
            return LocalActionsHandler(
                self.nendo_instance.config,
                self.config,
                self.nendo_instance,
                self.logger,
                self.redis,
                self.worker_manager,
            )
        if handler_type == HandlerType.COLLECTIONS:
            return LocalCollectionsHandler(self.nendo_instance, self.logger)

        raise Exception("Unknown handler type: " + str(handler_type))


class RemoteNendoHandlerFactory(NendoHandlerFactory):
    def create(self, handler_type: HandlerType):
        if handler_type == HandlerType.TRACKS:
            return RemoteTracksHandler(self.nendo_instance, self.db, self.logger)
        if handler_type == HandlerType.ASSETS:
            # TODO re-enable GCS support at some point
            # return RemoteAssetsHandler(self.nendo_instance, self.logger)
            return LocalAssetsHandler(self.nendo_instance, self.config, self.logger)
        if handler_type == HandlerType.ACTIONS:
            return RemoteActionsHandler(
                self.nendo_instance.config,
                self.config,
                self.nendo_instance,
                self.logger,
                self.redis,
                self.worker_manager,
            )
        if handler_type == HandlerType.COLLECTIONS:
            return RemoteCollectionsHandler(self.nendo_instance, self.logger)

        raise Exception("Unknown handler type: " + str(handler_type))
