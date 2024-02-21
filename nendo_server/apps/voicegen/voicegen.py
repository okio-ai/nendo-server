# -*- encoding: utf-8 -*-
"""Musicgeneration app."""
# ruff: noqa: BLE001, T201, I001
import argparse
import gc
import os
import uuid
import sys
from typing import Any

import librosa
import matplotlib.pyplot as plt
import numpy as np
import redis
import torch
from nendo import Nendo
from nendo import NendoTrack, NendoResource
from rq.job import Job


def free_memory(to_delete: Any):
    del to_delete
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


def finish_track(track: NendoTrack, add_to_collection_id: str):
    nd = Nendo()
    if add_to_collection_id is not None and len(add_to_collection_id) > 0:
        nd.add_track_to_collection(
            track_id=track.id,
            collection_id=add_to_collection_id,
        )
    # compute spectrogram
    # TODO turn into a plugin
    y, sr = librosa.load(track.resource.src, sr=None)
    mel_spect = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=256)
    log_mel_spect = librosa.power_to_db(mel_spect, ref=np.max)
    plt.figure(figsize=(10, 4))
    librosa.display.specshow(log_mel_spect, sr=sr, x_axis="time", y_axis="mel")
    plt.axis("off")
    plt.xticks([]), plt.yticks([])
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    image_file_path = os.path.join(
        nd.config.library_path,
        "images/",
        f"{uuid.uuid4()}.png",
    )
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


def main():
    parser = argparse.ArgumentParser(description="Voice Generation.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)
    parser.add_argument("--voice", type=str, required=True)
    parser.add_argument("--prompt", type=str, required=True)

    args = parser.parse_args()
    nd = Nendo()
    redis_conn = redis.Redis(
        host="redis",
        port=6379,
        db=0,
    )
    job = Job.fetch(args.job_id, connection=redis_conn)
    job.meta["errors"] = []
    job.save_meta()

    job.meta["progress"] = "Generating Text to speech"
    job.save_meta()
    generation = nd.plugins.voicegen_styletts2(
        text=args.prompt,
        voice=args.voice,
    )
    free_memory(nd.plugins.voicegen_styletts2.plugin_instance)

    collection_id = args.add_to_collection_id
    if collection_id is None:
        tmp_coll = nd.library.add_collection(
            name="Generated Voice",
            user_id=args.user_id,
            track_ids=[],
        )
        collection_id = tmp_coll.id
    generation.set_meta({
        "title": "Generated Speech",
    })
    finish_track(generation, collection_id)
    sys.stdout.flush()
    print(generation.id)


if __name__ == "__main__":
    main()
