# -*- encoding: utf-8 -*-
"""Musicanalysis app."""
# ruff: noqa: BLE001, I001, T201
import argparse
import gc
import signal
from typing import Any, Callable, List

import redis
import torch
from nendo import Nendo
from nendo import NendoTrack
from rq.job import Job

TIMEOUT = 600


def timeout_handler(num, stack):
    raise TimeoutError("Operation timed out")


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


def process_tracks_with_timeout(
        job: Job,
        timeout: int,
        progress_info: str,
        tracks: List[NendoTrack],
        func: Callable,
        **kwargs: Any,
):
    for i, track in enumerate(tracks):
        signal.alarm(timeout)
        try:
            job.meta["progress"] = f"{progress_info} Track {i + 1}/{len(tracks)}"
            job.save_meta()
            func(track=track, **kwargs)
        except Exception as e:
            if "Operation timed out" in str(e):
                err = f"Error processing track {track.id}: Operation Timed Out"
            else:
                err = f"Error processing track {track.id}: {e}"
            # nd.logger.info(err)
            job.meta["errors"] = job.meta["errors"] + [err]
            job.save_meta()
            return
        finally:
            signal.alarm(0)


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

    signal.signal(signal.SIGALRM, timeout_handler)


    target_collection = nd.library.get_collection(
        collection_id = args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()

    process_tracks_with_timeout(
        job, TIMEOUT, "Captioning", tracks, nd.plugins.caption_lpmusiccaps,
    )
    free_memory(nd.plugins.caption_lpmusiccaps.plugin_instance.model)

    process_tracks_with_timeout(
        job, TIMEOUT, "Analyzing", tracks, nd.plugins.classify_core,
    )
    free_memory(nd.plugins.classify_core.plugin_instance)

    process_tracks_with_timeout(
        job, TIMEOUT, "Embedding", tracks, nd.library.embed_track,
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
