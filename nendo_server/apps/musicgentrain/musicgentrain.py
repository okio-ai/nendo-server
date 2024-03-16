# -*- encoding: utf-8 -*-
"""Musicgeneration app."""
import argparse
import gc
import os
# ruff: noqa: BLE001, T201, I001
import shutil
from pathlib import Path
from typing import Any, Callable, List

import redis
import torch
from nendo import Nendo
from nendo import NendoTrack
from rq.job import Job
from wrapt_timeout_decorator import timeout


def restrict_tf_memory():
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    import tensorflow as tf
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        # Restrict TensorFlow to only allocate 1GB of memory on the first GPU
        try:
            tf.config.set_logical_device_configuration(
                gpus[0],
                [tf.config.LogicalDeviceConfiguration(memory_limit=1024)])
            logical_gpus = tf.config.list_logical_devices("GPU")
            print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
        except RuntimeError as e:
            # Virtual devices must be set before GPUs have been initialized
            print(e)


def free_memory(to_delete: Any):
    del to_delete
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


@timeout(int(os.getenv("TRACK_PROCESSING_TIMEOUT")))
def process_track(
        job: Job,
        progress_info: str,
        track: NendoTrack,
        func: Callable,
        **kwargs: Any,
):
    try:
        job.meta["progress"] = progress_info
        job.save_meta()
        func(track=track, **kwargs)
    except Exception as e:
        err = f"Error processing track {track.id}: {e}"
        job.meta["errors"] = job.meta["errors"] + [err]
        job.save_meta()


def split_vocal(track: NendoTrack, nd: Nendo, result_list: List[NendoTrack]):
    stems = nd.plugins.stemify_demucs(track=track, stem_types=["vocals", "no_vocals"], filter_silent=False)
    vocals, no_vocals = stems[0], stems[1]

    # remove unused track
    nd.library.remove_track(vocals.id, remove_relationships=True)

    # override meta for new track
    no_vocals.meta = dict(track.meta)
    result_list.append(no_vocals)
    return no_vocals


def main():
    parser = argparse.ArgumentParser(description="MusicGen training.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)

    # Musicgen specific arguments
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--remove_vocals", action="store_true", default=False)
    parser.add_argument("--run_analysis", action="store_true", default=False)
    parser.add_argument("--batch_size", type=int, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--lr", type=float, required=True)

    args = parser.parse_args()
    restrict_tf_memory()
    nd = Nendo()
    redis_conn = redis.Redis(
        host="redis",
        port=6379,
        db=0,
    )
    job = Job.fetch(args.job_id, connection=redis_conn)
    job.meta["errors"] = []
    job.save_meta()

    target_collection = nd.library.get_collection(
        collection_id=args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()

    job.meta["progress"] = f"Preparing training for {len(tracks)} Tracks"
    job.save_meta()

    train_collection_list = []
    train_collection = None
    try:

        if args.remove_vocals:
            for i, track in enumerate(tracks):
                process_track(
                    job,
                    f"Removing vocals for Track {i + 1}/{len(tracks)}",
                    track,
                    split_vocal,
                    nd=nd,
                    result_list=train_collection_list,
                )
        else:
            train_collection_list = tracks

        free_memory(nd.plugins.stemify_demucs.plugin_instance)

        if args.run_analysis:
            for i, track in enumerate(train_collection_list):
                process_track(
                    job,
                    f"Analyzing Track {i + 1}/{len(tracks)}",
                    track,
                    nd.plugins.classify_core,
                )
            free_memory(nd.plugins.classify_core.plugin_instance)

        train_collection = nd.library.add_collection(
            name="Musicgen Training",
            user_id=args.user_id,
            track_ids=[track.id for track in train_collection_list],
            collection_type="temp",
        )

        job.meta["progress"] = f"Started Musicgen training, this might take a while..."
        job.save_meta()

        output_dir = Path.home() / ".cache" / "nendo" / "models" / "musicgen" / str(
            args.user_id) / target_collection.name.replace(" ", "_")

        if output_dir.exists():
            shutil.rmtree(output_dir)

        os.makedirs(output_dir, exist_ok=True)
        nd.plugins.musicgen.train(
            collection=train_collection,
            output_dir=output_dir.absolute().as_posix(),
            model=args.model,
            prompt=args.prompt,
            batch_size=args.batch_size,
            lr=args.lr,
            epochs=args.epochs,
            finetune=True
        )

        target_collection.set_meta({
            "musicgen_model": str(output_dir),
            "musicgen_prompt": args.prompt,
            "musicgen_model_type": args.model,
        })
    finally:
        # cleanup
        if train_collection is not None:
            nd.library.remove_collection(
                collection_id=train_collection.id,
                user_id=args.user_id,
                remove_relationships=True,
            )
        if args.remove_vocals:
            [nd.library.remove_track(track.id, remove_relationships=True) for track in train_collection_list]

        print(f"collection/{args.target_id}")


if __name__ == "__main__":
    main()
