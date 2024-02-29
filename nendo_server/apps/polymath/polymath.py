# -*- encoding: utf-8 -*-
# ruff: noqa: BLE001, T201
"""Polymath."""

import argparse
import gc
import os
import signal
import uuid
from typing import List, Optional, Any, Dict

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import redis
import tensorflow as tf
import torch
from nendo import Nendo, NendoResource, NendoTrack, NendoCollection
from rq.job import Job

TIMEOUT = 600


def timeout_handler(num, stack):
    raise TimeoutError("Operation timed out")


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


def restrict_tf_memory():
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        # Restrict TensorFlow to only allocate 2GB of memory on the first GPU
        try:
            tf.config.set_logical_device_configuration(
                gpus[0],
                [tf.config.LogicalDeviceConfiguration(memory_limit=2048)])
            logical_gpus = tf.config.list_logical_devices("GPU")
            print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
        except RuntimeError as e:
            # Virtual devices must be set before GPUs have been initialized
            print(e)


def free_memory(to_delete: Any):
    del to_delete
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def get_original_title(track: NendoTrack) -> str:
    if "title" in track.meta and track.meta["title"] is not None:
        return track.meta["title"]
    else:
        return track.resource.meta["original_filename"]


def get_duration(track: NendoTrack) -> float:
    return round(librosa.get_duration(y=track.signal, sr=track.sr), 3)


def run_polymath(
    job: Job,
    tracks: List[NendoTrack],
    classify: bool,
    stemify: bool,
    stem_types: List[str],
    quantize: bool,
    quantize_to_bpm: int,
    loopify: bool,
    n_loops: int,
    beats_per_loop: int,
    embed: bool,
    add_to_collection_id: Optional[str] = None,
) -> List[NendoTrack]:
    """Run polymath."""
    nd = Nendo()
    signal.alarm(TIMEOUT)
    n_tracks = len(tracks)
    results: List[NendoTrack] = []
    try:
        if stemify:
            stems_map: Dict[uuid.UUID, NendoCollection] = {}
            for n, track in enumerate(tracks):
                duration = get_duration(track)
                original_title = get_original_title(track)

                if track.track_type != "stem":
                    job.meta["progress"] = f"Stemifying Track {n + 1}/{n_tracks}"
                    job.save_meta()
                    stems = track.process(
                        "nendo_plugin_stemify_demucs",
                        stem_types=stem_types,
                    )

                    for stem in stems:
                        stem_type = stem.get_meta("stem_type")
                        stem.meta = dict(track.meta)
                        stem.set_meta(
                            {
                                "title": f"{original_title} - {stem_type} stem",
                                "stem_type": stem_type,
                                "duration": duration,
                            },
                        )
                        finish_track(stem, add_to_collection_id)
                        results.append(stem)

                    # remember which stems belong to which track
                    stems_map[track.id] = stems

            free_memory(nd.plugins.stemify_demucs.plugin_instance)

        if quantize:
            quantize_map: Dict[uuid.UUID, List[NendoTrack]] = {}
            for n, track in enumerate(tracks):
                duration = get_duration(track)
                original_title = get_original_title(track)

                job.meta["progress"] = f"Quantizing Track {n + 1}/{n_tracks}"
                job.save_meta()
                # quantize original track
                quantized = track.process(
                    "nendo_plugin_quantize_core",
                    bpm=quantize_to_bpm,
                )
                if not quantized.has_related_track(
                    track_id=track.id,
                    direction="from",
                ):
                    quantized.relate_to_track(
                        track_id=track.id,
                        relationship_type="quantized",
                    )
                # workaround for setting proper title
                quantized.meta = dict(track.meta)
                quantized.set_meta(
                    {
                        "title": f"{original_title} - ({quantize_to_bpm} bpm)",
                        "duration": duration,
                    },
                )
                finish_track(quantized, add_to_collection_id)
                results.append(quantized)

                # check for stems
                if stemify and track.id in stems_map:
                    stems = stems_map[track.id]
                    for j, stem in enumerate(stems): # type: NendoTrack
                        job.meta[
                            "progress"] = (
                                f"Quantizing Stem {j + 1}/{len(stems)} "
                                f"for Track {n + 1}/{n_tracks}"
                            )
                        job.save_meta()
                        qt = stem.process(
                            "nendo_plugin_quantize_core",
                            bpm=quantize_to_bpm,
                        )

                        # remember which quantized stems belong to which track
                        if track.id in quantize_map:
                            quantize_map[track.id].append(qt)
                        else:
                            quantize_map[track.id] = [qt]

                        if not qt.has_related_track(
                            track_id=track.id,
                            direction="from"
                        ):
                            qt.relate_to_track(
                                track_id=track.id,
                                relationship_type="quantized",
                            )
                        qt.meta = dict(track.meta)
                        qt.set_meta(
                            {
                                "title": (
                                    f"{original_title} - "
                                    f"{stems[j].meta['stem_type']} "
                                    f"({quantize_to_bpm} bpm)"
                                ),
                                "stem_type": stems[j].meta["stem_type"],
                                "duration": duration,
                            },
                        )
                        finish_track(qt, add_to_collection_id)
                        results.append(qt)

            free_memory(nd.plugins.quantize_core.plugin_instance)

        if loopify is True:
            for n, track in enumerate(tracks):
                duration = get_duration(track)
                original_title = get_original_title(track)

                job.meta["progress"] = f"Loopifying Track {n + 1}/{n_tracks}"
                job.save_meta()
                loops = track.process(
                    "nendo_plugin_loopify",
                    n_loops=n_loops,
                    beats_per_loop=beats_per_loop,
                )
                for num_loop, lp in enumerate(loops): # type: (int, NendoTrack)
                    if not lp.has_related_track(track_id=track.id, direction="from"):
                        lp.relate_to_track(
                            track_id=track.id,
                            relationship_type="loop",
                        )
                    lp.meta = dict(track.meta)
                    lp.set_meta(
                        {
                            "title": f"{original_title} - loop {num_loop + 1}",
                            "duration": duration,
                        },
                    )
                    finish_track(lp, add_to_collection_id)
                    results.append(lp)

                if quantize and track.id in quantize_map:
                    quantized = quantize_map.get(track.id)

                    for qt in quantized:
                        qt_loops = qt.process(
                            "nendo_plugin_loopify",
                            n_loops=n_loops,
                            beats_per_loop=beats_per_loop,
                        )
                        for num_loop, lp in enumerate(qt_loops):
                            if not lp.has_related_track(
                                track_id=track.id,
                                direction="from",
                            ):
                                lp.relate_to_track(
                                    track_id=track.id,
                                    relationship_type="loop",
                                )
                            stem_type = (
                                qt.meta["stem_type"] if
                                qt.has_meta("stem_type") else ""
                            )
                            qt_info = (
                                f" ({quantize_to_bpm} bpm)"
                                if qt.track_type == "quantized"
                                else ""
                            )
                            lp.meta = dict(track.meta)
                            lp.set_meta(
                                {
                                    "title": (
                                        f"{original_title} - {stem_type} "
                                        f"loop {num_loop + 1} {qt_info}"
                                    ),
                                    "duration": duration,
                                },
                            )
                            finish_track(lp, add_to_collection_id)
                            results.append(lp)

                elif stemify and track.id in stems_map:
                    stems = stems_map.get(track.id)
                    for stem in stems:
                        stem_loops = stem.process(
                            "nendo_plugin_loopify",
                            n_loops=n_loops,
                            beats_per_loop=beats_per_loop,
                        )
                        for num_loop, lp in enumerate(stem_loops):
                            if not lp.has_related_track(
                                track_id=track.id,
                                direction="from"
                            ):
                                lp.relate_to_track(
                                    track_id=track.id,
                                    relationship_type="loop",
                                )
                            stem_type = (
                                stem.meta["stem_type"] if
                                stem.has_meta("stem_type") else ""
                            )
                            lp.meta = dict(track.meta)
                            lp.set_meta(
                                {
                                    "title": (
                                        f"{original_title} - {stem_type} "
                                        f"loop {num_loop + 1}"
                                    ),
                                    "duration": duration,
                                },
                            )
                            finish_track(lp, add_to_collection_id)
                            results.append(lp)

            free_memory(nd.plugins.loopify.plugin_instance)

        if classify:
            for n, track in enumerate(tracks):
                pd = track.get_plugin_data(plugin_name="nendo_plugin_classify_core")
                if len(pd) == 0 or nd.config.replace_plugin_data:
                    job.meta["progress"] = f"Analyzing Track {n + 1}/{n_tracks}"
                    job.save_meta()
                    track.process("nendo_plugin_classify_core")

            free_memory(nd.plugins.classify_core.plugin_instance)

        if embed:
            n_tracks += len(results)
            for n, track in enumerate(tracks):
                job.meta["progress"] = f"Embedding Track {n + 1}/{n_tracks}"
                job.save_meta()
                nd.library.embed_track(track)

            for n, track in enumerate(results):
                job.meta["progress"] = (
                    f"Embedding Track {n + len(tracks) + 1}"
                    f"/{n_tracks}"
                )
                job.save_meta()
                nd.library.embed_track(track)

            free_memory(nd.plugins.embed_clap.plugin_instance)
    except Exception as e:
        err = f"Error processing track {track.id}: {e}"
        nd.logger.info(err)
        job.meta["errors"] = job.meta["errors"] + [err]
        job.save_meta()
        raise
    finally:
        signal.alarm(0)
    return results


