# -*- encoding: utf-8 -*-
"""Utility functions used by Nendo."""
import json
import os
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from typing import List

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
from nendo import Nendo, NendoResource
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.types import TypeDecorator
from sqlalchemy_json import NestedMutableDict, NestedMutableList


class JSONEncodedDict(TypeDecorator):
    impl = JSON

    def process_bind_param(self, value, dialect):
        return json.dumps(convert(value))

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

def convert(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, (np.matrix, np.ndarray)):
        if obj.size > 4096:
            return None
        return obj.tolist()
    if isinstance(obj, np.float32):
        return float(obj)
    if isinstance(obj, (NestedMutableList, list)):
        return [convert(x) for x in obj]
    if isinstance(obj, (Mapping, NestedMutableDict)):
        return {k: convert(v) for k, v in obj.items()}
    return obj

def create_spectrogram(
    track_ids: List[str],
    n_mels: int = 256,
) -> str:
    # compute and add spectrogram to file
    # TODO turn into a plugin
    nd = Nendo()
    rendered_spectrograms = 0
    for target_id in track_ids:
        image_file_path = os.path.join(
            nd.config.library_path,
            "images/",
            f"{uuid.uuid4()}.png",
        )
        track = nd.get_track(target_id)
        y, sr = librosa.load(track.resource.src, sr=None)

        # Compute the Mel spectrogram
        mel_spect = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mels)

        # Convert to log scale
        log_mel_spect = librosa.power_to_db(mel_spect, ref=np.max)

        # Plot the spectrogram
        plt.figure(figsize=(10, 4))
        librosa.display.specshow(log_mel_spect, sr=sr, x_axis="time", y_axis="mel")

        # Remove axes, legends, and white borders
        plt.axis("off")
        plt.xticks([]), plt.yticks([])  # Remove axis ticks
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        # Save the figure
        plt.savefig(image_file_path, bbox_inches="tight", pad_inches=0)
        plt.close()
        image_resource = NendoResource(
            file_path=os.path.dirname(image_file_path),
            file_name=os.path.basename(image_file_path),
            resource_type="image",
            location="local",
            meta={
                "image_type": "spectrogram",
            },
        )
        track.images = [image_resource.model_dump()]
        track.save()
        rendered_spectrograms += 1
    return (
        f"Successfully rendered {rendered_spectrograms}/{len(track_ids)} "
        "spectrograms"
    )
