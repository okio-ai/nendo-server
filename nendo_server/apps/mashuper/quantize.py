# -*- encoding: utf-8 -*-
"""Actions used by the Mashuper app."""
# ruff: noqa: ARG001, T201, D103

import argparse

from nendo import Nendo


def quantize(
    job_id: str,
    user_id: str,
    target_id: str,
    target_bpm: int = 120,
) -> None:
    nd = Nendo()
    target_collection = nd.library.get_collection(
        collection_id=target_id,
        get_related_tracks=False,
    )
    tracks = target_collection.tracks()
    track = tracks[0]
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
    if target_collection.collection_type == "temp":
        nd.library.remove_collection(
            collection_id=target_collection.id,
            user_id=user_id,
            remove_relationships=True,
        )
    print(q_track.id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantize.")
    parser.add_argument("--user_id", type=str, required=True)
    parser.add_argument("--job_id", type=str, required=True)
    parser.add_argument("--target_id", type=str, required=True)
    parser.add_argument("--target_bpm", type=int, required=True)

    args = parser.parse_args()

    quantize(
        job_id=args.job_id,
        user_id=args.user_id,
        target_id=args.target_id,
        target_bpm=args.target_bpm,
    )
