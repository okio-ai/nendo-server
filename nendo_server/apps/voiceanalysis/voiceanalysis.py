# -*- encoding: utf-8 -*-
# ruff: noqa: BLE001, T201
"""Voice Analysis app."""
import argparse
import gc
import re
from typing import Any, Callable, List

import redis
import torch
from nendo import Nendo, NendoTrack
from rq.job import Job
from wrapt_timeout_decorator import timeout


@timeout(600)
def process_tracks(
        job: Job,
        progress_info: str,
        tracks: List[NendoTrack],
        func: Callable,
        **kwargs: Any,
):
    for i, track in enumerate(tracks):
        try:
            job.meta["progress"] = f"{progress_info} Track {i + 1}/{len(tracks)}"
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


def llm_analysis(
        track: NendoTrack,
        oom_threshold: int = 25000,
        split_size: int = 20000,  # current max on A10 + mistral-8bitQ
):
    nd = Nendo()

    transcription = track.get_plugin_value("transcription")

    # filter timestamps
    pattern = r"\[(\d{1,3}:\d{1,2})-(\d{1,3}:\d{1,2})\]:"
    transcription = re.sub(pattern, "", transcription).replace("\n", "")

    nd.logger.warning(f"Transcription Length: {len(transcription)}")

    if len(transcription) > oom_threshold:
        summaries = []
        splits = [transcription[i:i + split_size] for i in range(0, len(transcription), split_size)]
        for j, split in enumerate(splits):
            nd.logger.warning(f"split {j}/{len(splits)}")
            nd.logger.warning(f"split {split}")
            split_summary = nd.plugins.textgen.summarization(prompt=split)
            nd.logger.warning(f"summary {split_summary}")
            summaries.append(split_summary)

        transcription = " ".join(summaries)
        transcription = transcription.replace("\n", "")

    templates = nd.plugins.textgen.templates()
    result = nd.plugins.textgen(
        prompts=[transcription, transcription, transcription],
        system_prompts=[
            templates.TOPIC_DETECTION,
            templates.SENTIMENT_ANALYSIS,
            templates.SUMMARIZATION,
        ],
    )
    topics, sentiments, summary = result[0], result[1], result[2]
    nd.logger.warning(f"topics {topics}")
    nd.logger.warning(f"sentiments {sentiments}")
    nd.logger.warning(f"summary {summary}")


    track.add_plugin_data(
        key="summary",
        value=summary,
        plugin_name="nendo_plugin_textgen",
        plugin_version="0.1.0",
    )
    track.add_plugin_data(
        key="sentiment_analysis",
        value=sentiments,
        plugin_name="nendo_plugin_textgen",
        plugin_version="0.1.0",
    )
    track.add_plugin_data(
        key="topic_detection",
        value=topics,
        plugin_name="nendo_plugin_textgen",
        plugin_version="0.1.0",
    )


def main():
    parser = argparse.ArgumentParser(description="Voice analysis.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=True)
    parser.add_argument("--target_id", type=str, required=True)

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
        collection_id = args.target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()

    process_tracks(
        job, "Transcribing", tracks, nd.plugins.transcribe_whisper,
        return_timestamps=True,
    )
    free_memory(nd.plugins.transcribe_whisper.plugin_instance.pipe)

    process_tracks(
        job, "LLM Analyzing", tracks, llm_analysis,
    )
    free_memory(nd.plugins.textgen.plugin_instance.model)

    process_tracks(
        job, "Embedding", tracks, nd.library.embed_track,
    )
    free_memory(nd.plugins.embed_clap.plugin_instance)

    if (target_collection.collection_type == "temp"):
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
