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
        facebook_models = [
            "facebook/musicgen-small",
            "facebook/musicgen-medium",
            "facebook/musicgen-melody",
            "facebook/musicgen-stereo-small",
            "facebook/musicgen-stereo-medium",
            "facebook/musicgen-stereo-melody",
        ]

        community_models = [
            "pharoAIsanders420/musicgen-stereo-dub",
            "pharoAIsanders420/musicgen-medium-hiphop",
            "pharoAIsanders420/musicgen-small-dnb"
        ]

        models = facebook_models + community_models

        base_path = os.path.join(
            Path.home(), ".cache/nendo/models/musicgen/", user_id
        )
        if not os.path.exists(base_path):
            return models

        for coll_name in os.listdir(base_path):
            if os.path.isdir(os.path.join(base_path, coll_name)):
                for model_name in os.listdir(os.path.join(base_path, coll_name)):
                    models.append(f"local//{coll_name}/{model_name}")

        return models
