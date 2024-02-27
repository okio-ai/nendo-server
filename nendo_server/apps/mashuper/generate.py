# -*- encoding: utf-8 -*-
"""Generator action used by the Mashuper app."""
# ruff: noqa: ARG001, T201, D103

import argparse
import gc
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


def generate(
    job_id: str,
    target_id: str,
    target_bpm: int = 120,
) -> None:
    nd = Nendo()
    track = nd.get_track(target_id)
    q_track = track.process("nendo_plugin_quantize_core", bpm=target_bpm)
    # copy classified track info
    if track.has_meta("original_filename"):
        q_track.set_meta({"original_filename" : track.meta["original_filename"]})
    for pd in track.get_plugin_data(plugin_name="nendo_plugin_classify_core"):
        # don't copy tempo (has been changed by quantization)
        if pd.key != "tempo":
            q_track.add_plugin_data(
                plugin_name=pd.plugin_name,
                plugin_version=pd.plugin_version,
                key=pd.key,
                value=pd.value,
            )
    print(q_track.id)

def main():
    parser = argparse.ArgumentParser(description="Music Generation.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--temperature", type=float, required=False, default=1.0)
    parser.add_argument("--cfg_coef", type=float, required=False, default=3.5)
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--bpm", type=int, required=False, default=120)
    parser.add_argument("--duration", type=int, required=False, default=4)

    # TODO these currently don't get set by the frontend, will be set in the future
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)
    parser.add_argument("--n_samples", type=int, required=False, default=1)
    parser.add_argument("--key", type=str, required=False, default="C")
    parser.add_argument("--scale", type=str, required=False, default="major")
    parser.add_argument("--model", type=str, required=False, default="facebook/musicgen-stereo-medium")
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

    generations = nd.plugins.musicgen(
        n_samples=args.n_samples,
        prompt=args.prompt,
        bpm=args.bpm,
        key=args.key,
        scale=args.scale,
        model=args.model,
        duration=2 * args.duration, # TODO revise
        temperature=args.temperature,
        cfg_coef=args.cfg_coef,
        seed=args.seed,
    )
    free_memory(nd.plugins.musicgen.plugin_instance)

    # collection_id = args.add_to_collection_id
    # if collection_id is None:
    #     tmp_coll = nd.library.add_collection(
    #         name="Musicgen Generated",
    #         user_id=args.user_id,
    #         track_ids=[],
    #     )
    #     collection_id = tmp_coll.id

    for i, track in enumerate(generations):
        job.meta["progress"] = f"Loopifying generated Track {i + 1}/{len(generations)}"
        loops = track.process(
            "nendo_plugin_loopify",
            n_loops=1,
            beats_per_loop=args.duration,
        )
        job.meta["progress"] = f"Post-processing generated Track {i + 1}/{len(generations)}"
        job.save_meta()
        track.set_meta({
            "title": f"{args.prompt} - {i+1}",
        })
        finish_track(track, None)

    if args.add_to_collection_id is not None and len(args.add_to_collection_id) > 0:
        print("collection/" + args.add_to_collection_id)
    else:
        print(",".join([str(loop.id) for loop in loops]))

if __name__ == "__main__":
    main()
