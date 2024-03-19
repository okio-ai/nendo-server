# -*- encoding: utf-8 -*-
"""Musicanalysis app."""
# ruff: noqa: BLE001, I001, T201
import argparse
import gc
import os
from typing import Any, Callable

import redis
import torch
from nendo import Nendo
from nendo import NendoTrack
from rq.job import Job
from wrapt_timeout_decorator import timeout


def restrict_tf_memory():
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


def free_memory(to_delete: Any):
    del to_delete
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


def main():
    parser = argparse.ArgumentParser(description="Music analysis.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--target_id", type=str, required=True)

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
        collection_id = args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()

    for i, track in enumerate(tracks):
        process_track(
            job,
            f"Analyzing Track {i + 1}/{len(tracks)}",
            track,
            nd.plugins.caption_lpmusiccaps,
        )
    free_memory(nd.plugins.caption_lpmusiccaps.plugin_instance.model)

    for i, track in enumerate(tracks):
        process_track(
            job,
            f"Analyzing Track {i + 1}/{len(tracks)}",
            track,
            nd.plugins.classify_core,
        )
    free_memory(nd.plugins.classify_core.plugin_instance)

    for i, track in enumerate(tracks):
        process_track(
            job,
            f"Embedding Track {i + 1}/{len(tracks)}",
            track,
            nd.library.embed_track,
        )
    free_memory(nd.plugins.embed_clap.plugin_instance)

    if target_collection.collection_type == "temp":
        nd.library.remove_collection(
            collection_id=target_collection.id,
            user_id=args.user_id,
            remove_relationships=True,
        )
    else:
        print(f"collection/{args.target_id}")
        return
    if len(tracks) > 0:
        print(tracks[-1].id)
    else:
        print("")


if __name__ == "__main__":
    main()