def main():
    parser = argparse.ArgumentParser(description="Polymath.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=True)
    parser.add_argument("--target_id", type=str, required=False)
    parser.add_argument("--classify", action="store_true", default=False)
    parser.add_argument("--stemify", action="store_true", default=False)
    parser.add_argument("--stem_types", metavar="N", type=str, nargs="+", required=True)
    parser.add_argument("--quantize", action="store_true", default=False)
    parser.add_argument("--quantize_to_bpm", type=int, required=True)
    parser.add_argument("--loopify", action="store_true", default=False)
    parser.add_argument("--n_loops", type=int, required=True)
    parser.add_argument("--beats_per_loop", type=int, required=True)
    parser.add_argument("--embed", action="store_true", default=False)
    parser.add_argument("--add_to_collection_id", type=str, required=False)

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
        collection_id=args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()
    results = run_polymath(
        job=job,
        tracks=tracks,
        classify=args.classify,
        stemify=args.stemify,
        stem_types=args.stem_types,
        quantize=args.quantize,
        quantize_to_bpm=args.quantize_to_bpm,
        loopify=args.loopify,
        n_loops=args.n_loops,
        beats_per_loop=args.beats_per_loop,
        embed=args.embed,
        add_to_collection_id=args.add_to_collection_id,
    )

    if target_collection.collection_type == "temp":
        nd.library.remove_collection(
            collection_id=target_collection.id,
            user_id=args.user_id,
            remove_relationships=True,
        )
    if args.add_to_collection_id is not None and len(args.add_to_collection_id) > 0:
        print("collection/" + args.add_to_collection_id)
    else:
        if len(results) > 0:
            print(results[-1].id)
        else:
            print("")


if __name__ == "__main__":
    main()
