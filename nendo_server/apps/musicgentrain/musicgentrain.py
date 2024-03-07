# -*- encoding: utf-8 -*-
"""Musicgeneration app."""
# ruff: noqa: BLE001, T201, I001
import signal
import argparse
import gc
from pathlib import Path
from typing import Any, List, Callable

import redis
import torch
from nendo import Nendo
from nendo import NendoTrack
from rq.job import Job


def free_memory(to_delete: Any):
    del to_delete
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


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


def main():
    parser = argparse.ArgumentParser(description="MusicGen training.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=False)
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)

    # Musicgen specific arguments
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)

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

    target_collection = nd.library.get_collection(
        collection_id=args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()

    job.meta["progress"] = f"Preparing training for {len(tracks)} Tracks"
    job.save_meta()

    train_collection_list = []

    for i, track in enumerate(tracks):
        job.meta["progress"] = f"Removing vocals for Track {i + 1}/{len(tracks)}"
        job.save_meta()
        stems = nd.plugins.stemify_demucs(track=track, stem_types=["vocals", "no_vocals"])
        vocals, no_vocals = stems[0], stems[1]

        # remove unused track
        nd.library.remove_track(vocals.id, remove_relationships=True)
        train_collection_list.append(no_vocals)

    free_memory(nd.plugins.stemify_demucs.plugin_instance)
    process_tracks_with_timeout(
        job, 600, "Analyzing", tracks, nd.plugins.classify_core,
    )

    train_collection = nd.library.add_collection(
        name="Musicgen Training",
        user_id=args.user_id,
        track_ids=[track.id for track in train_collection_list],
        collection_type="temp",
        batch_size=1,
        lr=0.5,
        epochs=3,
    )

    job.meta["progress"] = f"Started Musicgen training..."
    job.save_meta()

    output_dir = Path.home() / ".cache" / "nendo" / "models" / "musicgen" / str(args.user_id) / target_collection.name
    nd.plugins.musicgen.train(
        collection=train_collection,
        output_dir=output_dir,
        model=args.model,
        prompt=args.prompt,
        finetune=True
    )

    target_collection.set_meta({
        "musicgen_model": str(output_dir),
        "musicgen_prompt": args.prompt,
        "musicgen_model_type": args.model,
    })

    # cleanup
    nd.library.remove_collection(
        collection_id=train_collection.id,
        user_id=args.user_id,
        remove_relationships=True,
    )
    [nd.library.remove_track(track.id, remove_relationships=True) for track in train_collection_list]

    print("collection/" + args.add_to_collection_id)


if __name__ == "__main__":
    main()
