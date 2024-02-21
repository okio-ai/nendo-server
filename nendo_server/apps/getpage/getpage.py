# -*- encoding: utf-8 -*-
"""Actions for running Polymath."""

import argparse

import redis
import requests
from bs4 import BeautifulSoup
from nendo import Nendo, NendoTrack
from readability import Document
from rq.job import Job


def getpage(
    job_id: str,
    target_id: str,
):
    """Crawl, summarize and embed a website."""
    redis_conn = redis.Redis(
        host="redis",
        port=6379,
        db=0,
    )
    job = Job.fetch(job_id, connection=redis_conn)
    nd = Nendo()
    track_or_collection = nd.get_track_or_collection(target_id)
    if type(track_or_collection) == NendoTrack:
        tracks = [track_or_collection]
    else:
        tracks = track_or_collection.tracks()
    num_tracks = len(tracks)
    templates = nd.plugins.textgen.templates()
    for i, track in enumerate(tracks):
        job.meta["progress"] = f"Crawling website {i+1}/{num_tracks}"
        job.save_meta()
        response = requests.get(track.get_meta("url"))  # noqa: S113
        doc = Document(response.text)
        soup = BeautifulSoup(doc.summary(), "html.parser")
        body = soup.get_text()
        track.add_plugin_data(
            plugin_name="getpage_app",
            plugin_version="0.1.0",
            key="body",
            value=body,
        )
        job.meta["progress"] = f"Summarizing website {i+1}/{num_tracks}"
        job.save_meta()
        result = nd.plugins.textgen(
            prompts=[body],
            system_prompts=[templates.SUMMARIZATION],
        )
        summary = result[0]
        track.add_plugin_data(
            plugin_name="nendo_plugin_textgen",
            key="summary",
            value=summary,
        )
        job.meta["progress"] = f"Embedding website {i+1}/{num_tracks}"
        nd.library.embed_track(track)
    nd.logger.info(target_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract main content from a webpage.")
    parser.add_argument("--job_id", type=str, required=True)
    parser.add_argument("--target_id", type=str, required=True)
    args = parser.parse_args()
    getpage(
        job_id=args.job_id,
        target_id=args.target_id,
    )
