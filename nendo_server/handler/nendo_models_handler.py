from abc import ABC
import os
from typing import List
from pathlib import Path

from nendo import Nendo
import logging


class ModelsHandler(ABC):
    nendo_instance: Nendo = None
    logger: logging.Logger = None

    def __init__(self, nendo_instance, logger):
        self.nendo_instance = nendo_instance
        self.logger = logger

    def scan_available_models(self, user_id: str) -> List[str]:
        """Scan the available models from the users local model directory."""
        models = []

        base_path = os.path.join(
            Path.home(), ".cache/nendo/models/musicgen/", user_id
        )
        if not os.path.exists(base_path):
            return models

        models = [model for model in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, model))]
        return models