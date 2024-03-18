# -*- encoding: utf-8 -*-
"""Musicgeneration app."""
# ruff: noqa: BLE001, T201, I001
import argparse
import gc
from pathlib import Path
import os
import uuid
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
    parser = argparse.ArgumentParser(description="Music Generation.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)

    parser.add_argument("--temperature", type=float, required=False, default=1.0)
    parser.add_argument("--cfg_coef", type=float, required=False, default=3.5)
    parser.add_argument("--prompt", type=str, required=True)

    # TODO these currently don't get set by the frontend, will be set in the future
    parser.add_argument("--n_samples", type=int, required=False, default=5)
    parser.add_argument("--bpm", type=int, required=False, default=120)
    parser.add_argument("--key", type=str, required=False, default="C")
    parser.add_argument("--scale", type=str, required=False, default="major")
    parser.add_argument("--model", type=str, required=False, default="facebook/musicgen-stereo-medium")
    parser.add_argument("--duration", type=int, required=False, default=15)
    parser.add_argument("--seed", type=int, required=False, default=-1)

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

    job.meta["progress"] = f"Generating {args.n_samples} Tracks"
    job.save_meta()

    if "local" in args.model:
        model_path = os.path.join(
            Path.home(), ".cache/nendo/models/musicgen/", args.user_id,
            args.model.split("//")[1],
        )
        if not os.path.exists(model_path):
            job.meta["errors"].append(f"Model {args.model} not found")
            job.save_meta()
            return
    else:
        model_path = args.model

    generations = nd.plugins.musicgen(
        n_samples=args.n_samples,
        prompt=args.prompt,
        bpm=args.bpm,
        key=args.key,
        scale=args.scale,
        model=model_path,
        duration=args.duration,
        temperature=args.temperature,
        cfg_coef=args.cfg_coef,
        seed=args.seed,
    )
    free_memory(nd.plugins.musicgen.plugin_instance)

    collection_id = args.add_to_collection_id
    if collection_id is None:
        tmp_coll = nd.library.add_collection(
            name="Musicgen Generated",
            user_id=args.user_id,
            track_ids=[],
        )
        collection_id = tmp_coll.id

    for i, track in enumerate(generations):
        job.meta["progress"] = f"Post-processing generated Track {i + 1}/{len(generations)}"
        job.save_meta()
        track.set_meta({
            "title": f"{args.prompt} - {i+1}",
        })
        finish_track(track, collection_id)

    if args.add_to_collection_id is not None and len(args.add_to_collection_id) > 0:
        print("collection/" + args.add_to_collection_id)
    else:
        print(generations[-1].id)


if __name__ == "__main__":
    main()
