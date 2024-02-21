# -*- encoding: utf-8 -*-
# ruff: noqa: BLE001, T201
"""Polymath."""

import argparse
import os
import signal
import uuid
from typing import List, Optional

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import redis
from nendo import Nendo, NendoResource, NendoTrack
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

def run_polymath(
    job: Job,
    track: NendoTrack,
    track_num: int,
    track_num_total: int,
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
) -> None:
    """Run polymath."""
    nd = Nendo()
    signal.alarm(TIMEOUT)
    results = [track]
    try:
        nd.logger.info(f"Processing Track {track.id}")
        duration = round(librosa.get_duration(y=track.signal, sr=track.sr), 3)
        # workaround to assign proper titles
        original_title = ""
        if "title" in track.meta and track.meta["title"] is not None:
            original_title = track.meta["title"]
        else:
            original_title = track.resource.meta["original_filename"]
        if (classify is True and (
            len(
                track.get_plugin_data(
                    plugin_name="nendo_plugin_classify_core",
                ),
            ) == 0 or nd.config.replace_plugin_data is True)):
            job.meta["progress"] = f"Analyzing Track {track_num}/{track_num_total}"
            job.save_meta()
            track.process("nendo_plugin_classify_core")
        stems = track
        if stemify is True and track.track_type != "stem":
            job.meta["progress"] = f"Stemifying Track {track_num}/{track_num_total}"
            job.save_meta()
            stems = track.process("nendo_plugin_stemify_demucs", stem_types=stem_types)
            # workaround for setting proper title
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
        quantized = stems
        if quantize is True:
            job.meta["progress"] = f"Quantizing Track {track_num}/{track_num_total}"
            job.save_meta()
            quantized = stems.process(
                "nendo_plugin_quantize_core",
                bpm=quantize_to_bpm,
            )
            if type(quantized) == NendoTrack:
                if not quantized.has_related_track(track_id=track.id, direction="from"):
                    quantized.relate_to_track(
                        track_id=track.id,
                        relationship_type="quantized",
                    )
                # workaround for setting proper title
                quantized.meta = dict(track.meta)
                duration = round(librosa.get_duration(y=quantized.signal, sr=quantized.sr), 3)
                quantized.set_meta(
                    {
                        "title": f"{original_title} - ({quantize_to_bpm} bpm)",
                        "duration": duration,
                    },
                )
                finish_track(quantized, add_to_collection_id)
                results.append(quantized)
            else:  # is a collection
                for j, qt in enumerate(quantized):
                    if not qt.has_related_track(track_id=track.id, direction="from"):
                        qt.relate_to_track(
                            track_id=track.id,
                            relationship_type="quantized",
                        )
                    qt.meta = dict(track.meta)
                    duration = round(librosa.get_duration(y=qt.signal, sr=qt.sr), 3)
                    if stems[j].track_type == "stem":
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
                    else:
                        qt.set_meta(
                            {
                                "title": f"{original_title} ({quantize_to_bpm} bpm)",
                                "duration": duration,
                            },
                        )
                    finish_track(qt, add_to_collection_id)
                    results = results.append(qt)
        loopified = quantized
        if loopify is True:
            loopified = []
            job.meta["progress"] = f"Loopifying Track {track_num}/{track_num_total}"
            job.save_meta()
            if type(quantized) == NendoTrack:
                quantized = [quantized]
            for qt in quantized:
                qt_loops = qt.process(
                    "nendo_plugin_loopify",
                    n_loops=n_loops,
                    beats_per_loop=beats_per_loop,
                )
                loopified += qt_loops
                num_loop = 1
                for lp in qt_loops:
                    if not lp.has_related_track(track_id=track.id, direction="from"):
                        lp.relate_to_track(
                            track_id=track.id,
                            relationship_type="loop",
                        )
                    stem_type = qt.meta["stem_type"] if qt.has_meta("stem_type") else ""
                    qt_info = (
                        f" ({quantize_to_bpm} bpm)"
                        if qt.track_type == "quantized"
                        else ""
                    )
                    lp.meta = dict(track.meta)
                    duration = round(librosa.get_duration(y=lp.signal, sr=lp.sr), 3)
                    lp.set_meta(
                        {
                            "title": f"{original_title} - {stem_type} loop {num_loop} {qt_info}",
                            "duration": duration,
                        },
                    )
                    finish_track(lp, add_to_collection_id)
                    results.append(lp)
                    num_loop += 1
        if embed is True:
            job.meta["progress"] = f"Embedding Track {track_num}/{track_num_total}"
            job.save_meta()
            if type(loopified) == NendoTrack:
                nd.library.embed_track(loopified)
            else:  # is a collection/list
                for t in loopified:
                    nd.library.embed_track(t)
    except Exception as e:
        if "Operation timed out" in str(e):
            err = f"Error processing track {track.id}: Operation Timed Out"
        else:
            err = f"Error processing track {track.id}: {e}"
        nd.logger.info(err)
        job.meta["errors"] = job.meta["errors"] + [err]
        job.save_meta()
    finally:
        signal.alarm(0)
    return results

if __name__ == "__main__":
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

    if args.target_id is None or len(args.target_id) == 0:
        tracks = nd.get_tracks()
    else:
        track_or_collection = nd.get_track_or_collection(args.target_id)
        if type(track_or_collection) == NendoTrack:
            tracks = [track_or_collection]
        else:
            tracks = track_or_collection.tracks()
    num_tracks = len(tracks)
    for i, track in enumerate(tracks):
        results = run_polymath(
            job=job,
            track=track,
            track_num=i+1,
            track_num_total=num_tracks,
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
    if args.add_to_collection_id is not None and len(args.add_to_collection_id) > 0:
        print("collection/" + args.add_to_collection_id)
    else:
        print(results[-1].id)
