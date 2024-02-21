from typing import List

from pydantic import BaseModel


class TrackFilter(BaseModel):
    filter_key: str = None
    filter_type: str = None
    filter_options: List[str] = []


def get_track_filters():
    return [
        TrackFilter(
            filter_key="type",
            filter_type="multi-select",
            filter_options=["track", "stem", "loop", "singleshot", "midi"],
        ),
        TrackFilter(
            filter_key="key",
            filter_type="multi-select",
            filter_options=[
                "c",
                "c#",
                "db",
                "d",
                "d#",
                "eb",
                "e",
                "f",
                "f#",
                "gb",
                "g",
                "g#",
                "ab",
                "a",
                "a#",
                "bb",
                "b",
                "cb",
                "e#",
                "fb",
                "b#",
            ],
        ),
        TrackFilter(
            filter_key="genre",
            filter_type="multi-select",
            filter_options=[
                "hip-hop",
                "jazz",
                "rock",
                "pop",
                "classical",
                "electronic",
            ],
        ),
        TrackFilter(
            filter_key="bpm",
            filter_type="multi-select",
            filter_options=list(map(str, range(50, 201))),
        ),
        # TrackFilter(
        #     filter_key="sort",
        #     filter_type="multi-select",
        #     filter_options=["asc", "desc", "random"],
        # ),
    ]
